"""Panel (wide) data builder for the 24-coin funding universe.

Builds:
  fund_sum_wide[date, coin]   = sum of 3 daily 8h funding rates (honest per-day funding)
  fund_last_wide[date, coin]  = last 8h funding rate of the day (ranking signal)
  close_wide[date, coin]      = daily close

Coins enter when they have data (panel-style). The universe is the 24-coin basket
itself (a survivorship selection of "still-listed" perps — flagged as a caveat).
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd

CACHE = "/Users/gjw255/astrodata/SWARM/SLATE/sol_data_cache"
COINS = ["AAVEUSDT","ADAUSDT","APTUSDT","ARBUSDT","ATOMUSDT","AVAXUSDT","BCHUSDT",
         "BNBUSDT","BTCUSDT","DOGEUSDT","DOTUSDT","ETHUSDT","FILUSDT","INJUSDT",
         "LINKUSDT","LTCUSDT","MKRUSDT","NEARUSDT","OPUSDT","SOLUSDT","SUIUSDT",
         "TIAUSDT","UNIUSDT","XRPUSDT"]


def _load_coin(coin: str):
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
    fund_sum = fd["rate"].resample("1D").sum()
    fund_last = fd["rate"].resample("1D").last()
    out = px[["close","volume"]].copy()
    out["fund_sum"] = fund_sum
    out["fund_last"] = fund_last
    return out.dropna(subset=["close"])


def build_panel():
    closes, fund_sums, fund_lasts, vols = {}, {}, {}, {}
    for c in COINS:
        df = _load_coin(c)
        if len(df) < 200:
            continue
        closes[c] = df["close"]
        fund_sums[c] = df["fund_sum"]
        fund_lasts[c] = df["fund_last"]
        vols[c] = df["volume"]
    close = pd.DataFrame(closes).sort_index()
    fund_sum = pd.DataFrame(fund_sums).sort_index()
    fund_last = pd.DataFrame(fund_lasts).sort_index()
    vol = pd.DataFrame(vols).sort_index()
    # align all on the same index
    idx = close.index.intersection(fund_sum.index).intersection(fund_last.index)
    return (close.loc[idx], fund_sum.loc[idx], fund_last.loc[idx], vol.loc[idx])


if __name__ == "__main__":
    close, fund_sum, fund_last, vol = build_panel()
    print(f"Date range: {close.index.min().date()} -> {close.index.max().date()} ({len(close)} days)")
    print(f"Coins: {list(close.columns)}")
    print(f"Coins per date (median): {close.notna().sum(axis=1).median():.0f}")
    print(f"Coins per date (min/max): {close.notna().sum(axis=1).min():.0f} / {close.notna().sum(axis=1).max():.0f}")

    # ---------------- PERSISTENCE CHARACTERIZATION ----------------
    # AR(1) coefficient of daily funding sum per coin (full-sample, for diagnosis)
    print("\n=== Funding persistence (full-sample AR(1) on daily fund_sum) ===")
    print(f"{'coin':10s} {'AR(1)':>7s} {'half_life(d)':>13s} {'mean(bps)':>10s} {'std(bps)':>9s}")
    rows = []
    for c in close.columns:
        s = fund_sum[c].dropna()
        if len(s) < 100:
            continue
        x = s.values
        x_lag = x[:-1]
        x_cur = x[1:]
        phi = np.corrcoef(x_lag, x_cur)[0,1]
        # half-life in days: log(0.5)/log(phi) for phi in (0,1)
        if 0 < phi < 1:
            hl = np.log(0.5)/np.log(phi)
        else:
            hl = np.nan
        rows.append((c, phi, hl, s.mean()*1e4, s.std()*1e4))
    rows.sort(key=lambda r: -r[1])
    for r in rows:
        print(f"{r[0]:10s} {r[1]:7.3f} {r[2]:13.1f} {r[3]:+10.2f} {r[4]:9.2f}")
    print(f"\nMedian AR(1): {np.median([r[1] for r in rows]):.3f}")
    print(f"Median half-life: {np.median([r[2] for r in rows if not np.isnan(r[2])]):.1f} days")

    # rolling AR(1) over time — does it vary?
    print("\n=== Rolling 60-day AR(1) of funding (median across coins) ===")
    rolling_ar1 = []
    for c in close.columns:
        s = fund_sum[c].dropna()
        if len(s) < 100: continue
        # rolling AR(1)
        ar1 = s.rolling(60).apply(lambda x: np.corrcoef(x[:-1], x[1:])[0,1] if len(x)>2 else np.nan, raw=True)
        rolling_ar1.append(ar1)
    rdf = pd.concat(rolling_ar1, axis=1)
    median_ar1 = rdf.median(axis=1).dropna()
    print(f"  median rolling-AR(1) across time: mean={median_ar1.mean():.3f}, min={median_ar1.min():.3f}, max={median_ar1.max():.3f}")
    print(f"  quantiles 10/50/90: {median_ar1.quantile(0.1):.3f} / {median_ar1.quantile(0.5):.3f} / {median_ar1.quantile(0.9):.3f}")
