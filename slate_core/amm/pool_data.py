"""Pool data fetcher for AMM LP backtesting.

Fetches stablecoin price history (USDCUSDT, EURCUSDT) from Binance and estimates
pool volume from price volatility. Real pool volume would come from a subgraph
or indexer; this vol-scaled proxy is the documented v1 approximation.
"""
from __future__ import annotations

import json
import os
import time

import pandas as pd
import requests

BINANCE_KLINES = "https://fapi.binance.com/fapi/v1/klines"
CACHE_DIR = "sol_data_cache"


def fetch_stablecoin_prices(pair: str = "USDCUSDT", interval: str = "1d",
                            days: int = 365) -> pd.DataFrame:
    """Fetch daily candle data for a stablecoin pair from Binance Futures."""
    path = os.path.join(CACHE_DIR, f"AMM_{pair}_{interval}.json")
    if os.path.exists(path):
        df = pd.read_json(path)
        if len(df) > 50:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            return df.set_index("timestamp").sort_index()

    start = int((time.time() - days * 86400) * 1000)
    all_klines = []
    cur = start
    while cur < int(time.time() * 1000):
        resp = requests.get(BINANCE_KLINES, params={
            "symbol": pair, "interval": interval, "startTime": cur, "limit": 1000,
        }, timeout=15)
        data = resp.json()
        if not data:
            break
        all_klines.extend(data)
        cur = data[-1][0] + 1
        if len(data) < 1000:
            break
        time.sleep(0.3)

    rows = []
    for k in all_klines:
        rows.append({"timestamp": pd.Timestamp(k[0], unit="ms"),
                     "open": float(k[1]), "high": float(k[2]),
                     "low": float(k[3]), "close": float(k[4]),
                     "volume": float(k[5])})
    df = pd.DataFrame(rows).set_index("timestamp").sort_index()
    os.makedirs(CACHE_DIR, exist_ok=True)
    df.reset_index().to_json(path, orient="records", date_format="iso")
    return df


def load_pool_data(pair: str = "USDCUSDT") -> pd.DataFrame:
    """Load (or fetch) stablecoin price data for LP backtesting."""
    return fetch_stablecoin_prices(pair)
