"""Loader + accumulating store for Hyperliquid candle data.

Because the first-party candle API only exposes the most recent 5,000 candles,
the store is *accumulating*: `refresh_store` polls candles since the last stored
open time and appends, so history grows over time across runs. No synthetic data.
"""
from __future__ import annotations

import json
import os
from typing import Optional

import pandas as pd

from slate_core.dex.data.hyperliquid_client import HLClient

REAL_DATA_DEFAULT = "sol_data_cache/HYPERLIQUID_SOL_1h.json"
# HL candles: t=openTime(ms), T=closeTime(ms), o/h/l/c/v, n, i, s
_CAN_KEYS = ["t", "T", "o", "h", "l", "c", "v", "n", "i", "s"]


def load_candles(path: str = REAL_DATA_DEFAULT) -> pd.DataFrame:
    """Load the JSON-array candle store into an OHLCV frame on a DatetimeIndex."""
    df = pd.read_json(path)
    df = df.rename(columns={"o": "open", "h": "high", "l": "low",
                            "c": "close", "v": "volume"})
    df["timestamp"] = pd.to_datetime(df["t"], unit="ms")
    df = df[["timestamp", "open", "high", "low", "close", "volume"]] \
        .set_index("timestamp").sort_index()
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["close"])


def refresh_store(path: str = REAL_DATA_DEFAULT, coin: str = "SOL",
                  interval: str = "1h", client: Optional[HLClient] = None) -> int:
    """Fetch candles newer than the last stored open time and append (dedup by t).
    Returns the number of new candles appended."""
    client = client or HLClient()
    existing = []
    if os.path.exists(path):
        with open(path) as f:
            existing = json.load(f)
    last_t = max((c["t"] for c in existing), default=None)
    start = (last_t + 1) if last_t is not None else None
    new = client.candles(coin, interval, start_ms=start)
    have = {c["t"] for c in existing}
    fresh = [c for c in new if c["t"] not in have]
    if not fresh:
        return 0
    merged = existing + fresh
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(merged, f)
    return len(fresh)


def merge_funding(df, client, coin: str = "SOL"):
    """Fetch HL funding history and add a forward-filled 'funding' column (the 8h
    funding rate carried onto each bar). funding>0 => longs pay (carry: short);
    funding<0 => longs receive. Returns df unchanged if funding can't be fetched.

    Tries a DISK CACHE first (sol_data_cache/FUNDING_{coin}.json), then the live
    API, caching the result for offline use."""
    import json, os
    import pandas as pd

    cache_path = f"sol_data_cache/FUNDING_{coin}.json"
    hist = None

    # 1) Try disk cache first
    if os.path.exists(cache_path):
        try:
            with open(cache_path) as f:
                hist = json.load(f)
        except Exception:
            hist = None

    # 2) Fall back to live API + cache the result
    if not hist:
        try:
            hist = client.funding_history(coin)
            if hist:
                os.makedirs("sol_data_cache", exist_ok=True)
                with open(cache_path, "w") as f:
                    json.dump(hist, f)
        except Exception:
            return df

    if not hist:
        return df
    fr = pd.DataFrame(hist)
    if "fundingRate" not in fr.columns or "time" not in fr.columns:
        return df
    fr["time"] = pd.to_datetime(fr["time"], unit="ms")
    s = (fr.set_index("time")["fundingRate"].astype(float)
         .sort_index()[~fr.set_index("time").index.duplicated(keep="last")])
    funded = df.copy()
    funded["funding"] = s.reindex(df.index, method="ffill").fillna(0.0)
    return funded


def load_markets(coins, base: str = "sol_data_cache"):
    """Load multiple HL perp candle frames for cross-market / pairs strategies.
    Returns {coin: df}. Files must already be fetched (HYPERLIQUID_{coin}_1h.json)."""
    return {c: load_candles(f"{base}/HYPERLIQUID_{c}_1h.json") for c in coins}
