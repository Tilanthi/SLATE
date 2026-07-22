"""Tests for the honest vectorized backtester.

The whole point of this module: PROVE there is no lookahead and that the
attribution matches a dead-simple, obviously-correct reference loop. The
+3.43 regime-switch result came from `rets = pos * bar_ret` (crediting a bar's
own move to a signal decided at that bar's close). These tests encode that bug
as a permanent regression guard.
"""
import numpy as np
import pandas as pd
import pytest

from slate_core.backtest.honest import (
    backtest, CEX, DEX, bars_per_year_from_index, assert_causal,
)


def _df(closes, freq="1D"):
    idx = pd.date_range("2024-01-01", periods=len(closes), freq=freq)
    return pd.DataFrame({"open": closes, "high": closes, "low": closes,
                         "close": closes, "volume": [1.0] * len(closes)}, index=idx)


def _random_walk(n, seed=0, vol=0.02):
    rng = np.random.RandomState(seed)
    rets = rng.normal(0, vol, n)
    price = 100 * np.cumprod(1 + rets)
    return _df(price)


# --------------------------------------------------------------------------
# 1. THE regression: a signal decided from THIS bar's close must not earn
#    this bar's return. (This is exactly the +3.43 bug.)
# --------------------------------------------------------------------------
def test_lookahead_regression_contemporaneous_signal_has_no_edge():
    # The +3.43 bug: signal decided from THIS bar's close must NOT earn this
    # bar's return. Zero costs to isolate RETURN ATTRIBUTION (the lookahead
    # question) from legitimate turnover drag.
    df = _random_walk(4000, seed=1)
    close = df["close"].values
    target = np.sign(np.diff(close, prepend=close[0])).astype(int)
    res = backtest(target, df, venue=CEX, fee=0.0, slippage_bps=0.0)
    sh = res["metrics"]["sharpe"]
    # held[t]=target[t-1] is independent of bar_ret[t] on iid returns => Sharpe~N(0,ppy/n)
    # std≈0.30, so |sharpe|<1.0 is ~3.3 sigma robust. The BUGGY attribution would
    # give ~sqrt(365)=19 (sign(ret)*ret=|ret|>0 every bar) — so this still catches it hard.
    assert abs(sh) < 1.0, (
        f"Contemporaneous signal earned Sharpe {sh:.2f} with ZERO costs — "
        f"the engine is leaking the current bar's return (lookahead is back!)."
    )


def test_bug_demo_buggy_attribution_would_be_huge():
    """If we (deliberately) used the buggy attribution, the same contemporaneous
    signal earns ~sqrt(bars_per_year). Documents why the regression guard matters."""
    df = _random_walk(4000, seed=1)
    close = df["close"].values
    target = np.sign(np.diff(close, prepend=close[0])).astype(int)  # decided at bar's close
    bar_ret = np.zeros(len(close)); bar_ret[1:] = close[1:] / close[:-1] - 1
    buggy = target * bar_ret                                  # NO lag = the bug
    buggy_sharpe = buggy.mean() / buggy.std() * np.sqrt(365)
    assert buggy_sharpe > 10, f"buggy attribution only gave {buggy_sharpe:.1f}"


def test_perfect_foresight_signal_does_show_edge():
    """Sanity: if the SIGNAL genuinely knows the future, the engine MUST reflect
    it — proving the engine isn't artificially damping real edge."""
    df = _random_walk(2000, seed=2)
    close = df["close"].values
    fut = np.zeros(len(close), dtype=int)
    fut[:-1] = np.sign(close[1:] - close[:-1])  # peek one bar ahead
    res = backtest(fut, df, venue=CEX)
    assert res["metrics"]["sharpe"] > 5, (
        f"Perfect-foresight signal only got Sharpe {res['metrics']['sharpe']:.2f} "
        f"— engine should amplify a genuinely predictive signal."
    )


# --------------------------------------------------------------------------
# 2. Correctness vs an obviously-correct reference loop (no vectorization tricks)
# --------------------------------------------------------------------------
def _reference_loop(target, close, one_way, funding=None, settlements_per_bar=0.0):
    """Trivial O(n) reference: decide at close[t-1], hold over bar t."""
    n = len(close)
    held = np.zeros(n)
    held[1:] = target[:-1]
    net = np.zeros(n)
    for t in range(1, n):
        bar_ret = close[t] / close[t - 1] - 1.0
        gross = held[t] * bar_ret
        dhold = abs(held[t] - held[t - 1])
        cost = dhold * one_way
        fund = 0.0
        if funding is not None and settlements_per_bar > 0:
            fund = -funding[t] * settlements_per_bar * held[t]
        net[t] = gross - cost + fund
    return net


def test_matches_reference_loop_no_funding():
    df = _random_walk(500, seed=3)
    close = df["close"].values
    rng = np.random.RandomState(7)
    target = rng.choice([-1, 0, 1], size=len(close))
    one_way = CEX.taker_fee + CEX.slippage_bps / 1e4
    res = backtest(target, df, venue=CEX)
    ref = _reference_loop(target, close, one_way)
    np.testing.assert_allclose(res["returns"], ref, atol=1e-12)


def test_matches_reference_loop_with_funding():
    df = _random_walk(500, seed=4)
    close = df["close"].values
    rng = np.random.RandomState(8)
    target = rng.choice([-1, 1], size=len(close))
    funding = rng.normal(0.0001, 0.0001, len(close))  # ~0.01% per 8h, noisy
    df["funding"] = funding
    one_way = CEX.taker_fee + CEX.slippage_bps / 1e4
    res = backtest(target, df, venue=CEX)
    # daily bars => 3 funding settlements per bar (24h / 8h)
    ref = _reference_loop(target, close, one_way, funding=funding, settlements_per_bar=3.0)
    np.testing.assert_allclose(res["returns"], ref, atol=1e-12)


# --------------------------------------------------------------------------
# 3. Directional + cost sanity
# --------------------------------------------------------------------------
def test_short_profits_when_price_falls():
    closes = np.array([100, 90, 80], dtype=float)
    df = _df(closes)
    target = -np.ones(3, dtype=int)  # always short
    res = backtest(target, df, venue=CEX)
    assert res["metrics"]["total_ret"] > 0  # price fell 20%, short profits


def test_buyhold_turnover_and_cost():
    df = _random_walk(300, seed=5)
    target = np.ones(len(df), dtype=int)
    res = backtest(target, df, venue=CEX)
    # all-long target => entered once at bar1, still held at the end (no exit
    # inside the window) => turnover = 1.0 one-way unit, cost = 1 * one_way.
    assert abs(res["metrics"]["turnover"] - 1.0) < 1e-9
    one_way = CEX.taker_fee + CEX.slippage_bps / 1e4
    assert abs(res["metrics"]["total_cost"] - 1 * one_way) < 1e-9


def test_enter_then_exit_turnover_two():
    df = _random_walk(300, seed=5)
    target = np.ones(len(df), dtype=int)
    target[200:] = 0  # flatten at bar 200 => one entry + one exit
    res = backtest(target, df, venue=CEX)
    assert abs(res["metrics"]["turnover"] - 2.0) < 1e-9


# --------------------------------------------------------------------------
# 4. Funding sign
# --------------------------------------------------------------------------
def test_funding_long_pays_short_receives_when_positive():
    closes = np.array([100, 100, 100], dtype=float)  # flat price => no PnL
    df = _df(closes)
    df["funding"] = np.array([0.0, 0.001, 0.001])  # strongly positive funding
    long_res = backtest(np.ones(3, dtype=int), df, venue=CEX)
    short_res = backtest(-np.ones(3, dtype=int), df, venue=CEX)
    assert long_res["metrics"]["total_funding"] < 0   # long pays
    assert short_res["metrics"]["total_funding"] > 0  # short receives


# --------------------------------------------------------------------------
# 5. bars_per_year detection
# --------------------------------------------------------------------------
def test_bars_per_year_detection():
    assert bars_per_year_from_index(_df([1, 2, 3], "1D").index) == 365
    assert bars_per_year_from_index(_df([1, 2, 3], "1h").index) == 8760
    assert bars_per_year_from_index(_df([1, 2, 3], "4h").index) == 2190


# --------------------------------------------------------------------------
# 6. Causal guard: catches a signal that peeks into the future
# --------------------------------------------------------------------------
def test_causal_guard_passes_honest_signal():
    df = _random_walk(200, seed=9)

    def honest_sig(df, i):
        if i < 20:
            return 0
        return 1 if df["close"].iloc[i] > df["close"].iloc[i - 20] else -1

    assert assert_causal(honest_sig, df, i=100) is True


def test_causal_guard_catches_future_peeker():
    df = _random_walk(200, seed=10)

    def peeker(df, i):
        if i + 1 >= len(df):
            return 0
        return 1 if df["close"].iloc[i + 1] > df["close"].iloc[i] else -1  # future!

    assert assert_causal(peeker, df, i=100) is False


# --------------------------------------------------------------------------
# 7. Determinism
# --------------------------------------------------------------------------
def test_deterministic():
    df = _random_walk(400, seed=11)
    target = np.sign(np.diff(df["close"].values, prepend=1)).astype(int)
    r1 = backtest(target, df, venue=CEX)
    r2 = backtest(target, df, venue=CEX)
    assert r1["metrics"]["sharpe"] == r2["metrics"]["sharpe"]
