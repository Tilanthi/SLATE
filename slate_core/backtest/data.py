"""Honest data loading for the backtest discovery sweep.

Only REAL exchange data. No synthesis. The CEX ``SOLUSDT_{1m,5m,...,1d}_1y.csv``
files are all the SAME hourly series (verified: identical 8641 bars / values) —
mislabeled, so we expose the single real hourly series they contain, not the
timescales their filenames claim. Multi-timescale coverage comes from honestly
RESAMPLING the real hourly series (4h/8h/12h), never from the fake files.

Genuinely distinct real datasets:
  * CEX SOL daily, 1080 bars, 2023-08 → 2026-07 (3 yr) + Binance 8h funding
  * CEX SOL hourly, ~8641 bars, 1 yr
  * DEX HL SOL/BTC/ETH hourly, ~5001 bars, 7 mo + HL hourly funding
"""
from __future__ import annotations

import json
import os
from typing import Dict

import pandas as pd
from slate_core.config.paths import DATA_CACHE_DIR

_CACHE = DATA_CACHE_DIR


def _ohlcv_from_json(path: str) -> pd.DataFrame:
    df = pd.read_json(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp").sort_index()
    keep = [c for c in ["open", "high", "low", "close", "volume",
                        "atr", "atr_ratio", "rsi"] if c in df.columns]
    return df[keep].astype(float)


# --------------------------------------------------------------------------
# CEX (Binance SOLUSDT perp)
# --------------------------------------------------------------------------
def load_cex_daily(funding: bool = True) -> pd.DataFrame:
    """1080 real daily SOLUSDT-perp bars (2023-08→2026-07) + Binance 8h funding."""
    df = _ohlcv_from_json(f"{_CACHE}/SOLUSDT_perpetual_1d_36m.csv")
    if funding:
        df = _merge_binance_funding(df)
    return df


def load_cex_hourly() -> pd.DataFrame:
    """~8641 real hourly SOLUSDT bars (1 yr). Source of resampled coarser TFs."""
    # All SOLUSDT_*_1y.csv are the same hourly series; pick one canonical.
    return _ohlcv_from_json(f"{_CACHE}/SOLUSDT_1h_1y.csv")


def _merge_binance_funding(df: pd.DataFrame) -> pd.DataFrame:
    """Merge Binance 8h funding as forward-filled `funding` (per-8h rate)."""
    path = f"{_CACHE}/BINANCE_SOL_FUNDING.json"
    if not os.path.exists(path):
        return df
    rec = json.load(open(path))
    fr = pd.DataFrame(rec)
    fr["time"] = pd.to_datetime(fr["fundingTime"], unit="ms")
    fr["rate"] = fr["fundingRate"].astype(float)
    fr = fr.set_index("time").sort_index()[["rate"]].rename(columns={"rate": "funding"})
    out = df.copy()
    # For each bar, funding rate = last known 8h rate (forward fill); pre-funding = 0
    out["funding"] = fr["funding"].reindex(out.index, method="ffill").fillna(0.0)
    return out


# --------------------------------------------------------------------------
# DEX (Hyperliquid)
# --------------------------------------------------------------------------
def load_dex(coin: str = "SOL", funding: bool = True) -> pd.DataFrame:
    """~5001 real HL hourly bars + HL hourly funding for SOL/BTC/ETH."""
    from slate_core.dex.data.load_data import load_candles  # parses HL schema
    df = load_candles(f"{_CACHE}/HYPERLIQUID_{coin}_1h.json")
    if funding:
        df = _merge_hl_funding(df, coin)
    return df


def _merge_hl_funding(df: pd.DataFrame, coin: str) -> pd.DataFrame:
    path = f"{_CACHE}/FUNDING_{coin}.json"
    if not os.path.exists(path):
        return df
    rec = json.load(open(path))
    fr = pd.DataFrame(rec)
    fr["time"] = pd.to_datetime(fr["time"], unit="ms")
    fr["rate"] = fr["fundingRate"].astype(float)
    fr = fr.set_index("time").sort_index()[["rate"]].rename(columns={"rate": "funding"})
    out = df.copy()
    out["funding"] = fr["funding"].reindex(out.index, method="ffill").fillna(0.0)
    return out


# --------------------------------------------------------------------------
# Resampling (honest multi-timescale from the real hourly series)
# --------------------------------------------------------------------------
def resample(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Aggregate an OHLCV frame to a coarser freq (e.g. '4h','8h','12h','1D').
    Funding (if present) is SUMMED (total funding over the window)."""
    aggs = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if "volume" in df.columns:
        aggs["volume"] = "sum"
    out = df.resample(freq).agg(aggs).dropna(subset=["open", "close"])
    if "funding" in df.columns:
        # funding column is a PER-SETTLEMENT rate (e.g. 8h); keep it a rate (last in
        # window) so the backtester's settlements_per_bar scaling stays correct.
        # (Summing here would double-count funding on coarser bars.)
        fund = df["funding"].resample(freq).last()
        out["funding"] = fund.reindex(out.index).fillna(0.0)
    return out.astype({c: float for c in out.columns if c != "funding"})


def load_all() -> Dict[str, pd.DataFrame]:
    """The full real-data catalogue used by the sweep."""
    catalogue = {}
    daily = load_cex_daily()
    catalogue["cex_daily_SOL"] = daily
    hr = load_cex_hourly()
    catalogue["cex_1h_SOL"] = hr
    for f in ["4h", "8h", "12h", "1D"]:
        catalogue[f"cex_{f}_SOL"] = resample(hr, f)
    for coin in ["SOL", "BTC", "ETH"]:
        catalogue[f"dex_1h_{coin}"] = load_dex(coin)
    return catalogue


__all__ = ["load_cex_daily", "load_cex_hourly", "load_dex", "resample",
           "load_all", "_merge_binance_funding", "_merge_hl_funding"]
