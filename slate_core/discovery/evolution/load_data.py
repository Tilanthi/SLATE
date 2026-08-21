"""Market-data loader for the evolution layer.

Default source is `slate_core/data_cache/SOLUSDT_perpetual_1d_36m.csv` — ~1,080 REAL
daily SOLUSDT-perp bars (2023-08 → present) fetched from Binance, so IS/OOS
splits are measured on hundreds of bars, not ~35 (the overfit-from-tiny-sample
problem). The loader still resamples to daily if handed an intraday file (e.g.
the legacy hourly 6-month cache), preserving the documented daily-timeframe edge.
The closed-loop discovery loads its own data separately.

Binance funding history is merged into the daily candles as a `funding` column
(forward-filled from 8h events) — enabling funding-reversal / funding-carry
archetypes.
"""
from __future__ import annotations

import json
import os

import pandas as pd
from slate_core.config.paths import DATA_CACHE_DIR

REAL_DATA_DEFAULT = f"{DATA_CACHE_DIR}/SOLUSDT_perpetual_1d_36m.csv"
FUNDING_DATA_DEFAULT = f"{DATA_CACHE_DIR}/BINANCE_SOL_FUNDING.json"


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


def merge_funding(df: pd.DataFrame,
                  funding_path: str = FUNDING_DATA_DEFAULT) -> pd.DataFrame:
    """Merge Binance funding history into the candle df as a forward-filled
    `funding` column. Reads BINANCE_SOL_FUNDING.json ({fundingTime (ms),
    fundingRate (str)}). Pre-funding bars get 0.0. Returns df unchanged if the
    file is absent or malformed."""
    if not os.path.exists(funding_path):
        return df
    try:
        records = json.load(open(funding_path))
        fr = pd.DataFrame(records)
        fr["time"] = pd.to_datetime(fr["fundingTime"], unit="ms")
        fr["rate"] = fr["fundingRate"].astype(float)
        fr = fr.set_index("time").sort_index()
        fr = fr[~fr.index.duplicated(keep="last")]
        funded = df.copy()
        funded["funding"] = fr["rate"].reindex(funded.index, method="ffill").fillna(0.0)
        return funded
    except Exception:
        return df


def load_daily_data(path: str = REAL_DATA_DEFAULT, trim_to_funding: bool = True) -> pd.DataFrame:
    """Load OHLCV and resample to daily if the source is intraday, then merge
    Binance funding history as a `funding` column. If trim_to_funding and the
    funding column is present, drop pre-funding bars (where funding==0.0 at the
    start of the series) so IS/OOS splits cover real funding data."""
    df = load_ohlcv(path)
    if is_intraday(df):
        df = resample_to_daily(df)
    df = merge_funding(df)
    if trim_to_funding and "funding" in df.columns:
        # Find the first bar with nonzero funding; trim everything before it
        nonzero = (df["funding"] != 0.0)
        if nonzero.any() and not nonzero.iloc[0]:
            first_real = nonzero.idxmax()
            df = df.loc[first_real:]
    return df
