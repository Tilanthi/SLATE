"""Bar-level DEX backtester with Hyperliquid economics.

Cash accounting: a buy pays notional out of cash (and the fee, or +rebate), a
sell adds notional; equity = cash + position*mark. This makes total PnL exact
without FIFO bookkeeping. Each bar the strategy's `act()` returns the orders it
wants active THIS bar; the backtester fills them via the bar-level fill model,
applies fees/rebates, enforces a leverage cap, and accrues funding. The strategy
sees only `history = df.iloc[:i+1]` (lookahead cage, same discipline as the CEX
backtester).

Honest v1 limits: bar-level maker fills approximate queue/adverse-selection
(needs L2); funding uses a constant rate by default (real per-bar funding can be
wired via funding_history later).
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from slate_core.dex.backtester.economics import HLFeeSchedule, fee_for
from slate_core.dex.backtester.fill_model import bar_fill, bar_fill_l2
from slate_core.dex.strategies.action import BarState, DexStrategy, Order


@dataclass
class DexBacktestConfig:
    fee_schedule: HLFeeSchedule = field(default_factory=HLFeeSchedule)
    initial_capital: float = 10000.0
    max_leverage: float = 3.0
    funding_interval_bars: int = 8     # HL funding ~8h; on 1h bars every 8 bars
    funding_rate: float = 0.0          # constant funding rate per interval (v1 proxy)
    warmup: int = 20
    l2_provider: Optional[Callable[[str, float], float]] = None
    # If set, (side, px) -> queue_ahead (resting size ahead of a maker order). The
    # backtester then uses queue-aware maker fills (bar_fill_l2) instead of the bar
    # proxy — graduating market-making from indicative to definitive. None => proxy.


@dataclass
class DexBacktestResult:
    final_equity: float
    total_pnl: float
    total_fees: float
    total_rebates: float
    total_funding: float
    total_trades: int
    maker_fills: int
    taker_fills: int
    maker_fraction: float
    n_bars: int
    bars_in_market: int
    max_drawdown_pct: float
    rejections: Dict[str, int]
    equity_curve: List[float]

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses_asdict_skip_curve(self)


def dataclasses_asdict_skip_curve(r: DexBacktestResult) -> Dict[str, Any]:
    d: Dict[str, Any] = {}
    for f in r.__dataclass_fields__:
        if f == "equity_curve":
            continue
        d[f] = getattr(r, f)
    return d


class DexBacktester:
    def __init__(self, config: DexBacktestConfig = None):
        self.config = config or DexBacktestConfig()

    def backtest(self, strategy: DexStrategy, df) -> DexBacktestResult:
        cfg = self.config
        sch = cfg.fee_schedule
        cash = cfg.initial_capital
        position = 0.0
        bars_in_market = 0
        equity_curve: List[float] = []
        maker_fills = taker_fills = 0
        total_fees = total_rebates = total_funding = 0.0
        rejections: Counter = Counter()
        n = len(df)
        last_close = cfg.initial_capital
        # Deferred execution (lookahead cage): orders decided at bar i fill at bar
        # i+1, so a strategy that acts on df.iloc[:i+1] can never trade on future info.
        pending: List[Order] = []

        def _apply(order: Order, o, h, l, c, volume):
            nonlocal cash, position, maker_fills, taker_fills
            nonlocal total_fees, total_rebates
            dirn = 1.0 if order.side == "B" else -1.0
            if order.reduce_only and (position == 0 or math.copysign(1, position) == dirn):
                rejections["reduce_only_canceled"] += 1
                return
            equity = cash + position * c
            new_pos = position + dirn * order.sz
            if equity > 0 and abs(new_pos * c) > equity * cfg.max_leverage:
                rejections["capped"] += 1
                return
            if cfg.l2_provider is not None:
                queue = cfg.l2_provider(order.side, order.px)
                filled, fpx, maker, rej = bar_fill_l2(
                    order, o, h, l, c, oracle_px=c, schedule=sch,
                    queue_ahead=queue, bar_volume=volume)
            else:
                filled, fpx, maker, rej = bar_fill(order, o, h, l, c, oracle_px=c, schedule=sch)
            if rej:
                rejections[rej] += 1
                return
            if not filled:
                return
            notional = order.sz * fpx
            f = fee_for(notional, maker, sch)
            if f >= 0:
                total_fees += f
                cash -= f
            else:
                total_rebates += -f
                cash += -f
            if order.side == "B":
                cash -= notional
                position += order.sz
            else:
                cash += notional
                position -= order.sz
            if maker:
                maker_fills += 1
            else:
                taker_fills += 1

        for i in range(cfg.warmup, n):
            row = df.iloc[i]
            o, h, l, c = (float(row[k]) for k in ("open", "high", "low", "close"))
            last_close = c
            volume = float(row.get("volume", 0.0) or 0.0)
            # 1) fill orders decided at the previous bar against THIS bar
            for order in pending:
                _apply(order, o, h, l, c, volume)
            pending = []
            # 2) funding accrual on the current position
            if cfg.funding_interval_bars and (i % cfg.funding_interval_bars == 0) and position != 0:
                pay = position * c * cfg.funding_rate
                total_funding += pay
                cash -= pay
            # 3) mark equity, then ask the strategy for next bar's orders
            equity = cash + position * c
            if position != 0.0:
                bars_in_market += 1
            state = BarState(i=i, open=o, high=h, low=l, close=c, position=position,
                             entry_px=0.0, equity=equity, timestamp=df.index[i],
                             history=df.iloc[: i + 1])
            pending = strategy.act(state) or []
            equity_curve.append(equity)
        # orders decided on the final bar never execute (no next bar) — discarded.

        final_equity = cash + position * last_close
        total_trades = maker_fills + taker_fills
        maker_fraction = maker_fills / total_trades if total_trades else 0.0
        peak = -math.inf
        mdd = 0.0
        for e in equity_curve:
            peak = max(peak, e)
            if peak > 0:
                mdd = max(mdd, (peak - e) / peak)
        return DexBacktestResult(
            final_equity=final_equity,
            total_pnl=final_equity - cfg.initial_capital,
            total_fees=total_fees, total_rebates=total_rebates, total_funding=total_funding,
            total_trades=total_trades, maker_fills=maker_fills, taker_fills=taker_fills,
            maker_fraction=maker_fraction, n_bars=max(0, n - cfg.warmup),
            bars_in_market=bars_in_market,
            max_drawdown_pct=mdd, rejections=dict(rejections), equity_curve=equity_curve,
        )
