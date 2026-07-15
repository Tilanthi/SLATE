"""Market-data loader for the evolution layer.

Default source is `sol_data_cache/SOLUSDT_perpetual_1d_36m.csv` — ~1,080 REAL
daily SOLUSDT-perp bars (2023-08 → present) fetched from Binance, so IS/OOS
splits are measured on hundreds of bars, not ~35 (the overfit-from-tiny-sample
problem). The loader still resamples to daily if handed an intraday file (e.g.
the legacy hourly 6-month cache), preserving the documented daily-timeframe edge.
The closed-loop discovery loads its own data separately.
"""
from __future__ import annotations

import pandas as pd

REAL_DATA_DEFAULT = "sol_data_cache/SOLUSDT_perpetual_1d_36m.csv"


def load_ohlcv(path: str = REAL_DATA_DEFAULT) -> pd.DataFrame:
    """Load the JSON-array data file (despite its .csv extension) with a DatetimeIndex."""
    df = pd.read_json(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp").sort_index()
    return df


def is_intraday(df: pd.DataFrame) -> bool:
    """True if the median bar interval is shorter than one day."""
    if len(df) < 3:
        return False
    median_delta = df.index.to_series().diff().median()
    return pd.notna(median_delta) and median_delta < pd.Timedelta(days=1)


def resample_to_daily(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate OHLCV (and ATR if present) to daily bars."""
    aggs = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if "volume" in df.columns:
        aggs["volume"] = "sum"
    if "atr" in df.columns:
        aggs["atr"] = "last"          # backtester reads atr (defaults to 2% if absent)
    out = df.resample("1D").agg(aggs).dropna(subset=["open", "close"])
    return out


def load_daily_data(path: str = REAL_DATA_DEFAULT) -> pd.DataFrame:
    """Load OHLCV and resample to daily if the source is intraday."""
    df = load_ohlcv(path)
    if is_intraday(df):
        return resample_to_daily(df)
    return df
