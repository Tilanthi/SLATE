"""Portfolio backtester: combine multiple premium-stream return series.

Takes N independent premium-stream return series (funding carry on different
coins, basis, yield) + target weights, produces the COMBINED portfolio return
stream + equity curve + risk/return metrics. This is the tool that validates
diversification: the whole should have a better Sharpe than any part, and the
inter-stream correlation report catches fake diversification.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from slate_core.statistics.equity_curve import (
    correlation_matrix, diversification_ratio, equity_to_returns, max_drawdown,
    portfolio_metrics,
)


class PortfolioBacktester:
    """Combine N premium streams into a portfolio and measure its risk/return."""

    def __init__(self, periods_per_year: int = 365):
        self.ppy = periods_per_year

    def combine(self, stream_returns: Dict[str, np.ndarray],
                weights: Dict[str, float]) -> Dict:
        """Weighted combination of return streams → portfolio returns + metrics."""
        if not stream_returns:
            return {"returns": np.array([]), "equity_curve": [],
                    "metrics": {}, "diversification_ratio": 1.0}
        min_len = min(len(v) for v in stream_returns.values())
        names = list(stream_returns.keys())
        aligned = {k: np.asarray(v[:min_len]) for k, v in stream_returns.items()}
        w = np.array([weights.get(k, 0.0) for k in names], dtype=float)
        total_w = w.sum()
        if total_w > 0:
            w = w / total_w
        port_ret = np.zeros(min_len)
        for i, k in enumerate(names):
            port_ret += w[i] * aligned[k]
        equity = self._returns_to_equity(port_ret)
        m = portfolio_metrics(port_ret, periods_per_year=self.ppy)
        dr = diversification_ratio(aligned, {k: weights.get(k, 0) for k in names})
        return {
            "returns": port_ret,
            "equity_curve": equity.tolist(),
            "metrics": m,
            "diversification_ratio": dr,
            "weights": {k: float(w[i]) for i, k in enumerate(names)},
        }

    def walk_forward_validate(self, stream_returns: Dict[str, np.ndarray],
                              weights: Dict[str, float],
                              n_folds: int = 5) -> Dict:
        """Walk-forward: split into n_folds, evaluate combined portfolio per fold."""
        if not stream_returns:
            return {"folds": [], "aggregate": {}}
        min_len = min(len(v) for v in stream_returns.values())
        fold_size = min_len // n_folds
        if fold_size < 10:
            return {"folds": [], "aggregate": {"error": "too few bars per fold"}}
        folds = []
        all_rets = []
        for f in range(n_folds):
            start = f * fold_size
            end = start + fold_size if f < n_folds - 1 else min_len
            fold_streams = {k: v[start:end] for k, v in stream_returns.items()}
            result = self.combine(fold_streams, weights)
            folds.append({
                "fold": f,
                "sharpe": result["metrics"].get("sharpe", 0),
                "max_drawdown": result["metrics"].get("max_drawdown", 0),
                "annualized_return": result["metrics"].get("annualized_return", 0),
            })
            all_rets.extend(result["returns"].tolist())
        agg = portfolio_metrics(np.array(all_rets), periods_per_year=self.ppy)
        return {"folds": folds, "aggregate": agg}

    def monte_carlo(self, returns: np.ndarray, n_sims: int = 1000,
                    seed: int = 42) -> Dict:
        """Bootstrap-resample the return series, report drawdown distribution."""
        if len(returns) < 10:
            return {"p50_dd": 0, "p95_dd": 0, "max_dd": 0}
        rng = np.random.RandomState(seed)
        n = len(returns)
        dds = []
        for _ in range(n_sims):
            sample = rng.choice(returns, size=n, replace=True)
            dds.append(max_drawdown(sample))
        dds = np.array(dds)
        return {
            "p50_dd": float(np.percentile(dds, 50)),
            "p95_dd": float(np.percentile(dds, 95)),
            "max_dd": float(np.max(dds)),
            "mean_dd": float(np.mean(dds)),
        }

    def correlation_report(self, stream_returns: Dict[str, np.ndarray]) -> Dict:
        """Inter-stream correlation + diversification assessment."""
        corr = correlation_matrix(stream_returns)
        if corr.empty:
            return {"correlation_matrix": {}, "max_correlation": 0.0,
                    "redundant_pairs": []}
        max_corr = 0.0
        redundant = []
        names = list(corr.columns)
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                c = float(corr.iloc[i, j])
                if abs(c) > max_corr:
                    max_corr = abs(c)
                if abs(c) > 0.7:
                    redundant.append({"pair": (names[i], names[j]), "corr": c})
        return {
            "correlation_matrix": corr.to_dict(),
            "max_correlation": max_corr,
            "redundant_pairs": redundant,
        }

    @staticmethod
    def _returns_to_equity(returns: np.ndarray, start: float = 1.0) -> np.ndarray:
        return start * np.cumprod(1.0 + np.nan_to_num(returns))


__all__ = ["PortfolioBacktester"]
