"""Funding-persistence-timed carry prototype (research script, NOT a module).

Real data only (BASKET_*_FUNDING 8h + BASKET_*_1d daily OHLCV). Honest costs via
slate_core.backtest.honest. The backtester enforces held[t]=target[t-1] (causal).

Strategy:
  Naive baseline: each day, rank 24 coins by funding; short top-N (highest
    funding), long bottom-N (most negative). Equal-weighted. Hold 1 day.
  Persistence-timed: same ranks, but only ENTER/hold the carry when funding
    is HIGH and predicted to PERSIST (rolling AR(1) forecast stays extreme &
    same-signed). When persistence low / reversal predicted -> flat.
"""
from __future__ import annotations
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gjw255/astrodata/SWARM/SLATE")
from slate_core.backtest import backtest, CEX, bars_per_year_from_index

CACHE = "/Users/gjw255/astrodata/SWARM/SLATE/sol_data_cache"
COINS = ["AAVEUSDT","ADAUSDT","APTUSDT","ARBUSDT","ATOMUSDT","AVAXUSDT","BCHUSDT",
         "BNBUSDT","BTCUSDT","DOGEUSDT","DOTUSDT","ETHUSDT","FILUSDT","INJUSDT",
         "LINKUSDT","LTCUSDT","MKRUSDT","NEARUSDT","OPUSDT","SOLUSDT","SUIUSDT",
         "TIAUSDT","UNIUSDT","XRPUSDT"]


def load_coin(coin: str):
    """Return (daily_df, daily_funding_sum) for one coin. Daily OHLCV indexed at
    00:00 UTC; daily funding = SUM of the 3 actual 8h rates that day (honest)."""
    with open(f"{CACHE}/BASKET_{coin}_1d.json") as f:
        px = pd.DataFrame(json.load(f))
    px["timestamp"] = pd.to_datetime(px["timestamp"])
    px = px.set_index("timestamp").sort_index()
    for c in ["open","high","low","close","volume"]:
        if c in px.columns:
            px[c] = pd.to_numeric(px[c], errors="coerce")

    with open(f"{CACHE}/BASKET_{coin}_FUNDING.json") as f:
        fd = pd.DataFrame(json.load(f))
    fd["time"] = pd.to_datetime(fd["fundingTime"], unit="ms")
    fd["rate"] = pd.to_numeric(fd["fundingRate"], errors="coerce")
    fd = fd.dropna(subset=["rate"]).set_index("time").sort_index()[["rate"]]
    # sum of all 8h funding rates within each UTC day
    daily_fund_sum = fd["rate"].resample("1D").sum()
    daily_fund_last = fd["rate"].resample("1D").last()  # also keep last-rate (for ranking signal)

    df = px.join(daily_fund_sum.rename("fund_sum"), how="inner")
    df = df.join(daily_fund_last.rename("fund_last"), how="inner")
    return df


def load_all():
    frames = {}
    for c in COINS:
        df = load_coin(c)
        if len(df) > 200:
            frames[c] = df
    # restrict all to common date range
    start = max(f.index.min() for f in frames.values())
    end = min(f.index.max() for f in frames.values())
    out = {c: f.loc[start:end].copy() for c, f in frames.items()}
    return out, start, end


if __name__ == "__main__":
    frames, start, end = load_all()
    print(f"Loaded {len(frames)} coins, common range {start.date()} -> {end.date()} ({(end-start).days} days)")
    # show sample
    c = "BTCUSDT"
    print(f"\n{c} sample (head/tail):")
    print(frames[c][["close","fund_sum","fund_last"]].head(3))
    print(frames[c][["close","fund_sum","fund_last"]].tail(3))
    # basic funding stats
    print("\nMean daily funding sum (bps):")
    means = {c: frames[c]["fund_sum"].mean()*1e4 for c in frames}
    for c in sorted(means, key=means.get, reverse=True)[:5]:
        print(f"  {c}: {means[c]:+.2f} bps/day")
    print("  ...")
    for c in sorted(means, key=means.get)[:5]:
        print(f"  {c}: {means[c]:+.2f} bps/day")
