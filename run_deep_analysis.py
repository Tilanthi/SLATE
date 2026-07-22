"""Deep analysis of honest-sweep survivors.

A real edge must be positive in BOTH the in-sample and out-of-sample windows
(IS<0, OOS>0 is just OOS-window regime luck — see the dex_1h trend results).
It must also have enough trades that the Sharpe isn't noise, and survive a
bootstrap on the OOS returns. We additionally run FAMILY-LEVEL walk-forward
(expanding window, re-select best variant on train, eval on test) for the
economically-motivated edges.
"""
from __future__ import annotations

import json
import numpy as np
import pandas as pd

from slate_core.backtest.data import load_cex_daily, load_cex_hourly, load_dex, resample
from slate_core.backtest.honest import backtest, bars_per_year_from_index, CEX, DEX
from slate_core.backtest import strategies as S


def bootstrap_sharpe_ci(returns, ppy, n=2000, seed=0, qs=(0.05, 0.5, 0.95)):
    if len(returns) < 5:
        return (0, 0, 0)
    rng = np.random.RandomState(seed)
    rets = np.asarray(returns)
    m = len(rets)
    shs = []
    for _ in range(n):
        s = rng.choice(rets, size=m, replace=True)
        sd = s.std(ddof=1)
        shs.append(s.mean() / sd * np.sqrt(ppy) if sd > 0 else 0)
    return tuple(np.percentile(shs, q * 100) for q in qs)


def target_for(df, fam, name, params):
    for f, n2, fn, _ in S.GRID:
        if f == fam and n2 == name:
            return fn(df, **params)
    return None


def family_walk_forward(df, venue, family, n_folds=5, min_train_frac=0.4):
    """Expanding window: pick the best variant in `family` by IS-Sharpe on the
    training window, eval that variant on the next test window. Concatenate OOS
    returns -> honest family OOS Sharpe."""
    variants = [(n, fn, p) for f, n, fn, _ in S.GRID if f == family
                for p in _expand_one(f, n)]
    n = len(df)
    ppy = bars_per_year_from_index(df.index)
    min_train = int(n * min_train_frac)
    fold = max(1, (n - min_train) // n_folds)
    oos, picks = [], []
    for f in range(n_folds):
        te = min_train + f * fold
        ts_end = min(te + fold, n)
        if te >= n or ts_end <= te:
            break
        train, test = df.iloc[:te], df.iloc[te:ts_end]
        best_sh, best = -9e9, None
        for (vn, fn, params) in variants:
            t = fn(train, **params)
            if np.nansum(np.abs(t)) == 0:
                continue
            sh = backtest(t, train, venue=venue)["metrics"]["sharpe"]
            if sh > best_sh:
                best_sh, best = sh, (vn, fn, params)
        if best is None:
            continue
        t_test = best[1](test, **best[2])
        r = backtest(t_test, test, venue=venue)
        oos.append(r["returns"])
        picks.append(best[0])
    oos = np.concatenate(oos) if oos else np.array([])
    if len(oos) == 0:
        return None
    eq = np.cumprod(1 + np.nan_to_num(oos))
    mu, sd = oos.mean(), oos.std(ddof=1)
    sh = mu / sd * np.sqrt(ppy) if sd > 0 else 0
    ci = bootstrap_sharpe_ci(oos, ppy)
    return {"family": family, "oos_sharpe": sh, "oos_ret": float(eq[-1] - 1),
            "picks": picks, "ci5": ci[0], "ci50": ci[1], "ci95": ci[2],
            "oos_bars": len(oos)}


def _expand_one(family, name):
    import itertools
    for f, n, fn, params in S.GRID:
        if f == family and n == name:
            keys = list(params.keys())
            for c in itertools.product(*[params[k] for k in keys]):
                yield dict(zip(keys, c))
            return


def main():
    res = pd.read_csv("honest_sweep_results.csv")
    res = res[res["oos_sharpe"].notna()].copy()

    # ---- robust survivor filter: positive in BOTH windows, enough trades, sane DD
    rob = res[(res["is_sharpe"] > 0) & (res["oos_sharpe"] > 0)
              & (res["n_trades"] >= 12) & (res["oos_maxdd"] < 0.5)].copy()
    rob["is_oos_gap"] = rob["is_sharpe"] - rob["oos_sharpe"]
    print("=" * 80)
    print("ROBUST SURVIVORS  (IS>0 AND OOS>0 AND n_trades>=12 AND OOS_DD<50%)")
    print("=" * 80)
    print(f"{len(rob)} of {len(res)} variants pass  (={100*len(rob)/len(res):.1f}%)\n")
    for _, r in rob.sort_values("oos_sharpe", ascending=False).iterrows():
        print(f"  {r['dataset']:13s} {r['family']:8s} {r['name']:15s} "
              f"IS={r['is_sharpe']:+.2f} OOS={r['oos_sharpe']:+.2f} "
              f"ret={r['oos_ret']:+.2%} dd={r['oos_maxdd']:.2f} trd={int(r['n_trades']):3d} "
              f"{r['params'][:30]}")

    # ---- bootstrap CI on OOS Sharpe for the daily survivors
    print("\n" + "=" * 80)
    print("BOOTSTRAP 90% CI on OOS Sharpe (daily survivors, re-run on real data)")
    print("=" * 80)
    datasets = {"cex_daily_SOL": (load_cex_daily(), CEX),
                "cex_4h_SOL": (resample(load_cex_hourly(), "4h"), CEX)}
    for _, r in rob[rob["dataset"].isin(datasets)].sort_values("oos_sharpe", ascending=False).head(12).iterrows():
        df, venue = datasets[r["dataset"]]
        params = json.loads(r["params"])
        t = target_for(df, r["family"], r["name"], params)
        if t is None:
            continue
        k = int(len(df) * 0.6)
        r_oos = backtest(t[k:], df.iloc[k:], venue=venue)
        ci = bootstrap_sharpe_ci(r_oos["returns"], bars_per_year_from_index(df.index))
        sig = "SIG" if ci[0] > 0 else "ns"
        print(f"  [{sig}] {r['dataset']:13s} {r['family']:8s} {r['name']:15s} "
              f"OOS_sh={r_oos['metrics']['sharpe']:+.2f}  CI=[{ci[0]:+.2f}, {ci[2]:+.2f}]  "
              f"ret={r_oos['metrics']['total_ret']:+.2%}")

    # ---- family-level walk-forward (the honest generalization test)
    print("\n" + "=" * 80)
    print("FAMILY-LEVEL WALK-FORWARD  (re-select best variant per train window)")
    print("=" * 80)
    df_d = load_cex_daily()
    for family in ["trend", "carry", "meanrev", "momentum"]:
        wf = family_walk_forward(df_d, CEX, family)
        if wf is None:
            print(f"  {family:8s}: (no trades)")
            continue
        sig = "SIG" if wf["ci5"] > 0 else "ns"
        print(f"  [{sig}] {family:8s}: OOS_sh={wf['oos_sharpe']:+.2f}  "
              f"CI=[{wf['ci5']:+.2f},{wf['ci95']:+.2f}]  ret={wf['oos_ret']:+.2%}  "
              f"bars={wf['oos_bars']}  picks={wf['picks']}")


if __name__ == "__main__":
    main()
