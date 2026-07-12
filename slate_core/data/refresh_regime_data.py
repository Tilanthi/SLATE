"""Refresh orchestrator + CLI for the regime data layer (Phase 1a, Task 5).

Fetches each stream for a symbol (or the whole basket), aggregates to daily, and
persists via regime_store. Run as a CLI (background/decoupled from the live loop):

    python3 -m slate_core.data.refresh_regime_data --start 2026-01-01 --end 2026-07-12
    python3 -m slate_core.data.refresh_regime_data --start 2026-01-01 --end 2026-07-12 --symbol SOLUSDT
"""
from __future__ import annotations

import argparse
import datetime
import logging

from slate_core.data import regime_store
from slate_core.data.multi_stream_fetcher import (
    aggregate_funding_daily,
    aggregate_ohlcv_daily,
    fetch_funding_history,
    fetch_ohlcv_history,
)
from slate_core.data.regime_assets import BASKET

logger = logging.getLogger(__name__)

DEFAULT_STREAMS = ("funding_1d", "ohlcv_1d")


def refresh_symbol(symbol: str, start_ms: int, end_ms: int,
                   streams: tuple = DEFAULT_STREAMS) -> dict:
    """Fetch + aggregate + save all requested streams for one symbol."""
    if "funding_1d" in streams:
        rows = fetch_funding_history(symbol, start_ms, end_ms)
        regime_store.save_stream(symbol, "funding_1d", aggregate_funding_daily(rows))
    if "ohlcv_1d" in streams:
        rows = fetch_ohlcv_history(symbol, start_ms, end_ms)
        regime_store.save_stream(symbol, "ohlcv_1d", aggregate_ohlcv_daily(rows))
    return regime_store.read_manifest().get(symbol, {})


def _ms(date_str: str) -> int:
    return int(datetime.datetime.fromisoformat(date_str).timestamp() * 1000)


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="Refresh regime multi-stream data.")
    ap.add_argument("--start", required=True, help="YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD")
    ap.add_argument("--symbol", default=None, help="single symbol; default = whole basket")
    args = ap.parse_args(argv)

    start_ms, end_ms = _ms(args.start), _ms(args.end)
    symbols = [args.symbol] if args.symbol else BASKET
    for sym in symbols:
        try:
            saved = refresh_symbol(sym, start_ms, end_ms)
            logger.info("refreshed %s: %s", sym, list(saved.keys()))
            print(f"✓ {sym}: {list(saved.keys())}")
        except Exception as exc:  # noqa: BLE001 - one symbol failing must not stop the basket
            logger.error("refresh %s failed: %s", sym, exc)
            print(f"✗ {sym}: {exc}")
    return 0


if __name__ == "__main__":
    main()
