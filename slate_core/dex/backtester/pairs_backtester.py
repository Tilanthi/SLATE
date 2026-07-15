"""Pairs (stat-arb) backtester: a $-neutral 2-leg spread trade — long asset A /
short asset B (or the reverse), mean-reverting their spread. This is the multi-leg
edge class that single-asset backtests cannot express. Lookahead-safe (the position
decided at bar i takes effect at bar i+1).

A spread position of +1 = long $`notional` of A and short $`notional` of B; its
per-bar mark-to-market PnL is notional * (rA - rB). Entries/exits pay taker fees on
both legs. Market-neutral, so there is no buy-and-hold benchmark — PnL is absolute.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

from slate_core.dex.backtester.economics import HLFeeSchedule

SpreadFn = Callable[..., int]


@dataclass
class PairsBacktestConfig:
    notional: float = 1000.0            # USDC per leg ($-neutral)
    fee_schedule: HLFeeSchedule = field(default_factory=HLFeeSchedule)
    warmup: int = 50


@dataclass
class PairsBacktestResult:
    total_pnl: float
    total_fees: float
    total_trades: int
    n_bars: int
    bars_in_market: int
    max_drawdown_pct: float
    equity_curve: List[float]

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if k != "equity_curve"}


class PairsBacktester:
    def __init__(self, config: PairsBacktestConfig = None):
        self.config = config or PairsBacktestConfig()

    def backtest(self, spread_signal: SpreadFn, dfA, dfB) -> PairsBacktestResult:
        cfg = self.config
        sch = cfg.fee_schedule
        cash = 0.0                 # running mark-to-market PnL (USDC)
        position = 0               # -1 / 0 / +1  (+1 = long A / short B)
        pending = 0
        equity_curve: List[float] = []
        fees = 0.0
        trades = 0
        bars_in = 0
        n = min(len(dfA), len(dfB))
        cA = dfA["close"].astype(float).values
        cB = dfB["close"].astype(float).values

        for i in range(cfg.warmup, n):
            # spread return of a +1 position over bar i (long A / short B)
            if cA[i - 1] > 0 and cB[i - 1] > 0:
                spread_ret = (cA[i] / cA[i - 1] - 1.0) - (cB[i] / cB[i - 1] - 1.0)
            else:
                spread_ret = 0.0
            # execute the position change decided last bar (taker, both legs)
            if pending != position:
                change = abs(pending - position)
                fees += change * 2.0 * cfg.notional * sch.taker
                cash -= change * 2.0 * cfg.notional * sch.taker
                position = pending
                trades += 1
            # accrue MTM PnL from holding the spread
            if position != 0:
                cash += cfg.notional * position * spread_ret
                bars_in += 1
            # decide next position from past-only info
            try:
                sig = spread_signal(dfA, dfB, i)
            except Exception:  # noqa: BLE001
                sig = 0
            pending = sig if sig in (-1, 0, 1) else 0
            equity_curve.append(cash)

        peak = -math.inf
        mdd = 0.0
        for e in equity_curve:
            peak = max(peak, e)
            if peak > 0:
                mdd = max(mdd, (peak - e) / peak)
        return PairsBacktestResult(
            total_pnl=cash, total_fees=fees, total_trades=trades,
            n_bars=max(0, n - cfg.warmup), bars_in_market=bars_in,
            max_drawdown_pct=mdd, equity_curve=equity_curve)
