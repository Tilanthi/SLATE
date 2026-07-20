"""Equity-curve → returns → portfolio-metrics utilities.

Shared helpers for converting an equity curve into a return series and computing
standard risk/return metrics (Sharpe, Sortino, max drawdown, Calmar). Used by
the premium streams, the portfolio backtester, and the risk layer.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, Sequence


def equity_to_returns(curve: Sequence[float]) -> np.ndarray:
    """Convert an equity curve to period returns (r_t = curve_t / curve_{t-1} - 1)."""
    c = np.asarray(curve, dtype=float)
    if len(c) < 2:
        return np.array([])
    prev = c[:-1]
    prev = np.where(prev == 0, np.nan, prev)
    rets = c[1:] / prev - 1.0
    return rets[np.isfinite(rets)]


def max_drawdown(returns: np.ndarray) -> float:
    """Max drawdown fraction from a return series."""
    if len(returns) == 0:
        return 0.0
    equity = np.cumprod(1.0 + np.nan_to_num(returns))
    running = np.maximum.accumulate(equity)
    dd = (equity - running) / running
    return float(np.min(dd)) * -1.0   # positive number


def portfolio_metrics(returns: np.ndarray, periods_per_year: int = 365) -> Dict[str, float]:
    """Standard risk/return metrics from a period-return series."""
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < 2:
        return {"sharpe": 0.0, "sortino": 0.0, "max_drawdown": 0.0,
                "calmar": 0.0, "annualized_return": 0.0, "annualized_vol": 0.0,
                "n_periods": len(r)}
    mean = float(np.mean(r))
    vol = float(np.std(r, ddof=1))
    downside = r[r < 0]
    downside_vol = float(np.std(downside, ddof=1)) if len(downside) > 1 else 0.0
    mdd = max_drawdown(r)
    ann_ret = mean * periods_per_year
    ann_vol = vol * np.sqrt(periods_per_year)
    sharpe = (ann_ret) / ann_vol if ann_vol > 0 else 0.0
    sortino = (ann_ret) / (downside_vol * np.sqrt(periods_per_year)) if downside_vol > 0 else 0.0
    calmar = ann_ret / mdd if mdd > 0 else 0.0
    return {
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": mdd,
        "calmar": calmar,
        "annualized_return": ann_ret,
        "annualized_vol": ann_vol,
        "n_periods": len(r),
    }


def correlation_matrix(stream_returns: Dict[str, np.ndarray]) -> pd.DataFrame:
    """Correlation matrix across premium-stream return series (aligned by index)."""
    if not stream_returns:
        return pd.DataFrame()
    min_len = min(len(v) for v in stream_returns.values())
    if min_len == 0:
        return pd.DataFrame()
    aligned = {k: np.asarray(v[:min_len]) for k, v in stream_returns.items()}
    df = pd.DataFrame(aligned)
    return df.corr()


def diversification_ratio(stream_returns: Dict[str, np.ndarray],
                          weights: Dict[str, float]) -> float:
    """Diversification ratio = weighted-avg vol / portfolio vol (>1 = diversified)."""
    if not stream_returns or not weights:
        return 1.0
    min_len = min(len(v) for v in stream_returns.values())
    rets = {k: np.asarray(v[:min_len]) for k, v in stream_returns.items()}
    w = np.array([weights.get(k, 0.0) for k in rets])
    w = w / w.sum() if w.sum() > 0 else w
    vols = np.array([np.std(rets[k]) for k in rets])
    wavg_vol = float(np.sum(w * vols))
    port_ret = np.zeros(min_len)
    for i, k in enumerate(rets):
        port_ret += w[i] * rets[k]
    port_vol = float(np.std(port_ret))
    return wavg_vol / port_vol if port_vol > 0 else 1.0


__all__ = ["equity_to_returns", "max_drawdown", "portfolio_metrics",
           "correlation_matrix", "diversification_ratio"]
