"""Tests for the Hyperliquid data layer (slate_core.dex.data)."""
import json

from slate_core.dex.data.hyperliquid_client import HLClient
from slate_core.dex.data.load_data import load_candles, refresh_store


def _candle(t):
    return {"t": t, "T": t + 59, "o": "1", "c": "1", "h": "1", "l": "1",
            "v": "1", "i": "1h", "s": "SOL", "n": 1}


def test_candles_paginates_via_last_open_time_and_stops_on_short_page():
    page1 = [_candle(1000 + i) for i in range(500)]   # full page -> must continue
    page2 = [_candle(1500 + i) for i in range(3)]      # short -> stop
    pages = iter([page1, page2])
    calls = []

    def fake_post(body):
        calls.append(body)
        return next(pages)

    out = HLClient(post_fn=fake_post, page=500).candles("SOL", "1h", start_ms=1000)
    assert len(out) == 503
    assert len(calls) == 2
    # second call advanced startTime past page1's last open time (1499) -> 1500
    assert calls[1]["req"]["startTime"] == 1500


def test_candles_without_start_is_single_recent_call():
    calls = []

    def fake_post(body):
        calls.append(body)
        return [_candle(1000)]

    out = HLClient(post_fn=fake_post).candles("SOL", "1h")
    assert len(out) == 1
    assert "startTime" not in calls[0]["req"]


def test_load_candles_roundtrip_to_ohlcv(tmp_path):
    rows = [{"t": 1000, "T": 1059, "o": "10", "h": "11", "l": "9", "c": "10.5",
             "v": "5", "i": "1h", "s": "SOL", "n": 1},
            {"t": 2000, "T": 2059, "o": "10.5", "h": "12", "l": "10", "c": "11.5",
             "v": "6", "i": "1h", "s": "SOL", "n": 2}]
    p = tmp_path / "c.json"
    p.write_text(json.dumps(rows))
    df = load_candles(str(p))
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert len(df) == 2
    assert abs(df["close"].iloc[1] - 11.5) < 1e-9


def test_refresh_store_appends_only_new_candles(tmp_path):
    p = tmp_path / "store.json"
    p.write_text(json.dumps([_candle(1000), _candle(2000)]))

    def fake_post(body):
        return [_candle(3000), _candle(4000)]

    n = refresh_store(str(p), "SOL", "1h", client=HLClient(post_fn=fake_post))
    df = load_candles(str(p))
    assert n == 2
    assert len(df) == 4
