"""Sync historical fetcher for the regime data layer (Phase 1a).

Pulls daily OHLCV (`/fapi/v1/klines`) and funding-rate history
(`/fapi/v1/fundingRate`) from Binance USDT-M perpetuals, and aggregates each
stream to a daily frame with a strict no-lookforward rule.

Network lives here only; callers and tests parse fixtures or mock the fetch
functions. Public surface:
    fetch_funding_history(symbol, start_ms, end_ms) -> list[dict]
    fetch_ohlcv_history(symbol, start_ms, end_ms) -> list[list]
    aggregate_funding_daily(rows) -> pd.DataFrame
    aggregate_ohlcv_daily(rows) -> pd.DataFrame
"""
from __future__ import annotations

import logging
import time
from typing import Any, List

import pandas as pd
import requests

logger = logging.getLogger(__name__)

_FAPI = "https://fapi.binance.com"
_TIMEOUT = 20
_MAX_RETRIES = 4


def _get(endpoint: str, params: dict) -> Any:
    """GET a Binance fapi endpoint with rate-limit backoff and retries."""
    url = f"{_FAPI}{endpoint}"
    delay = 1.0
    last_exc: Exception | None = None
    for _ in range(_MAX_RETRIES):
        try:
            r = requests.get(url, params=params, timeout=_TIMEOUT)
            if r.status_code in (429, 418):
                logger.warning("Binance rate limit %s; backing off %.1fs", r.status_code, delay)
                time.sleep(delay)
                delay *= 2
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            last_exc = exc
            logger.warning("fetch %s failed (%s); retry in %.1fs", endpoint, exc, delay)
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"Binance fetch failed: {endpoint} ({last_exc})")


def fetch_funding_history(symbol: str, start_ms: int, end_ms: int) -> List[dict]:
    """Paginated historical funding rates for one symbol. Returns raw Binance rows."""
    out: List[dict] = []
    cursor = start_ms
    while cursor < end_ms:
        batch = _get("/fapi/v1/fundingRate",
                     {"symbol": symbol, "startTime": cursor, "endTime": end_ms, "limit": 1000})
        if not isinstance(batch, list) or not batch:
            break
        out.extend(batch)
        last = int(batch[-1]["fundingTime"])
        if last <= cursor:  # no progress -> avoid infinite loop
            break
        cursor = last + 1
        if len(batch) < 1000:
            break
    return out


def fetch_ohlcv_history(symbol: str, start_ms: int, end_ms: int) -> List[list]:
    """Paginated daily klines for one symbol. Returns raw Binance kline arrays."""
    out: List[list] = []
    cursor = start_ms
    while cursor < end_ms:
        batch = _get("/fapi/v1/klines", {"symbol": symbol, "interval": "1d",
                                         "startTime": cursor, "endTime": end_ms, "limit": 1000})
        if not isinstance(batch, list) or not batch:
            break
        out.extend(batch)
        last = int(batch[-1][0])  # openTime
        if last <= cursor:
            break
        cursor = last + 86_400_000  # +1 day
        if len(batch) < 1000:
            break
    return out


def aggregate_funding_daily(rows: List[dict]) -> pd.DataFrame:
    """Daily funding rate = mean of the day's funding events.

    No lookforward: a row dated D contains only events with fundingTime <= end of D.
    """
    if not rows:
        return pd.DataFrame(columns=["funding_rate"], index=pd.DatetimeIndex([], name="date"))
    df = pd.DataFrame(rows)
    df["fundingTime"] = pd.to_datetime(df["fundingTime"], unit="ms")
    df["date"] = df["fundingTime"].dt.floor("D")
    df["fundingRate"] = df["fundingRate"].astype(float)
    g = df.groupby("date")["fundingRate"].mean()
    out = g.to_frame("funding_rate")
    out.index = pd.DatetimeIndex(out.index, name="date")
    return out.sort_index()


def aggregate_ohlcv_daily(rows: List[list]) -> pd.DataFrame:
    """Daily OHLCV from Binance kline arrays.

    Kline positions: [0]=openTime, [1]=open, [2]=high, [3]=low, [4]=close,
    [5]=volume. Already daily (interval=1d); this normalizes types/index.
    """
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"],
                            index=pd.DatetimeIndex([], name="date"))
    df = pd.DataFrame(rows, columns=[f"c{i}" for i in range(max(len(rows[0]), 12))])
    out = pd.DataFrame({
        "open": df["c1"].astype(float),
        "high": df["c2"].astype(float),
        "low": df["c3"].astype(float),
        "close": df["c4"].astype(float),
        "volume": df["c5"].astype(float),
    })
    out.index = pd.DatetimeIndex(pd.to_datetime(df["c0"].astype("int64"), unit="ms").dt.floor("D"),
                                 name="date")
    return out[~out.index.duplicated(keep="last")].sort_index()
