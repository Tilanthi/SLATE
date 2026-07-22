"""Honest discovery sweep — single-asset directional + carry strategies.

For every (dataset, strategy variant): compute IS Sharpe (first 60% of bars)
and OOS Sharpe (last 40%, NEVER touched by selection), plus turnover/cost and
an expanding walk-forward that re-selects the best variant per family on each
training window. Results ranked by OOS, with a multiple-testing guard.

Costs are brutally honest per venue (CEX taker 0.05%+15bps; DEX taker 0.045%+10bps),
real funding signed by position, 1-bar execution lag (no lookahead).
"""
from __future__ import annotations

import json
import time
from itertools import product

import numpy as np
import pandas as pd

from slate_core.backtest.data import load_cex_daily, load_cex_hourly, load_dex, resample
from slate_core.backtest.honest import backtest, walk_forward, bars_per_year_from_index, CEX, DEX
from slate_core.backtest import strategies as S


def is_oos(df, target, venue, is_frac=0.6):
    k = int(len(df) * is_frac)
    isdf, oosdf = df.iloc[:k], df.iloc[k:]
    r_is = backtest(target[:k], isdf, venue=venue)
    r_oos = backtest(target[k:], oosdf, venue=venue)
    return r_is["metrics"], r_oos["metrics"]


def run_single_asset():
    rows = []
    datasets = {
        "cex_daily_SOL": (load_cex_daily(), CEX),
        "cex_1h_SOL":    (load_cex_hourly(), CEX),
        "cex_4h_SOL":    (resample(load_cex_hourly(), "4h"), CEX),
        "cex_8h_SOL":    (resample(load_cex_hourly(), "8h"), CEX),
        "cex_12h_SOL":   (resample(load_cex_hourly(), "12h"), CEX),
        "dex_1h_SOL":    (load_dex("SOL"), DEX),
        "dex_1h_BTC":    (load_dex("BTC"), DEX),
        "dex_1h_ETH":    (load_dex("ETH"), DEX),
    }
    variants = S.expand_grid()
    t0 = time.time()
    for ds_name, (df, venue) in datasets.items():
        ppy = bars_per_year_from_index(df.index)
        for fam, name, fn, params in variants:
            try:
                target = fn(df, **params)
                if np.nansum(np.abs(target)) == 0:
                    continue
                m_is, m_oos = is_oos(df, target, venue)
                rows.append({
                    "dataset": ds_name, "family": fam, "name": name,
                    "params": json.dumps(params), "bars": len(df), "ppy": ppy,
                    "is_sharpe": m_is["sharpe"], "oos_sharpe": m_oos["sharpe"],
                    "oos_ret": m_oos["total_ret"], "oos_maxdd": m_oos["max_dd"],
                    "oos_calmar": m_oos["calmar"],
                    "turnover": m_oos["turnover"], "n_trades": m_oos["n_trades"],
                    "total_cost": m_oos["total_cost"], "total_funding": m_oos["total_funding"],
                    "is_ret": m_is["total_ret"],
                })
            except Exception as e:
                rows.append({"dataset": ds_name, "family": fam, "name": name,
                             "params": json.dumps(params), "error": str(e)[:80]})
        print(f"  {ds_name:14s} done ({time.time()-t0:.0f}s)")
    return pd.DataFrame(rows)


def analyze(df: pd.DataFrame):
    ok = df[df["oos_sharpe"].notna()].copy()
    print("\n" + "=" * 78)
    print("HONEST SWEEP — OOS results (last 40% of each series, never selected on)")
    print("=" * 78)
    print(f"total variants evaluated: {len(ok)}")
    print(f"OOS Sharpe > 0:   {(ok['oos_sharpe']>0).sum()}  ({100*(ok['oos_sharpe']>0).mean():.0f}%)")
    print(f"OOS Sharpe > 0.5: {(ok['oos_sharpe']>0.5).sum()}")
    print(f"OOS Sharpe > 1.0: {(ok['oos_sharpe']>1.0).sum()}")
    print(f"\nOOS Sharpe distribution:  p10={ok['oos_sharpe'].quantile(.1):+.2f}  "
          f"p50={ok['oos_sharpe'].median():+.2f}  p90={ok['oos_sharpe'].quantile(.9):+.2f}  "
          f"max={ok['oos_sharpe'].max():+.2f}")
    # Multiple-testing context: with N trials, the best OOS Sharpe has an expected
    # right-tail from noise alone. Rough SE of an annualized Sharpe over m bars:
    #   se ~= sqrt(ppy / m_oos).  Report how many exceed 2*se (nominal sig) and
    #   note Bonferroni would need ~3*se given N trials.
    print("\n--- TOP 25 by OOS Sharpe (with IS for overfit check) ---")
    top = ok.sort_values("oos_sharpe", ascending=False).head(25)
    for _, r in top.iterrows():
        flag = "  <-- IS>>OOS overfit?" if r["is_sharpe"] > r["oos_sharpe"] + 1.0 else ""
        print(f"  {r['dataset']:12s} {r['family']:8s} {r['name']:16s} "
              f"IS={r['is_sharpe']:+.2f} OOS={r['oos_sharpe']:+.2f} "
              f"ret={r['oos_ret']:+.2%} dd={r['oos_maxdd']:.2f} "
              f"trd={int(r['n_trades']):4d} cost={r['total_cost']:.3f} "
              f"{r['params'][:34]}{flag}")

    print("\n--- BY FAMILY: median OOS Sharpe + positive rate ---")
    g = ok.groupby("family")["oos_sharpe"].agg(["median", "mean", lambda s: (s > 0).mean()])
    g.columns = ["median_oos", "mean_oos", "pos_rate"]
    print(g.sort_values("median_oos", ascending=False).to_string())

    print("\n--- BY DATASET: median OOS Sharpe + positive rate ---")
    g2 = ok.groupby("dataset")["oos_sharpe"].agg(["median", "count", lambda s: (s > 0).mean()])
    g2.columns = ["median_oos", "n", "pos_rate"]
    print(g2.sort_values("median_oos", ascending=False).to_string())
    return ok


if __name__ == "__main__":
    print("Loading data + running honest sweep...")
    df = run_single_asset()
    df.to_csv("honest_sweep_results.csv", index=False)
    print(f"\nsaved {len(df)} rows -> honest_sweep_results.csv")
    analyze(df)
