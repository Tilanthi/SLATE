"""Tests for equity-curve utilities (slate_core.statistics.equity_curve)."""
import numpy as np
from slate_core.statistics.equity_curve import (
    equity_to_returns, max_drawdown, portfolio_metrics, correlation_matrix,
    diversification_ratio,
)


def test_equity_to_returns_basic():
    curve = [100.0, 101.0, 102.0, 101.0, 103.0]
    rets = equity_to_returns(curve)
    assert len(rets) == 4
    assert abs(rets[0] - 0.01) < 1e-9    # +1%
    assert abs(rets[2] + 1.0/102.0) < 1e-6  # drop


def test_equity_to_returns_empty():
    assert len(equity_to_returns([])) == 0
    assert len(equity_to_returns([100.0])) == 0


def test_max_drawdown():
    # peak 100, trough 80 → 20% DD
    rets = np.array([0.0, -0.2, 0.0])
    assert abs(max_drawdown(rets) - 0.2) < 1e-6


def test_portfolio_metrics_keys():
    rets = np.random.RandomState(0).normal(0.001, 0.02, 100)
    m = portfolio_metrics(rets)
    for k in ("sharpe", "sortino", "max_drawdown", "calmar",
              "annualized_return", "annualized_vol"):
        assert k in m


def test_correlation_matrix():
    rng = np.random.RandomState(1)
    a = rng.normal(0, 0.01, 50)
    b = a + rng.normal(0, 0.005, 50)   # correlated
    c = rng.normal(0, 0.01, 50)        # uncorrelated
    corr = correlation_matrix({"a": a, "b": b, "c": c})
    assert corr.loc["a", "b"] > 0.5     # correlated
    assert abs(corr.loc["a", "c"]) < 0.5  # uncorrelated


def test_diversification_ratio_greater_than_one():
    rng = np.random.RandomState(2)
    # two uncorrelated positive-EV streams → diversification > 1
    streams = {"x": rng.normal(0.001, 0.02, 200), "y": rng.normal(0.001, 0.02, 200)}
    dr = diversification_ratio(streams, {"x": 0.5, "y": 0.5})
    assert dr > 1.0
