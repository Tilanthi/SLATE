"""Event-driven execution engine — the realism core (Tier 1a).

Replaces vectorized close-to-close attribution for finalists with an order
lifecycle: each bar the strategy states a TARGET position (decided from the
prior close, no lookahead); the engine emits an order to reach it; the matching
engine fills it against the bar (or ticks) with:

  * taker fills at the close +/- slippage +/- square-root market impact,
  * optional partial fills capped by a participation rate (volume you can take),
  * optional maker fills that rest and fill only when the bar trades through the
    quote, capturing adverse selection (you fill at your price, then the bar
    closes against you) — reuses the logic from dex/backtester/mm_tick_backtester,
  * funding on the held position,
  * a configurable execution-latency lag.

In its simplest mode (taker, full fills, impact off) it is mathematically
identical to ``honest.backtest`` — the event engine is a strict generalization,
which the tests verify. The realism layers (impact, partial fills, maker adverse
selection) are added on top and each shaves the backtest Sharpe toward live.

Works for any venue (CEX/DEX) via the ``Venue`` object and for any strategy that
produces a target-position array (directional, carry, regime-gated). Market-
making and LP use their own dedicated evaluators (the queue logic there is
richer); this engine is the unified directional/finalist evaluator.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from slate_core.backtest.honest import (Venue, CEX, DEX, bars_per_year_from_index,
                                        _hours_per_bar, _metrics)
from slate_core.backtest.realism import sqrt_impact_bps


@dataclass
class Order:
    side: int                 # +1 buy, -1 sell, 0 none
    size_notional: float      # dollars to trade
    kind: str = "taker"       # "taker" | "maker"
    limit: Optional[float] = None   # limit price (maker)


@dataclass
class Fill:
    side: int
    price: float               # execution price (close for taker, limit for maker)
    size_notional: float       # dollars transacted
    fee: float
    slip_bps: float            # slippage charged (taker)
    impact_bps: float          # square-root impact charged (taker)
    reason: str


def match_order(order: Order, bar, venue: Venue, participation_cap: float,
                impact: bool, bar_vol_frac: float) -> Fill:
    """Fill one order against a bar (OHLC). `bar` is a dict-like with close/high/
    low/volume_usd. Returns a (possibly partial) fill.

    Taker: fills at the close; slippage + square-root impact are charged as cash
    costs (so quantity tracks the target exactly -> matches the vectorized honest
    engine in simple mode). Maker: rests at the limit, fills only if the bar
    trades through it (adverse selection realized by marking the acquired qty to
    the bar's close)."""
    close = bar["close"]
    vol_usd = max(bar.get("volume_usd", 0.0), 1e-9)
    max_size = participation_cap * vol_usd if participation_cap < 1 else abs(order.size_notional)
    size = min(abs(order.size_notional), max_size)
    if size <= 0:
        return Fill(order.side, close, 0.0, 0.0, 0.0, 0.0, "no_capacity")
    if order.kind == "taker":
        impact_bps = (sqrt_impact_bps(size, vol_usd, bar_vol_frac, venue.impact_k)
                      if impact else 0.0)
        return Fill(order.side, close, size, size * venue.taker_fee,
                    venue.slippage_bps, impact_bps, "taker")
    else:  # maker: rest at limit; fill only if the bar trades through the quote
        lim = order.limit if order.limit is not None else close
        touched = (order.side > 0 and bar["low"] <= lim) or (order.side < 0 and bar["high"] >= lim)
        if not touched:
            return Fill(order.side, lim, 0.0, 0.0, 0.0, 0.0, "not_touched")
        return Fill(order.side, lim, size, size * venue.maker_fee, 0.0, 0.0, "maker")


class EventBacktester:
    def __init__(self, venue: Venue = CEX, capital: float = 1.0, *,
                 mode: str = "taker", impact: bool = True,
                 participation_cap: float = 0.10, latency_bars: int = 0,
                 maker_halfspread_bps: float = 5.0, vol_lookback: int = 20,
                 liquidate_end: bool = True):
        self.venue = venue
        self.capital = capital
        self.mode = mode              # "taker" | "maker"
        self.impact = impact
        self.participation_cap = participation_cap
        self.latency_bars = latency_bars
        self.maker_halfspread_bps = maker_halfspread_bps
        self.vol_lookback = vol_lookback
        self.liquidate_end = liquidate_end

    def run(self, target, df: pd.DataFrame, funding: Optional[np.ndarray] = None) -> Dict:
        close = df["close"].astype(float).values
        high = df["high"].astype(float).values if "high" in df else close
        low = df["low"].astype(float).values if "low" in df else close
        vol = df["volume"].astype(float).values if "volume" in df else np.ones(len(close))
        volume_usd = np.abs(vol * close)
        n = len(close)
        target = np.asarray(target, dtype=float)
        assert len(target) == n
        if funding is None and "funding" in df.columns:
            funding = df["funding"].astype(float).values
        if funding is None:
            funding = np.zeros(n)
        ppy = bars_per_year_from_index(df.index)
        settlements_per_bar = _hours_per_bar(df) / self.venue.funding_interval_hours
        bar_ret = np.concatenate([[0.0], close[1:] / close[:-1] - 1.0])
        sigma = pd.Series(bar_ret).rolling(self.vol_lookback, min_periods=2).std().fillna(
            pd.Series(bar_ret).std()).values

        # Fraction-space engine. The position HELD over bar t is the decision made
        # at close[t-1]; the fill to reach it is executed AT close[t-1] (price and
        # volume of bar t-1). In simple mode (full taker fills, no impact) this is
        # mathematically identical to honest.backtest (held[t]=target[t-1]); the
        # realism layers (partial fills, impact, maker adverse selection, latency)
        # are added on top. No lookahead: the fill uses only bar <= t-1.
        pos = 0.0                 # achieved position fraction held over the current bar
        rets = np.zeros(n)
        fills: List[Fill] = []
        for t in range(1, n):
            dec = max(0, t - 1 - self.latency_bars)
            desired = target[dec]                 # decision from close[dec]
            delta = desired - pos
            cost = 0.0
            adverse = 0.0
            if abs(delta) > 1e-12:
                side = 1 if delta > 0 else -1
                size_dollars = abs(delta) * self.capital
                pb = t - 1                         # fill executes on bar t-1
                bar = {"close": close[pb], "high": high[pb], "low": low[pb],
                       "volume_usd": volume_usd[pb]}
                if self.mode == "maker":
                    lim = close[pb] * (1 - side * self.maker_halfspread_bps / 1e4)
                    order = Order(side, size_dollars, "maker", lim)
                else:
                    order = Order(side, size_dollars, "taker")
                fill = match_order(order, bar, self.venue, self.participation_cap,
                                   self.impact, sigma[pb])
                if fill.size_notional > 0:
                    fill_frac = side * fill.size_notional / self.capital
                    cost = (fill.fee + fill.size_notional *
                            (fill.slip_bps + fill.impact_bps) / 1e4) / self.capital
                    if fill.reason == "maker":
                        # adverse selection: acquired at `limit`, marked to close[pb].
                        # +ve = captured spread (close>limit); -ve = toxic (close<limit).
                        adverse = fill_frac * (close[pb] / fill.price - 1.0)
                    pos = pos + fill_frac
                    fills.append(fill)
            gross = pos * bar_ret[t]
            fund = -funding[t] * settlements_per_bar * pos
            rets[t] = gross + adverse - cost + fund
        # optional final liquidation: charge a taker fee on the ending position
        if self.liquidate_end and abs(pos) > 1e-12:
            rets[-1] -= abs(pos) * self.venue.taker_fee
        eq = np.cumprod(1 + np.nan_to_num(rets))
        m = _metrics(rets, eq, ppy)
        m["turnover"] = float(sum(f.size_notional for f in fills) / self.capital)
        m["n_fills"] = len(fills)
        m["impact_bps_mean"] = float(np.mean([f.impact_bps for f in fills]) if fills else 0)
        m["bars_per_year"] = ppy
        m["mode"] = self.mode
        return {"returns": rets, "equity": eq, "metrics": m, "fills": fills,
                "final_pos": float(pos)}


__all__ = ["Order", "Fill", "match_order", "EventBacktester"]
