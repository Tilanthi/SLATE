"""Market-maker rebate sweep on REAL data, optimistic vs honest (adverse-fill).

If the optimistic model (upper bound) already loses, reality is worse => the
retail maker-rebate edge is dead. If optimistic wins but honest loses, the edge
is within adverse-selection uncertainty (cannot confirm).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from slate_core.backtest.data import load_dex, load_cex_hourly
from slate_core.backtest.market_maker import mm_backtest
from slate_core.backtest.honest import DEX, CEX, bars_per_year_from_index
from run_deep_analysis import bootstrap_sharpe_ci


def sweep(df, venue, label):
    rows = []
    for hs in [0.0008, 0.0015, 0.003, 0.006, 0.012]:
        for mp in [1, 2, 4]:
            for sk in [0.0, 0.5, 1.0]:
                r = mm_backtest(df, half_spread=hs, max_pos=mp, inv_skew=sk, venue=venue)
                k = int(len(df) * 0.6)
                oos = r["returns"][k:]
                ppy = bars_per_year_from_index(df.index)
                ci = bootstrap_sharpe_ci(oos, ppy)
                rows.append({"hs": hs, "mp": mp, "sk": sk,
                             "oos_sh": oos.mean()/oos.std()*ppy**.5 if oos.std() else 0,
                             "ci5": ci[0], "ci95": ci[2],
                             "ret": r["total_ret"], "fills": r["n_fills"],
                             "fees": r["fees_paid"], "funding": r["funding_pnl"],
                             "final_qty": r["final_qty"]})
    return pd.DataFrame(rows)


def report(rows, label):
    print(f"\n--- {label} ---  (optimistic UPPER bound: fills assumed at the quote)")
    sub = rows.sort_values("oos_sh", ascending=False)
    print("  top 8 by OOS Sharpe:")
    for _, r in sub.head(8).iterrows():
        sig = "SIG" if r["ci5"] > 0 else "ns"
        print(f"    {sig} hs={r['hs']:.4f} mp={r['mp']} sk={r['sk']:.1f}  "
              f"OOS_sh={r['oos_sh']:+.2f} CI=[{r['ci5']:+.2f},{r['ci95']:+.2f}]  "
              f"ret={r['ret']:+.2%} fills={int(r['fills']):4d} "
              f"fees={r['fees']:.2f} funding={r['funding']:+.3f} final_qty={r['final_qty']:+.2f}")
    npos = (rows["oos_sh"] > 0).sum()
    print(f"  positive-rate: {npos}/{len(rows)}  best OOS Sharpe={rows['oos_sh'].max():+.2f}  "
          f"median={rows['oos_sh'].median():+.2f}")


if __name__ == "__main__":
    for df, venue, label in [(load_dex("SOL"), DEX, "DEX HL SOL 1h"),
                             (load_dex("BTC"), DEX, "DEX HL BTC 1h"),
                             (load_cex_hourly(), CEX, "CEX SOL 1h")]:
        rows = sweep(df, venue, label)
        print("=" * 84)
        print(f"MARKET-MAKER SWEEP — {label}  ({len(df)} bars)")
        print("=" * 84)
        report(rows, label)
