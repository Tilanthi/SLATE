"""Tests for the multi-stream historical fetcher (Phase 1a, Tasks 2 & 3).

Parsing/daily-aggregation is tested against committed REAL Binance fixtures
(no live network, no synthetic values). The network fetch functions are
exercised via the live smoke step in the plan, not here.
"""
import json

import pandas as pd

from slate_core.data.multi_stream_fetcher import (
    aggregate_funding_daily,
    aggregate_ohlcv_daily,
)


# --------------------------------------------------------------------------- #
# Task 2: funding-rate history
# --------------------------------------------------------------------------- #
def test_funding_daily_is_mean_of_events_no_lookforward():
    rows = json.load(open("tests/fixtures/regime/funding_SOLUSDT.json"))
    assert len(rows) > 0, "fixture missing - fetch it per the plan"

    df = aggregate_funding_daily(rows)

    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.name == "date"
    assert df.index.is_monotonic_increasing
    assert "funding_rate" in df.columns

    # daily value must equal the mean of that day's fundingRate values
    raw = pd.DataFrame(rows)
    raw["date"] = pd.to_datetime(raw["fundingTime"], unit="ms").dt.floor("D")
    raw["fundingRate"] = raw["fundingRate"].astype(float)
    expected = raw.groupby("date")["fundingRate"].mean()
    pd.testing.assert_series_equal(
        df["funding_rate"], expected.rename("funding_rate"), check_names=False
    )

    # no future-dated rows (fixture window ends 2026-07-08)
    assert df.index.max() <= pd.Timestamp("2026-07-08")


def test_funding_daily_handles_empty():
    df = aggregate_funding_daily([])
    assert df.empty
    assert "funding_rate" in df.columns


# --------------------------------------------------------------------------- #
# Task 3: OHLCV history
# --------------------------------------------------------------------------- #
def test_ohlcv_daily_columns_and_monotonic():
    rows = json.load(open("tests/fixtures/regime/klines_SOLUSDT.json"))
    df = aggregate_ohlcv_daily(rows)
    assert {"open", "high", "low", "close", "volume"} <= set(df.columns)
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.is_monotonic_increasing
    # OHLCV values are numeric
    for c in ["open", "high", "low", "close", "volume"]:
        assert pd.api.types.is_numeric_dtype(df[c])
