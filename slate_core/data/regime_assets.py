"""Regime-led discovery asset universe + data-store paths (Phase 1a).

Defines the ~10-perp basket the regime pipeline operates on, and the on-disk
layout for multi-stream per-symbol parquet files. Real Binance USDT-M perpetuals.
"""
from __future__ import annotations

from pathlib import Path

# ~10 liquid Binance USDT-M perpetuals. Amend here to change the universe.
BASKET = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT",
]

# Local data store (fetched data is NOT committed - gitignored).
DATA_DIR = Path("data/multi_stream")


def validate_symbol(symbol: str) -> bool:
    """True if symbol is an upper-case USDT perp in the configured basket."""
    return isinstance(symbol, str) and symbol.isupper() and symbol.endswith("USDT") and symbol in BASKET


def stream_path(symbol: str, stream: str) -> Path:
    """Parquet path for one (symbol, stream) daily series."""
    return DATA_DIR / symbol / f"{stream}.parquet"
