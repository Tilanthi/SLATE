"""Funding-carry premium stream: short perpetuals when funding is expensive.

A risk-premium strategy that collects funding payments from overleveraged longs.
When funding > threshold, go short (collect funding); otherwise flat. This is
COMPENSATION for bearing basis/squeeze risk — not a free lunch. The stream
produces an equity curve + returns for portfolio aggregation.
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from slate_core.discovery.perpetual_futures_backtest import (
    PerpetualBacktestConfig, PerpetualFuturesBacktester,
)
from slate_core.statistics.equity_curve import equity_to_returns, portfolio_metrics


def funding_carry_signal(threshold_pct: float = 0.0001):
    """Build signal_fn(df, i, params) -> {-1, 0, 1}: short when funding > threshold."""

    def signal_fn(df, i, params):
        funding = df["funding"].iloc[i] if "funding" in df.columns else 0.0
        return -1 if funding > threshold_pct else 0

    return signal_fn


def backtest_funding_carry(df: pd.DataFrame, coin: str = "SOL",
                           threshold_pct: float = 0.0001,
                           initial_capital: float = 10_000.0,
                           timeframe: str = "1h") -> Dict:
    """Backtest a single funding-carry premium stream.

    Args:
        df: OHLCV DataFrame with a 'funding' column (merge via load_data.merge_funding).
        coin: symbol label.
        threshold_pct: funding rate above which to short (0.0001 = 0.01%).
        initial_capital: starting capital for the backtest.
        timeframe: bar timeframe (determines annualization).

    Returns:
        {coin, equity_curve, returns, metrics, total_pnl, net_funding, ...}
    """
    if "funding" not in df.columns:
        df = df.copy()
        df["funding"] = 0.0   # no funding → flat (zero premium)

    config = PerpetualBacktestConfig(
        initial_capital=initial_capital,
        timeframe=timeframe,
    )
    backtester = PerpetualFuturesBacktester(config)
    signal_fn = funding_carry_signal(threshold_pct)

    result = backtester.backtest_strategy(
        df=df,
        strategy_name=f"funding_carry_{coin}",
        strategy_description=f"Short {coin} perp when funding > {threshold_pct}",
        edge_type="funding_carry",
        signal_function=signal_fn,
        parameters={"threshold_pct": threshold_pct},
    )

    curve = list(result.equity_curve) if result.equity_curve else [initial_capital]
    returns = equity_to_returns(curve)
    ppy = 8760 if timeframe == "1h" else 365
    metrics = portfolio_metrics(returns, periods_per_year=ppy)

    return {
        "coin": coin,
        "equity_curve": curve,
        "returns": returns,
        "metrics": metrics,
        "total_pnl": result.total_profit_usdt,
        "net_funding": result.net_funding_usdt,
        "max_drawdown_pct": result.max_drawdown_pct,
        "total_trades": result.total_trades,
    }


def backtest_funding_carry_multi(dfs: Dict[str, pd.DataFrame],
                                 threshold_pct: float = 0.0001,
                                 **kwargs) -> Dict[str, Dict]:
    """Backtest funding-carry for multiple coins → dict of per-coin results."""
    return {
        coin: backtest_funding_carry(df, coin=coin, threshold_pct=threshold_pct, **kwargs)
        for coin, df in dfs.items()
    }


__all__ = ["funding_carry_signal", "backtest_funding_carry", "backtest_funding_carry_multi"]
