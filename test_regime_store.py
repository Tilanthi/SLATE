"""Tests for the parquet store + manifest (Phase 1a, Task 4)."""
import pandas as pd

from slate_core.data import regime_store


def _df():
    idx = pd.to_datetime(["2026-06-01", "2026-06-02"])
    return pd.DataFrame({"funding_rate": [0.0001, 0.0002]}, index=idx)


def test_save_load_roundtrip_and_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(regime_store, "DATA_DIR", tmp_path)
    regime_store.save_stream("SOLUSDT", "funding_1d", _df())

    got = regime_store.load_stream("SOLUSDT", "funding_1d")
    pd.testing.assert_frame_equal(got, _df())

    m = regime_store.read_manifest()
    assert m["SOLUSDT"]["funding_1d"]["rows"] == 2
    assert m["SOLUSDT"]["funding_1d"]["start"].startswith("2026-06-01")
    assert regime_store.has_stream("SOLUSDT", "funding_1d") is True
    assert regime_store.has_stream("SOLUSDT", "ohlcv_1d") is False


def test_load_missing_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(regime_store, "DATA_DIR", tmp_path)
    try:
        regime_store.load_stream("BTCUSDT", "funding_1d")
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError for missing stream")
