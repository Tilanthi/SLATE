"""Tests for the portfolio backtester (slate_core.portfolio.portfolio_backtester)."""
import numpy as np

from slate_core.portfolio.portfolio_backtester import PortfolioBacktester


def _uncorrelated_streams(n=200, seed=0):
    rng = np.random.RandomState(seed)
    return {
        "carry_SOL": rng.normal(0.001, 0.02, n),
        "carry_BTC": rng.normal(0.0008, 0.015, n),
        "carry_ETH": rng.normal(0.0012, 0.025, n),
    }


def _correlated_streams(n=200, seed=0):
    rng = np.random.RandomState(seed)
    base = rng.normal(0.001, 0.02, n)
    return {"a": base, "b": base + rng.normal(0, 0.002, n)}


def test_combine_produces_metrics():
    bt = PortfolioBacktester()
    streams = _uncorrelated_streams()
    result = bt.combine(streams, {"carry_SOL": 0.33, "carry_BTC": 0.33, "carry_ETH": 0.34})
    assert "returns" in result
    assert len(result["returns"]) == 200
    assert "sharpe" in result["metrics"]
    assert result["diversification_ratio"] > 1.0   # diversified


def test_correlation_report_detects_redundancy():
    bt = PortfolioBacktester()
    streams = _correlated_streams()
    report = bt.correlation_report(streams)
    assert report["max_correlation"] > 0.7
    assert len(report["redundant_pairs"]) >= 1


def test_walk_forward_returns_per_fold():
    bt = PortfolioBacktester()
    streams = _uncorrelated_streams(n=500)
    weights = {k: 1.0 / len(streams) for k in streams}
    wf = bt.walk_forward_validate(streams, weights, n_folds=5)
    assert len(wf["folds"]) == 5
    assert "aggregate" in wf


def test_monte_carlo_returns_dd_distribution():
    bt = PortfolioBacktester()
    rets = np.random.RandomState(0).normal(0.001, 0.02, 200)
    mc = bt.monte_carlo(rets, n_sims=200)
    assert mc["p95_dd"] > mc["p50_dd"]   # tail is worse
    assert mc["max_dd"] >= mc["p95_dd"]
