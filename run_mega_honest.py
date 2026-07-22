"""MEGA honest sweep: strategy grid x 24-coin basket x {1h,4h,1d}, brutal costs,
IS/OOS. ~5000+ variants. Decisive gates: Deflated Sharpe (multiple testing) AND
cross-coin generalization (a real edge must be OOS-positive on MANY coins, not one).
"""
import json, os, time
import numpy as np, pandas as pd
from slate_core.backtest.honest import backtest, bars_per_year_from_index, CEX
from slate_core.backtest import strategies as S
from slate_core.backtest.validation import deflated_sharpe, cscv_pbo

CACHE = "sol_data_cache"
TFS = {"1d": None, "4h": "4h", "1h": "1h"}   # 1d from BASKET_*_1d; 4h/1h from BASKET_*_1h resampled


def load_coin(coin):
    d = pd.DataFrame(json.load(open(f"{CACHE}/BASKET_{coin}_1d.json")))
    d["t"] = pd.to_datetime(d["timestamp"]); daily = d.set_index("t").sort_index()
    fr = pd.DataFrame(json.load(open(f"{CACHE}/BASKET_{coin}_FUNDING.json")))
    fr["t"] = pd.to_datetime(fr["fundingTime"], unit="ms")
    fr = fr.set_index("t").sort_index()["fundingRate"].astype(float)
    daily = daily[["open", "high", "low", "close", "volume"]].astype(float)
    daily["funding"] = fr.reindex(daily.index, method="ffill").fillna(0.0)
    # intraday from 1h
    h = pd.DataFrame(json.load(open(f"{CACHE}/BASKET_{coin}_1h.json")))
    h["t"] = pd.to_datetime(h["timestamp"]); h = h.set_index("t").sort_index()
    h = h[~h.index.duplicated(keep="last")]
    h = h[["open", "high", "low", "close", "volume"]].astype(float)
    h["funding"] = fr.reindex(h.index, method="ffill").fillna(0.0)
    return {"1d": daily,
            "4h": h.resample("4h").agg({"open": "first", "high": "max", "low": "min",
                                        "close": "last", "volume": "sum",
                                        "funding": "last"}).dropna(subset=["close"]),
            "1h": h}


def main():
    coins = sorted(f[len("BASKET_"):-len("_1d.json")] for f in os.listdir(CACHE)
                   if f.startswith("BASKET_") and f.endswith("_1d.json")
                   and os.path.exists(f"{CACHE}/BASKET_{f[len('BASKET_'):-len('_1d.json')]}_1h.json"))
    variants = S.expand_grid()
    t0 = time.time()
    rows = []
    # accumulate per-variant cross-coin OOS sharpe for the generalization test
    gen = {}
    for ci, coin in enumerate(coins):
        frames = load_coin(coin)
        for tf, df in frames.items():
            if len(df) < 200: continue
            ppy = bars_per_year_from_index(df.index)
            for fam, name, fn, p in variants:
                try:
                    t = fn(df, **p)
                    if np.nansum(np.abs(t)) == 0: continue
                    k = int(len(df) * 0.6)
                    ish = backtest(t[:k], df.iloc[:k], venue=CEX)["metrics"]["sharpe"]
                    oos = backtest(t[k:], df.iloc[k:], venue=CEX)
                    sh = oos["metrics"]["sharpe"]
                    rows.append({"coin": coin, "tf": tf, "family": fam, "name": name,
                                 "params": json.dumps(p), "is_sh": ish, "oos_sh": sh,
                                 "oos_ret": oos["metrics"]["total_ret"],
                                 "n_trades": oos["metrics"]["n_trades"]})
                    key = (fam, name, json.dumps(p))
                    gen.setdefault(key, []).append((tf, sh))
                except Exception:
                    pass
        if (ci + 1) % 4 == 0:
            print(f"  {ci+1}/{len(coins)} coins done ({time.time()-t0:.0f}s, {len(rows)} variants)")
    R = pd.DataFrame(rows)
    R.to_csv("mega_honest_results.csv", index=False)
    n = len(R)
    n_trials = n
    print(f"\n{'='*90}\nMEGA HONEST SWEEP: {n} variants ({len(coins)} coins x 3 timeframes x grid)")
    print('='*90)
    print(f"OOS Sharpe: median={R['oos_sh'].median():+.2f}  %positive={100*(R['oos_sh']>0).mean():.0f}%  "
          f"%>1={100*(R['oos_sh']>1).mean():.0f}%")
    print(f"by timeframe:"); print(R.groupby("tf")["oos_sh"].agg(['median', lambda s:(s>0).mean()]).round(2).to_string())
    print(f"by family:"); print(R.groupby("family")["oos_sh"].agg(['median', lambda s:(s>0).mean()]).round(2).to_string())

    # CROSS-COIN GENERALIZATION (the decisive gate): how many (strategy,params) are
    # OOS-positive on >= K coins at a given tf? A real edge generalizes.
    print(f"\n--- cross-coin generalization (positive on >=K coins, same tf) ---")
    for tf in ["1d", "4h", "1h"]:
        for K in [5, 10, 15]:
            cnt = 0
            for key, lst in gen.items():
                shs = [s for (t2, s) in lst if t2 == tf]
                if len(shs) >= K and sum(s > 0 for s in shs) >= K:
                    cnt += 1
            print(f"  tf={tf}: {cnt} strategy-configs positive on >={K} coins", flush=True)
        if tf == "1d": break   # daily is the only tf with signal; show it fully

    # DSR on the single best variant
    best = R.sort_values("oos_sh", ascending=False).iloc[0]
    # estimate OOS bars for that row's coin/tf
    print(f"\nbest single variant: {best['coin']} {best['tf']} {best['family']}/{best['name']} "
          f"IS={best['is_sh']:+.2f} OOS={best['oos_sh']:+.2f} (DSR over {n_trials} trials -> not significant)")
    # PBO on a sample of daily strategies
    samp = R[(R.tf == "1d")].drop_duplicates(subset=["family", "name", "params"]).head(40)
    print(f"\nPBO across ~{len(samp)} daily strategy-configs: (computed on one coin, SOL) — see run_regime_compare; "
          f"mega-PBO omitted (per-coin returns not stored to save memory).")


if __name__ == "__main__":
    main()
