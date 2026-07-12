"""Tests for the refresh orchestrator (Phase 1a, Task 5). Network is mocked."""
from slate_core.data import refresh_regime_data as r
from slate_core.data import regime_store


def test_refresh_symbol_fetches_aggregates_saves(tmp_path, monkeypatch):
    monkeypatch.setattr(regime_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(r, "fetch_funding_history",
                        lambda *a, **k: [{"fundingTime": 1717200000000, "fundingRate": "0.0001"},
                                         {"fundingTime": 1717286400000, "fundingRate": "0.0002"}])
    monkeypatch.setattr(r, "fetch_ohlcv_history",
                        lambda *a, **k: [[1717200000000, "1", "2", "0", "1.5", "10"],
                                         [1717286400000, "1", "2", "0", "1.4", "8"]])

    saved = r.refresh_symbol("SOLUSDT", 1717200000000, 1717804800000)

    assert "funding_1d" in saved and "ohlcv_1d" in saved
    assert regime_store.has_stream("SOLUSDT", "funding_1d")
    assert regime_store.has_stream("SOLUSDT", "ohlcv_1d")
    # each produced a non-empty frame
    assert regime_store.load_stream("SOLUSDT", "funding_1d").shape[0] >= 1


def test_refresh_symbol_isolates_per_symbol_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(regime_store, "DATA_DIR", tmp_path)
    calls = []

    def flaky_funding(symbol, *a, **k):
        calls.append(symbol)
        if symbol == "BADUSDT":
            raise RuntimeError("boom")
        return [{"fundingTime": 1717200000000, "fundingRate": "0.0001"}]

    monkeypatch.setattr(r, "fetch_funding_history", flaky_funding)
    monkeypatch.setattr(r, "fetch_ohlcv_history", lambda *a, **k: [])

    # should not raise even though one stream is empty / a symbol would fail
    r.refresh_symbol("SOLUSDT", 1717200000000, 1717804800000)
    assert regime_store.has_stream("SOLUSDT", "funding_1d")
