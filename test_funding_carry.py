"""Tests for the funding-carry premium stream (slate_core.premium.funding_carry)."""
import numpy as np
import pandas as pd

from slate_core.premium.funding_carry import funding_carry_signal, backtest_funding_carry


def _synth_df(n=200, seed=0):
    """Synthetic OHLCV + funding DataFrame with a proper datetime index."""
    rng = np.random.RandomState(seed)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    idx = pd.date_range("2026-01-01", periods=n, freq="1h")
    return pd.DataFrame({
        "open": close, "high": close * 1.005, "low": close * 0.995,
        "close": close, "volume": rng.uniform(100, 1000, n),
        "funding": rng.uniform(-0.0002, 0.0003, n),
    }, index=idx)


def test_funding_carry_signal_returns_short_or_flat():
    fn = funding_carry_signal(0.0001)
    df = _synth_df()
    assert fn(df, 0, {}) in (-1, 0)


def test_backtest_funding_carry_returns_equity_curve():
    df = _synth_df(n=200)
    result = backtest_funding_carry(df, coin="TEST", threshold_pct=0.0001, timeframe="1h")
    assert "equity_curve" in result
    assert len(result["equity_curve"]) > 0
    assert "returns" in result
    assert "metrics" in result
    assert "sharpe" in result["metrics"]


def test_backtest_funding_carry_handles_no_funding_column():
    df = _synth_df(n=200)
    df = df.drop(columns=["funding"])
    result = backtest_funding_carry(df, coin="NOFUND", threshold_pct=0.0001)
    assert len(result["equity_curve"]) > 0   # ran flat, didn't crash
