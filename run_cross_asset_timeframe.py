"""Cross-asset timeframe study: does the 'coarser candle -> higher median OOS Sharpe'
trend found on SOL generalize to BTC and ETH? If yes -> the fee-drag mechanism is
real and general; if SOL-only -> the weekly-positive was sample luck.

Builds BTC/ETH daily frames (Binance fapi OHLCV + 8h funding), resamples to
1D/2D/3D/1W, runs the FULL grid (selection-free median), same honest pipeline.
"""
import json, time, os
import numpy as np, pandas as pd, requests

from slate_core.backtest.data import resample
from slate_core.backtest.honest import backtest, bars_per_year_from_index, CEX
from slate_core.backtest import strategies as S
from slate_core.backtest.validation import deflated_sharpe

KLINE = "https://fapi.binance.com/fapi/v1/klines"


def fetch_daily_ohlcv(sym, days=1500):
    path = f"sol_data_cache/CEX_{sym}_1d_ohlcv.json"
    if os.path.exists(path):
        d = json.load(open(path))
    else:
        start = int((time.time() - days * 86400) * 1000); out = []; cur = start
        while cur < time.time() * 1000:
            r = requests.get(KLINE, params={"symbol": sym, "interval": "1d",
                                            "startTime": cur, "limit": 1000}, timeout=20)
            d = r.json()
            if not d: break
            out.extend(d); cur = d[-1][0] + 86400000
        d = [{"timestamp": pd.Timestamp(k[0], unit="ms").isoformat(),
              "open": float(k[1]), "high": float(k[2]), "low": float(k[3]),
              "close": float(k[4]), "volume": float(k[5])} for k in out]
        json.dump(d, open(path, "w"))
    df = pd.DataFrame(d)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp").sort_index()
    df.index = df.index.tz_localize(None).normalize()
    # merge Binance 8h funding as ffill rate (same as SOL daily frame)
    fr = pd.DataFrame(json.load(open(f"sol_data_cache/BINANCE_{sym}_FUNDING.json")))
    fr["t"] = pd.to_datetime(fr["fundingTime"], unit="ms")
    fr = fr.set_index("t").sort_index()["fundingRate"].astype(float)
    df["funding"] = fr.reindex(df.index, method="ffill").fillna(0.0)
    return df


def run_grid(df):
    ppy = bars_per_year_from_index(df.index)
    oos_sh, robust, best, best_row = [], 0, -9, None
    for fam, name, fn, p in S.expand_grid():
        try:
            t = fn(df, **p)
            if np.nansum(np.abs(t)) == 0: continue
            k = int(len(df) * 0.6)
            ish = backtest(t[:k], df.iloc[:k], venue=CEX)["metrics"]["sharpe"]
            oos = backtest(t[k:], df.iloc[k:], venue=CEX)
            sh = oos["metrics"]["sharpe"]
            oos_sh.append(sh)
            if ish > 0 and sh > 0 and oos["metrics"]["n_trades"] >= 8: robust += 1
            if sh > best: best, best_row = sh, (fam, name, p, sh, oos["metrics"]["n_trades"])
        except Exception: pass
    n = len(oos_sh)
    return {"bars": len(df), "n": n, "med": float(np.median(oos_sh)) if n else float("nan"),
            "pos": (np.array(oos_sh) > 0).mean() if n else 0.0, "robust": robust,
            "best": best, "best_row": best_row, "ppy": ppy}


from slate_core.backtest.data import load_cex_daily
assets = {"SOL": load_cex_daily(), "BTC": fetch_daily_ohlcv("BTCUSDT"),
          "ETH": fetch_daily_ohlcv("ETHUSDT")}

print("=" * 92)
print("CROSS-ASSET TIMEFRAME STUDY: does coarser-is-better generalize? (SOL/BTC/ETH, honest)")
print("=" * 92)
print(f"{'asset':5s}{'TF':5s}{'bars':>6s}{'med_OOS':>9s}{'%pos':>7s}{'robust':>8s}{'best':>8s}")
grid_results = {}
for asset, daily in assets.items():
    grid_results[asset] = {}
    for tf, freq in [("1D", "1D"), ("2D", "2D"), ("3D", "3D"), ("1W", "W")]:
        df = daily if tf == "1D" else resample(daily, freq)
        r = run_grid(df)
        grid_results[asset][tf] = r
        print(f"{asset:5s}{tf:5s}{r['bars']:6d}{r['med']:+9.2f}{100*r['pos']:6.0f}%{r['robust']:8d}{r['best']:+8.2f}")
    print()

print("--- does the coarsening trend (median OOS Sharpe rising 1D->1W) replicate? ---")
for asset in assets:
    meds = [grid_results[asset][tf]["med"] for tf in ["1D", "2D", "3D", "1W"]]
    pos = [grid_results[asset][tf]["pos"] for tf in ["1D", "2D", "3D", "1W"]]
    rises = all(meds[i+1] >= meds[i] - 0.05 for i in range(3))
    print(f"  {asset}: median {['%.2f'%m for m in meds]}  pos% {[f'{100*p:.0f}' for p in pos]}  "
          f"{'REPLICATES (rises)' if rises else 'does NOT cleanly rise'}")

print("\n--- does SOL's 2D winner (rsi ob80/os20) transfer to BTC/ETH? ---")
for asset, daily in assets.items():
    df2 = resample(daily, "2D")
    t = S.meanrev_rsi(df2, ob=80, os_=20)
    r = backtest(t[int(len(df2)*0.6):], df2.iloc[int(len(df2)*0.6):], venue=CEX)
    print(f"  {asset} 2D rsi(80/20): OOS_sh={r['metrics']['sharpe']:+.2f} "
          f"ret={r['metrics']['total_ret']:+.2%} trd={int(r['metrics']['n_trades'])}")
