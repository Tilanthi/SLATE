"""Regression tests for backtester correctness fixes (2026-07-11).

Covers three force-multiplier fixes in perpetual_futures_backtest.py:
  Fix 1 - lookahead closure (signal must not see future bars)
  Fix 2 - timeframe-aware funding accrual + Sharpe annualization
  Fix 3 - deterministic RNG (reproducible backtests)

These use small SYNTHETIC fixtures (controlled inputs for unit testing) - they
make no claim about real market edge; they pin backtester *mechanics*.
"""
import numpy as np
import pandas as pd
from datetime import datetime

from slate_core.discovery.perpetual_futures_backtest import (
    PerpetualFuturesBacktester,
)


def _make_df(n: int, hours_per_bar: int = 24) -> pd.DataFrame:
    """Deterministic OHLCV frame on a DatetimeIndex at the given bar frequency."""
    rng = np.random.default_rng(0)
    idx = pd.date_range(datetime(2026, 1, 1), periods=n, freq=f"{hours_per_bar}h")
    price = 100.0
    closes = []
    for _ in range(n):
        price *= (1 + rng.normal(0, 0.02))
        closes.append(float(price))
    closes = np.array(closes)
    return pd.DataFrame(
        {
            "open": closes,
            "high": closes * 1.01,
            "low": closes * 0.99,
            "close": closes,
            "volume": np.full(n, 1000.0),
            "atr": closes * 0.02,
        },
        index=idx,
    )


# --------------------------------------------------------------------------- #
# Fix 1: lookahead closure
# --------------------------------------------------------------------------- #
def test_signal_cannot_see_future_bars():
    """A signal must only receive bars up to and including the current bar."""
    calls = []
    saw_future = []

    def peeking_signal(df, i, params):
        calls.append(i)
        # If the backtester passes the full frame, bar i+1 (tomorrow) is visible.
        saw_future.append(i + 1 < len(df))
        return 0

    df = _make_df(100)
    bt = PerpetualFuturesBacktester()
    bt.backtest_strategy(df, "peek", "lookahead test", "momentum", peeking_signal, {})

    assert len(calls) > 0, "signal was never called"
    assert not any(saw_future), (
        f"signal could see future bars at {sum(saw_future)} of {len(saw_future)} bars "
        "- lookahead hole is open"
    )


# --------------------------------------------------------------------------- #
# Fix 3: deterministic RNG
# --------------------------------------------------------------------------- #
def test_backtest_is_deterministic_across_runs():
    """Same inputs must yield identical results (fills/slippage/funding are seeded)."""

    def mom_signal(df, i, params):
        if i < 1:
            return 0
        return 1 if df["close"].iloc[i] > df["close"].iloc[i - 1] else -1

    df = _make_df(120)
    bt = PerpetualFuturesBacktester()
    r1 = bt.backtest_strategy(df, "t", "d", "momentum", mom_signal, {})
    r2 = bt.backtest_strategy(df, "t", "d", "momentum", mom_signal, {})

    assert r1.total_profit_usdt == r2.total_profit_usdt, (
        f"non-deterministic profit: {r1.total_profit_usdt} vs {r2.total_profit_usdt}"
    )
    assert r1.total_trades == r2.total_trades, "non-deterministic trade count"
    assert r1.sharpe_ratio == r2.sharpe_ratio, "non-deterministic sharpe"


# --------------------------------------------------------------------------- #
# Fix 2: timeframe-aware funding + Sharpe
# --------------------------------------------------------------------------- #
def test_funding_accrues_by_bar_frequency_not_hardcoded_24h():
    """Hourly bars must accrue ~1h of funding each, not a hardcoded 24h.

    With the bug, hourly and daily data both add 24h/bar -> similar funding
    magnitude. Fixed, hourly accrues 1h/bar -> far less total funding.
    """

    def always_long(df, i, params):
        return 1

    bt = PerpetualFuturesBacktester()
    daily = bt.backtest_strategy(_make_df(60, hours_per_bar=24), "t", "d", "momentum", always_long, {})
    hourly = bt.backtest_strategy(_make_df(60, hours_per_bar=1), "t", "d", "momentum", always_long, {})

    assert daily.net_funding_usdt != 0, "daily funding never accrued - test fixture broken"
    # Hourly funding (1h/bar, ~7 events) must be materially less than daily
    # (24h/bar, ~60 events). Buggy code makes them roughly equal.
    assert abs(hourly.net_funding_usdt) < abs(daily.net_funding_usdt) * 0.5, (
        f"hourly funding {hourly.net_funding_usdt} not scaled down from daily "
        f"{daily.net_funding_usdt} - timeframe not detected"
    )


def test_sharpe_annualization_scales_with_bar_frequency():
    """Annualization factor must reflect bar frequency, not be fixed at sqrt(252)."""

    def always_long(df, i, params):
        return 1

    bt = PerpetualFuturesBacktester()
    # Expose detected annualization if present (added by fix), else infer from result.
    daily = bt.backtest_strategy(_make_df(120, hours_per_bar=24), "t", "d", "momentum", always_long, {})
    hourly = bt.backtest_strategy(_make_df(120, hours_per_bar=1), "t", "d", "momentum", always_long, {})

    # The backtester should report its detected bars-per-year.
    bpy_hourly = getattr(hourly, "bars_per_year", None)
    bpy_daily = getattr(daily, "bars_per_year", None)
    assert bpy_hourly is not None and bpy_daily is not None, (
        "backtester did not expose bars_per_year on the result"
    )
    assert bpy_hourly > bpy_daily * 5, (
        f"hourly bars_per_year ({bpy_hourly}) should be ~24x daily ({bpy_daily})"
    )


# --------------------------------------------------------------------------- #
# Fix 2b: closed-loop must backtest DAILY bars (the source file is hourly)
# --------------------------------------------------------------------------- #
def test_closed_loop_market_data_is_daily():
    """The closed-loop loads via load_daily_data; it must yield daily bars, not
    the 4,182 hourly bars in the source file."""
    from slate_core.discovery.evolution.load_data import load_daily_data, is_intraday

    df = load_daily_data("sol_data_cache/SOLUSDT_perpetual_1d_12m.csv")
    assert not is_intraday(df), "data is still intraday after load_daily_data"
    assert 100 < len(df) < 400, f"expected ~175 daily bars, got {len(df)}"


def test_regime_filter_does_not_starve_small_daily_dataset():
    """Fix #2: the regime filter must not cut a small daily dataset below a
    viable backtest size (it was cutting 175 -> 47 bars -> 0 trades)."""
    from slate_core.discovery.market_regime_filter import (
        get_market_regime_filter, MIN_BARS_FOR_DISCOVERY,
    )
    from slate_core.discovery.evolution.load_data import load_daily_data

    df = load_daily_data("sol_data_cache/SOLUSDT_perpetual_1d_12m.csv")
    rf = get_market_regime_filter()
    filtered = rf.filter_for_discovery(df, strategy_type="adaptive_regime_switching")
    assert len(filtered) >= MIN_BARS_FOR_DISCOVERY, (
        f"regime filter left {len(filtered)} bars (< {MIN_BARS_FOR_DISCOVERY} floor) "
        "-> strategies will starve"
    )


# --------------------------------------------------------------------------- #
# Fix 4: carry PerpetualBacktestResult fields through to the DB
# --------------------------------------------------------------------------- #
def test_convert_backtest_to_dict_carries_all_db_fields():
    """The dict fed to the DB must carry real buy-hold, funding, prices, per-trade
    stats, and a USDT drawdown - not the 22 fields that defaulted to 0."""
    from slate_core.discovery.closed_loop_discovery import ClosedLoopDiscoveryEngine

    df = _make_df(120)

    def trade_signal(df, i, params):
        if i < 1:
            return 0
        return 1 if df["close"].iloc[i] > df["close"].iloc[i - 1] else -1

    bt = PerpetualFuturesBacktester()
    result = bt.backtest_strategy(df, "t", "d", "momentum", trade_signal, {})

    d = ClosedLoopDiscoveryEngine.convert_backtest_to_dict(result)

    # Canonical fields must mirror the real backtest object (not default to 0)
    assert d["buy_hold_profit_usdt"] == result.buy_hold_profit_usdt, "buy_hold lost"
    assert d["vs_buy_hold_usdt"] == result.vs_buy_hold_usdt, "vs_buy_hold lost"
    assert d["beat_market"] == result.beat_market, "beat_market lost"
    assert d["net_funding_usdt"] == result.net_funding_usdt, "net_funding lost"
    assert d["start_price"] == result.start_price, "start_price lost"
    assert d["end_price"] == result.end_price, "end_price lost"
    assert d["max_drawdown_usdt"] == result.max_drawdown_usdt, "max_drawdown_usdt lost"
    # USDT drawdown must be distinct from the validation ratio of the same name
    assert d["max_drawdown_usdt"] != d["max_drawdown"], "USDT drawdown == ratio"
    assert d["period_start"] == result.period_start, "period_start lost"
    assert d["total_profit"] == result.total_profit_usdt, "validation alias broken"
