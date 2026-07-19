"""Tick/L2 market-maker backtester for Hyperliquid (native, no LLM).

Replays the L2 snapshots accumulated by `l2_accumulator.py` and simulates a
market maker that rests bids/offers around mid. This is the fidelity layer the
bar-level pipeline cannot express: it resolves WHO fills and the adverse-
selection cost that determines whether maker-rebate alpha is real.

Fill model (the honest core): a resting maker order does NOT fill merely because
its price was touched. Price-time priority means better-priced orders fill first,
so our order fills only after the traded volume consumes all the size resting at
better prices. We observe traded volume as the book-depth delta between
consecutive snapshots (selling consumes bid depth; buying consumes ask depth).
Our fill quantity is then min(our_size, max(0, traded_volume - size_ahead_of_us)),
where size_ahead is the cumulative book size at prices better than ours.

This naturally models adverse selection: we only fill when directional pressure
is large enough to eat through to our level — exactly the toxic-flow scenario
where the post-fill mid moves against us. That cost is realized in mark-to-market
PnL and also logged explicitly as `adverse_selection_cost`.

Honest simplifications (conservative direction):
  - ~1s snapshot granularity cannot resolve sub-second queue races; book-depth
    deltas are a lower bound on true traded volume (miss intra-second trades),
    so fills are understated / adverse selection overstated. Safe direction.
  - Orders are cancel/replaced each snapshot (no multi-snapshot resting beyond
    one interval) — avoids free-option look-ahead.
  - A constant placement latency may be applied (orders lag mid by `latency_s`).
Reuses `economics.HLFeeSchedule` / `fee_for` so maker rebates vs taker fees are
identical to the bar-level venue model.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple, Union

from slate_core.dex.backtester.economics import HLFeeSchedule, fee_for, oracle_ok
from slate_core.dex.backtester.l2_tick_backtester import load_l2_snapshots


# A market-maker policy = the parameter vector the optimizer searches.
@dataclass
class MMPolicy:
    half_spread_bps: float = 10.0     # half-width of the quoted spread around mid
    inv_skew_bps: float = 2.0         # inventory skew (quotes shift against position)
    size: float = 0.5                 # base order size (base units)


# Per-snapshot microstructure state handed to an EVOLVED policy_fn. Field names
# MUST match the GP feature terminals (slate_core/dex/evolution/gp/genome.py).
@dataclass
class SnapshotState:
    i: int
    mid: float
    mid_ret1: float                # 1-snapshot mid return
    mid_ret5: float                # 5-snapshot mid return
    imbalance: float               # top-of-book order-flow imbalance (-1..1)
    spread_bps: float              # bid-ask spread (bps)
    depth_imb: float               # (bid_depth - ask_depth) / total
    bid_consumed: float            # traded volume that hit bids this step (depth delta)
    ask_consumed: float            # traded volume that hit asks this step
    queue_ahead_bid: float         # size resting at the best bid (queue proxy)
    queue_ahead_ask: float         # size resting at the best ask
    inv_frac: float                # signed inventory fraction (-1..1)
    vol_of_vol: float              # rolling stdev of recent mid returns (bps)
    adv_recent: float              # recent adverse-selection cost (bps)
    equity_slope: float            # recent equity-curve slope
    equity_curve: List[float] = field(default_factory=list)
    fill_rate: float = 0.0


# An evolved policy maps state -> (half_spread_bps, inv_skew_bps, size) or None (abstain).
PolicyFn = Callable[[SnapshotState], Optional[Tuple[float, float, float]]]
Policy = Union[MMPolicy, PolicyFn]


@dataclass
class MMTickResult:
    final_equity: float
    total_pnl: float                  # final_equity - starting capital
    total_rebates: float              # cash back from negative maker fees (>=0)
    total_fees: float                 # maker+taker fees paid (>=0)
    total_funding: float              # funding paid on inventory
    adverse_selection_cost: float     # MTM loss attributable to post-fill mid drift (measured)
    adverse_selection_charge: float   # explicit toxic-flow tax charged per fill (calibrated)
    maker_fills: int
    taker_fills: int
    fill_rate: float                  # maker fills / snapshots quoted (0..1)
    inventory_turnover: float         # sum(|filled qty|) / starting capital
    bars_in_market: int               # snapshots with a non-flat position
    n_snapshots: int
    max_drawdown_pct: float
    equity_curve: List[float] = field(default_factory=list)


def _depth_side(levels: Sequence) -> float:
    """Total size on one side of the book (levels = [[px, sz], ...])."""
    return float(sum(sz for _, sz in levels)) if levels else 0.0


def _size_ahead_better_bid(bids: Sequence, our_bid_px: float) -> float:
    """Cumulative bid size at prices STRICTLY BETTER (higher) than our resting bid.
    These orders have priority and fill before us, so they sit 'ahead' in the queue.
    """
    return float(sum(sz for px, sz in bids if px > our_bid_px)) if bids else 0.0


def _size_ahead_better_ask(asks: Sequence, our_ask_px: float) -> float:
    """Cumulative ask size at prices STRICTLY BETTER (lower) than our resting ask."""
    return float(sum(sz for px, sz in asks if px < our_ask_px)) if asks else 0.0


def _build_snapshot_state(i, cur, cur_mid, bid_consumed, ask_consumed, inv_frac,
                          mid_hist, adv_hist, eq_hist, equity_curve,
                          maker_fills, quoted_snaps) -> SnapshotState:
    """Build the per-snapshot microstructure state consumed by an evolved policy."""
    bids = cur.get("bids") or []
    asks = cur.get("asks") or []
    bd = float(sum(sz for _, sz in bids))
    ad = float(sum(sz for _, sz in asks))
    depth_imb = (bd - ad) / (bd + ad) if (bd + ad) > 0 else 0.0
    # recent mid returns + vol-of-vol (bps)
    mids = list(mid_hist)
    mid_ret1 = (mids[-1] / mids[-2] - 1.0) if len(mids) >= 2 and mids[-2] else 0.0
    mid_ret5 = (mids[-1] / mids[-6] - 1.0) if len(mids) >= 6 and mids[-6] else 0.0
    if len(mids) >= 6:
        rets = [(mids[k] / mids[k - 1] - 1.0) for k in range(max(1, len(mids) - 20), len(mids)) if mids[k - 1]]
        mean = sum(rets) / len(rets) if rets else 0.0
        var = sum((r - mean) ** 2 for r in rets) / len(rets) if rets else 0.0
        vol_of_vol = math.sqrt(var) * 10_000.0
    else:
        vol_of_vol = 0.0
    adv_recent = sum(adv_hist) / len(adv_hist) if adv_hist else 0.0
    eqs = list(eq_hist)
    equity_slope = (eqs[-1] / eqs[-6] - 1.0) if len(eqs) >= 6 and eqs[-6] else 0.0
    return SnapshotState(
        i=i, mid=cur_mid, mid_ret1=mid_ret1, mid_ret5=mid_ret5,
        imbalance=float(cur.get("imbalance", 0.0)),
        spread_bps=float(cur.get("spread_bps", 0.0)),
        depth_imb=depth_imb, bid_consumed=bid_consumed, ask_consumed=ask_consumed,
        queue_ahead_bid=float(bids[0][1]) if bids else 0.0,
        queue_ahead_ask=float(asks[0][1]) if asks else 0.0,
        inv_frac=inv_frac, vol_of_vol=vol_of_vol, adv_recent=adv_recent,
        equity_slope=equity_slope, equity_curve=list(equity_curve),
        fill_rate=(maker_fills / quoted_snaps) if quoted_snaps else 0.0,
    )


def backtest_mm(
    snaps: List[dict],
    policy: Policy,
    schedule: Optional[HLFeeSchedule] = None,
    capital: float = 10_000.0,
    max_inventory: float = 2.0,
    funding_rate_per_snap: float = 0.0,
    adv_lookback: int = 5,
    adverse_selection_bps: float = 0.6,   # empirical SOL post-fill adverse drift (~0.6bps/fill)
    max_half_spread_bps: float = 15.0,
    max_inv_skew_bps: float = 30.0,
) -> MMTickResult:
    """Backtest a market-maker policy over a stream of L2 snapshots.

    `policy` is either an `MMPolicy` (fixed half/skew/size) OR a callable
    `policy_fn(SnapshotState) -> (half_spread_bps, inv_skew_bps, size) | None`
    (an evolved GP policy; None = abstain this snapshot). Each snapshot: quote
    bid/ask around mid (skewed against inventory), then resolve the PREVIOUS
    snapshot's resting orders against this snapshot's book-depth delta. Fills are
    maker (at our price); inventory accrues funding.

    Honesty guards (so results are believable, not gamed by aggressive policies):
      - `adverse_selection_bps`: an explicit toxic-flow tax charged on EVERY maker
        fill. MTM only realizes 1 snap of adverse drift, but real adverse
        selection unfolds over ~10 snaps (empirically ~0.6bps/fill on SOL L2) — a
        policy can otherwise fill on a toxic order and exit before the drift hits.
        Charging ~1bps/fill makes the net spread capture realistic. Conservative.
      - `max_half_spread_bps` / `max_inv_skew_bps`: clamp evolved quotes to ranges
        physically realistic for a ~1bps-spread asset (HL SOL). A 50-500bps quote
        on a 1bps book is an artifact, not a real MM strategy.
    """
    sched = schedule or HLFeeSchedule()
    is_callable = callable(policy)
    as_rate = adverse_selection_bps / 10_000.0
    # Fixed-policy constants (only used when policy is an MMPolicy).
    half = max(1.0, getattr(policy, "half_spread_bps", 10.0)) / 10_000.0
    skew = getattr(policy, "inv_skew_bps", 0.0) / 10_000.0
    order_size = max(0.0, getattr(policy, "size", 0.5))

    position = 0.0
    cash = capital
    total_rebates = 0.0
    total_fees = 0.0
    total_funding = 0.0
    adverse_selection_cost = 0.0
    adverse_selection_charge = 0.0     # explicit toxic-flow tax (calibrated per fill)
    maker_fills = 0
    taker_fills = 0
    inventory_turnover = 0.0
    bars_in_market = 0
    quoted_snaps = 0

    # Rolling microstructure state for the evolved policy's features.
    mid_hist: deque = deque(maxlen=32)          # recent mids (returns + vol_of_vol)
    adv_hist: deque = deque(maxlen=20)          # recent settled adverse-selection (bps)
    eq_hist: deque = deque(maxlen=20)           # recent equity (slope)

    # Resting orders placed at snap i-1, resolved against snap i.
    resting_bid_px: Optional[float] = None
    resting_ask_px: Optional[float] = None
    resting_bid_sz = 0.0
    resting_ask_sz = 0.0
    # Track recent fill (price, sign, snap index) to measure adverse selection.
    pending_adv: List = []   # list of [fill_px, side(+1 buy / -1 sell), snap_idx]

    equity_curve: List[float] = []
    peak_equity = capital

    for i in range(1, len(snaps)):
        prev = snaps[i - 1]
        cur = snaps[i]
        prev_mid = float(prev["mid"])
        cur_mid = float(cur["mid"])
        prev_bids = prev.get("bids") or []
        prev_asks = prev.get("asks") or []
        cur_bids = cur.get("bids") or []
        cur_asks = cur.get("asks") or []

        # 1) Resolve resting orders placed at i-1 against book-depth delta.
        #    Selling consumes bid depth; our bid fills only after size_ahead is eaten.
        bid_consumed = max(0.0, _depth_side(prev_bids) - _depth_side(cur_bids))
        ask_consumed = max(0.0, _depth_side(prev_asks) - _depth_side(cur_asks))

        if resting_bid_px is not None and bid_consumed > 0.0:
            ahead = _size_ahead_better_bid(prev_bids, resting_bid_px)
            reached = bid_consumed - ahead
            if reached > 0.0:
                # Cap to remaining inventory capacity so position can NEVER exceed
                # max_inventory (a single fill otherwise overshoots the cap).
                fill_qty = min(resting_bid_sz, reached,
                               max(0.0, max_inventory - position))
                if fill_qty > 0.0:
                    notional = fill_qty * resting_bid_px
                    fee = fee_for(notional, is_maker=True, schedule=sched)
                    cash -= notional                 # pay for the bought base
                    if fee < 0.0:
                        total_rebates += -fee        # rebate = cash in
                    else:
                        total_fees += fee
                    cash -= fee                       # cost (fee>0) subtracts; rebate (fee<0) adds
                    # Adverse-selection tax: a maker fill is disproportionately
                    # toxic (informed flow); the real adverse drift unfolds over
                    # ~10 snaps while MTM only sees 1. Charge it explicitly so a
                    # policy can't profit by exiting before the drift realizes.
                    as_charge = as_rate * notional
                    cash -= as_charge
                    adverse_selection_charge += as_charge
                    position += fill_qty
                    inventory_turnover += fill_qty
                    maker_fills += 1
                    pending_adv.append([resting_bid_px, +1, i])

        if resting_ask_px is not None and ask_consumed > 0.0 and position > 0.0:
            ahead = _size_ahead_better_ask(prev_asks, resting_ask_px)
            reached = ask_consumed - ahead
            if reached > 0.0:
                fill_qty = min(resting_ask_sz, reached, position)
                if fill_qty > 0.0:
                    notional = fill_qty * resting_ask_px
                    fee = fee_for(notional, is_maker=True, schedule=sched)
                    cash += notional                 # receive for the sold base
                    if fee < 0.0:
                        total_rebates += -fee
                    else:
                        total_fees += fee
                    cash -= fee                       # cost (fee>0) subtracts; rebate (fee<0) adds
                    as_charge = as_rate * notional    # toxic-flow tax (sell side)
                    cash -= as_charge
                    adverse_selection_charge += as_charge
                    position -= fill_qty
                    inventory_turnover += fill_qty
                    maker_fills += 1
                    pending_adv.append([resting_ask_px, -1, i])

        # 2) Mark-to-market equity + funding.
        if position != 0.0:
            bars_in_market += 1
            if funding_rate_per_snap != 0.0:
                f = position * cur_mid * funding_rate_per_snap
                cash -= f
                total_funding += f

        equity = cash + position * cur_mid
        equity_curve.append(equity)
        peak_equity = max(peak_equity, equity)
        mid_hist.append(cur_mid)
        eq_hist.append(equity)

        # 3) Settle adverse-selection measurements now that `adv_lookback` snaps passed.
        still_pending = []
        for entry in pending_adv:
            fill_px, side, fidx = entry
            if i - fidx >= adv_lookback:
                drift = (cur_mid - fill_px) / fill_px   # +ve = price rose after fill
                # Adverse: a buy that fell, or a sell that rose.
                moved_against = max(0.0, -side * drift)
                adverse_selection_cost += moved_against * order_size
                adv_hist.append(moved_against * 10_000.0)   # bps
            else:
                still_pending.append(entry)
        pending_adv = still_pending

        # 4) Place new resting quotes for the next interval (cancel/replace).
        inv_frac = max(-1.0, min(1.0, position / max_inventory)) if max_inventory > 0 else 0.0
        quote_mid = cur_mid
        if is_callable:
            state = _build_snapshot_state(
                i, cur, cur_mid, bid_consumed, ask_consumed, inv_frac,
                mid_hist, adv_hist, eq_hist, equity_curve,
                maker_fills, quoted_snaps)
            try:
                q = policy(state)
            except Exception:  # noqa: BLE001 - sandbox already guards, but be safe
                q = None
            if isinstance(q, tuple) and len(q) == 3:
                # Clamp evolved quotes to physically-realistic ranges for a
                # ~1bps-spread asset. A 50-500bps quote on HL SOL is an artifact.
                c_half = max(1.0, min(max_half_spread_bps, float(q[0]))) / 10_000.0
                c_skew = max(-max_inv_skew_bps, min(max_inv_skew_bps, float(q[1]))) / 10_000.0
                c_size = max(0.0, min(max_inventory, float(q[2])))
                adj = -c_skew * inv_frac
                bid_px = quote_mid * (1.0 - c_half + adj)
                ask_px = quote_mid * (1.0 + c_half + adj)
                this_size = c_size
            else:
                bid_px = ask_px = None      # abstain this snapshot
                this_size = 0.0
        else:
            adj = -skew * inv_frac          # long inventory -> shift quotes down
            bid_px = prev_mid * (1.0 - half + adj)
            ask_px = prev_mid * (1.0 + half + adj)
            this_size = order_size
        # Oracle guard: refuse quotes >oracle_tol from mid (Hyperliquid rejects these).
        bid_ok = bid_px is not None and oracle_ok(bid_px, quote_mid, sched) and position < max_inventory
        ask_ok = ask_px is not None and oracle_ok(ask_px, quote_mid, sched) and position > -max_inventory
        resting_bid_px = bid_px if bid_ok else None
        resting_ask_px = ask_px if ask_ok else None
        resting_bid_sz = this_size if bid_ok else 0.0
        resting_ask_sz = this_size if ask_ok else 0.0
        if bid_ok or ask_ok:
            quoted_snaps += 1

    # Force-close any residual inventory at the last mid (taker).
    if abs(position) > 1e-9 and snaps:
        last_mid = float(snaps[-1]["mid"])
        notional = abs(position) * last_mid
        fee = fee_for(notional, is_maker=False, schedule=sched)
        if position > 0:
            cash += notional
        else:
            cash -= notional
        cash -= fee  # taker fee is a cost (fee>0)
        total_fees += max(0.0, fee)
        taker_fills += 1
        position = 0.0

    final_equity = cash  # position closed
    total_pnl = final_equity - capital
    max_dd = (peak_equity - min(equity_curve)) / peak_equity if equity_curve and peak_equity > 0 else 0.0
    fill_rate = maker_fills / quoted_snaps if quoted_snaps else 0.0

    return MMTickResult(
        final_equity=final_equity, total_pnl=total_pnl,
        total_rebates=total_rebates, total_fees=total_fees,
        total_funding=total_funding, adverse_selection_cost=adverse_selection_cost,
        adverse_selection_charge=adverse_selection_charge,
        maker_fills=maker_fills, taker_fills=taker_fills, fill_rate=fill_rate,
        inventory_turnover=inventory_turnover, bars_in_market=bars_in_market,
        n_snapshots=max(0, len(snaps) - 1), max_drawdown_pct=max_dd,
        equity_curve=equity_curve,
    )


__all__ = ["MMPolicy", "MMTickResult", "backtest_mm", "load_l2_snapshots"]
