"""Deterministic multi-stream loader for the regime data layer (Phase 1a, Task 6).

    load_regime_data(symbols, start, end, streams=None) -> dict[symbol, DataFrame]

Per symbol: joins all available daily streams on a daily date index bounded to
[start, end], fills only single isolated missing days (multi-day gaps stay NaN -
no fabrication), and rejects future-dated source rows. Deterministic: identical
output across calls for the same inputs.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional

import pandas as pd

from slate_core.data import regime_store

DEFAULT_STREAMS = ("ohlcv_1d", "funding_1d")


def _fill_isolated_day_gaps(df: pd.DataFrame) -> pd.DataFrame:
    """Fill only single isolated missing days (both neighbours present).
    Multi-day gaps stay NaN so we never fabricate values."""
    if df.empty:
        return df
    filled = df.ffill(limit=1)
    # keep a fill only where the NEXT day has real data (i.e. an isolated gap)
    keep = df.isna() & df.notna().shift(-1, fill_value=False)
    out = df.copy()
    out[keep] = filled[keep]
    return out


def load_regime_data(
    symbols: Iterable[str],
    start: str,
    end: str,
    streams: Optional[List[str]] = None,
) -> Dict[str, pd.DataFrame]:
    """Load and join daily streams per symbol over [start, end]."""
    streams = list(streams) if streams else list(DEFAULT_STREAMS)
    rng = pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="D", name="date")
    horizon = pd.Timestamp.now(tz=None).normalize() + pd.Timedelta(days=1)

    out: Dict[str, pd.DataFrame] = {}
    for sym in symbols:
        frames = []
        for st in streams:
            try:
                df = regime_store.load_stream(sym, st)
            except FileNotFoundError:
                continue
            df.index = pd.DatetimeIndex(df.index, name="date")
            if not df.empty and df.index.max() > horizon:
                raise ValueError(
                    f"{sym}/{st} contains future-dated rows (max={df.index.max().date()})"
                )
            frames.append(df)

        if not frames:
            out[sym] = pd.DataFrame(index=rng)
            continue

        joined = pd.concat(frames, axis=1)
        joined = joined[~joined.index.duplicated(keep="last")].sort_index()
        joined = joined.reindex(rng)
        out[sym] = _fill_isolated_day_gaps(joined)
    return out
