"""Tests for the daily-data loader (evolution/load_data.py)."""
import pandas as pd

from slate_core.discovery.evolution.load_data import (
    load_ohlcv, resample_to_daily, load_daily_data, is_intraday,
)


def _hourly_df():
    idx = pd.to_datetime(["2026-01-01 08:00", "2026-01-01 12:00", "2026-01-01 16:00",
                          "2026-01-02 08:00", "2026-01-02 12:00", "2026-01-02 16:00"])
    return pd.DataFrame(
        {"open": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
         "high": [1.5, 2.5, 3.5, 4.5, 5.5, 6.5],
         "low": [0.5, 1.5, 2.5, 3.5, 4.5, 5.5],
         "close": [1.2, 2.2, 3.2, 4.2, 5.2, 6.2],
         "volume": [10, 20, 30, 40, 50, 60]},
        index=idx,
    )


def test_resample_to_daily_collapses_bars():
    daily = resample_to_daily(_hourly_df())
    assert len(daily) == 2
    assert daily.index[0].date() == pd.Timestamp("2026-01-01").date()
    d1 = daily.iloc[0]
    assert d1["open"] == 1.0          # first
    assert d1["high"] == 3.5          # max of day
    assert d1["low"] == 0.5           # min of day
    assert d1["close"] == 3.2         # last
    assert d1["volume"] == 60         # sum


def test_is_intraday_detects_hourly():
    assert is_intraday(_hourly_df()) is True


def test_is_intraday_false_for_daily():
    daily = resample_to_daily(_hourly_df())
    assert is_intraday(daily) is False


def test_load_daily_data_real_yields_daily_index():
    df = load_daily_data("sol_data_cache/SOLUSDT_perpetual_1d_12m.csv")
    assert "close" in df.columns
    median_delta = df.index.to_series().diff().median()
    assert median_delta >= pd.Timedelta(days=1)    # daily, not hourly
    assert len(df) < 400                            # ~175 days, not 4182 hours
