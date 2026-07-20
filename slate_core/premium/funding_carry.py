"""Funding-carry premium stream: short perpetuals when funding is expensive.

A risk-premium strategy that collects funding payments from overleveraged longs.
When funding > threshold, go short (collect funding); otherwise flat. This is
COMPENSATION for bearing basis/squeeze risk — not a free lunch. The stream
produces an equity curve + returns for portfolio aggregation.

Includes regime-aware variant (skip carry in strong uptrends where shorts get
run over) and a funding-reversal variant (fade extreme funding = crowded
positioning).
"""
from __future__ import annotations

from typing import Callable, Dict

import numpy as np
import pandas as pd

from slate_core.discovery.perpetual_futures_backtest import (
    PerpetualBacktestConfig, PerpetualFuturesBacktester,
)
from slate_core.statistics.equity_curve import equity_to_returns, portfolio_metrics


# ---- signal factories ----

def funding_carry_signal(threshold_pct: float = 0.0):
    """Short when funding > threshold (default 0 = short whenever funding positive)."""

    def signal_fn(df, i, params):
        funding = df["funding"].iloc[i] if "funding" in df.columns else 0.0
        return -1 if funding > threshold_pct else 0

    return signal_fn


def funding_carry_regime_signal(uptrend_threshold: float = 0.03, lookback: int = 24):
    """Regime-aware carry: short when funding > 0 AND price NOT in a strong uptrend.

    Avoids the biggest carry losses (shorting into a rally) by checking if the
    close is > lookback-MA × (1+threshold). In a bull run → flat; in sideways/down
    → collect carry. This is the variant that should improve on the unconditional
    carry which lost money in the Dec 2025 – Jul 2026 bull period.
    """

    def signal_fn(df, i, params):
        funding = df["funding"].iloc[i] if "funding" in df.columns else 0.0
        if funding <= 0:
            return 0
        if i >= lookback:
            ma = float(df["close"].iloc[max(0, i - lookback):i + 1].mean())
            close = float(df["close"].iloc[i])
            if close > ma * (1.0 + uptrend_threshold):
                return 0    # strong uptrend → skip (avoid getting run over)
        return -1           # sideways/down → short (collect carry)

    return signal_fn


def funding_reversal_signal(extreme_pct: float = 0.90, lookback: int = 100):
    """Fade extreme funding: short when funding is in the top percentile (crowded
    longs → mean-revert), long when in the bottom percentile (crowded shorts →
    squeeze). A different premium from carry — this is a funding mean-reversion."""

    def signal_fn(df, i, params):
        if "funding" not in df.columns or i < lookback:
            return 0
        funding = float(df["funding"].iloc[i])
        recent = df["funding"].iloc[max(0, i - lookback):i + 1]
        p_high = float(recent.quantile(extreme_pct))
        p_low = float(recent.quantile(1.0 - extreme_pct))
        if funding > p_high:
            return -1    # extreme positive funding → short (crowded longs unwind)
        if funding < p_low:
            return 1     # extreme negative funding → long (short squeeze)
        return 0

    return signal_fn


# ---- generic backtest wrapper ----

def backtest_premium_stream(df: pd.DataFrame, coin: str, signal_fn: Callable,
                            strategy_name: str = "premium",
                            initial_capital: float = 10_000.0,
                            timeframe: str = "1h") -> Dict:
    """Run the bar backtester with any signal_fn → equity curve + returns + metrics."""
    if "funding" not in df.columns:
        df = df.copy()
        df["funding"] = 0.0

    config = PerpetualBacktestConfig(initial_capital=initial_capital, timeframe=timeframe)
    backtester = PerpetualFuturesBacktester(config)
    result = backtester.backtest_strategy(
        df=df, strategy_name=f"{strategy_name}_{coin}",
        strategy_description=strategy_name, edge_type=strategy_name,
        signal_function=signal_fn, parameters={},
    )
    curve = list(result.equity_curve) if result.equity_curve else [initial_capital]
    returns = equity_to_returns(curve)
    ppy = 8760 if timeframe == "1h" else 365
    metrics = portfolio_metrics(returns, periods_per_year=ppy)
    return {
        "coin": coin, "strategy": strategy_name,
        "equity_curve": curve, "returns": returns, "metrics": metrics,
        "total_pnl": result.total_profit_usdt,
        "net_funding": result.net_funding_usdt,
        "max_drawdown_pct": result.max_drawdown_pct,
        "total_trades": result.total_trades,
    }


# ---- convenience wrappers ----

def backtest_funding_carry(df, coin="SOL", threshold_pct=0.0, **kw):
    return backtest_premium_stream(df, coin, funding_carry_signal(threshold_pct),
                                   "funding_carry", **kw)


def backtest_funding_carry_regime(df, coin="SOL", uptrend_threshold=0.03,
                                  lookback=24, **kw):
    return backtest_premium_stream(
        df, coin, funding_carry_regime_signal(uptrend_threshold, lookback),
        "carry_regime", **kw)


def backtest_funding_reversal(df, coin="SOL", extreme_pct=0.90, lookback=100, **kw):
    return backtest_premium_stream(
        df, coin, funding_reversal_signal(extreme_pct, lookback),
        "funding_reversal", **kw)


def backtest_all_premiums(df, coin="SOL", **kw) -> Dict[str, Dict]:
    """Run all premium variants for a coin → {variant_name: result}."""
    return {
        "carry": backtest_funding_carry(df, coin=coin, **kw),
        "carry_regime": backtest_funding_carry_regime(df, coin=coin, **kw),
        "reversal": backtest_funding_reversal(df, coin=coin, **kw),
    }


__all__ = [
    "funding_carry_signal", "funding_carry_regime_signal", "funding_reversal_signal",
    "backtest_premium_stream",
    "backtest_funding_carry", "backtest_funding_carry_regime",
    "backtest_funding_reversal", "backtest_all_premiums",
    "backtest_funding_carry_multi",
]
