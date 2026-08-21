"""Fetch + cache HL funding history for the portfolio premium streams.

Run once to populate data_cache/FUNDING_{coin}.json for each coin. The
portfolio service then loads funding from these cache files (offline, no API
needed at runtime).

Usage:
    python3 -m slate_core.premium.fetch_funding             # default coins
    python3 -m slate_core.premium.fetch_funding SOL BTC     # specific coins
"""
from __future__ import annotations

import json
import os
import sys

from slate_core.dex.data.hyperliquid_client import HLClient
from slate_core.config.paths import DATA_CACHE_DIR


def fetch_and_cache(coin: str, client: HLClient = None) -> int:
    """Fetch funding history from HL and cache to data_cache/FUNDING_{coin}.json.
    Returns the number of funding records cached."""
    client = client or HLClient()
    cache_path = f"{DATA_CACHE_DIR}/FUNDING_{coin}.json"
    try:
        hist = client.funding_history(coin)
        if not hist:
            print(f"  {coin}: no funding data returned")
            return 0
        os.makedirs(DATA_CACHE_DIR, exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(hist, f)
        print(f"  {coin}: cached {len(hist)} funding records -> {cache_path}")
        return len(hist)
    except Exception as exc:
        print(f"  {coin}: ERROR fetching funding: {str(exc)[:120]}")
        return 0


def main(coins=None):
    coins = coins or ["SOL", "BTC", "ETH"]
    print(f"Fetching HL funding history for {len(coins)} coins...")
    total = 0
    for coin in coins:
        total += fetch_and_cache(coin)
    print(f"Done: {total} total funding records cached.")


if __name__ == "__main__":
    coins = sys.argv[1:] if len(sys.argv) > 1 else None
    main(coins)
