"""Fetch HL perp candles + funding for a ~20-coin basket (cross-sectional carry).

Reuses the HL client (real Hyperliquid API). Saves aligned hourly candles and
hourly funding per coin. No synthesis.
"""
from __future__ import annotations

import json
import os
import time

import pandas as pd

from slate_core.dex.data.hyperliquid_client import HLClient
from slate_core.dex.data.load_data import load_candles

CACHE = "sol_data_cache"
BASKET = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK",
          "DOT", "LTC", "BCH", "NEAR", "APT", "ARB", "OP", "INJ", "AAVE",
          "MKR", "UNI"]


def fetch_one(client, coin):
    """Fetch ~2 years of hourly candles + funding history; cache. Retry on 429."""
    cpath = f"{CACHE}/HL_{coin}_1h.json"
    fpath = f"{CACHE}/HL_{coin}_FUNDING.json"
    if os.path.exists(cpath) and os.path.exists(fpath):
        return coin
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - 730 * 86400 * 1000   # ~2 years

    def _retry(fn, *a):
        for attempt in range(6):
            try:
                return fn(*a)
            except Exception as e:
                if "429" in str(e) and attempt < 5:
                    time.sleep(5 * (attempt + 1))   # 5,10,15,20,25s backoff
                    continue
                raise
    try:
        candles = _retry(client.candles, coin, "1h", start_ms)
        json.dump(candles, open(cpath, "w"))
        time.sleep(1.5)
        fund = _retry(client.funding_history, coin, start_ms)
        json.dump(fund, open(fpath, "w"))
        return coin
    except Exception as e:
        print(f"  {coin}: ERR {type(e).__name__}: {str(e)[:80]}")
        return None


def main():
    client = HLClient()
    got = []
    for coin in BASKET:
        r = fetch_one(client, coin)
        if r:
            got.append(coin)
            n = len(json.load(open(f"{CACHE}/HL_{coin}_1h.json")))
            print(f"  {coin}: {n} candles + funding cached")
        time.sleep(2.0)   # be polite to the HL API (429 otherwise)
    print(f"\nfetched {len(got)}/{len(BASKET)} coins: {got}")
    json.dump(got, open(f"{CACHE}/hl_basket_coins.json", "w"))


if __name__ == "__main__":
    main()
