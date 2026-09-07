"""Parameter sweep on SOL basis: vary window, z_entry, holding-period, cost model.
Then walk-forward the best params for an honest OOS read."""
import sys, json
sys.path.insert(0, "novel_findings")
from _basis_backtest import (load_basis, basis_backtest, signal_zfade,
                              signal_zfade_tanh, PERP_ONE_WAY, SPOT_ONE_WAY)
import numpy as np, pandas as pd

df = load_basis("SOL")
print(f"SOL: {len(df)} bars {df.index.min().date()}->{df.index.max().date()}")

# Sweep with different cost assumptions
def sweep(df, signal_fn, **sk):
    rows = []
    for w in [30, 60, 90, 120]:
        for z in [1.0, 1.5, 2.0, 2.5, 3.0]:
            t = signal_fn(df, window=w, z_entry=z, **sk) if not sk else signal_fn(df, window=w, z_entry=z)
            for perp_ow in [PERP_ONE_WAY, 0.0005+5e-4]:  # [taker+slip, taker+low-slip]
                for spot_ow in [SPOT_ONE_WAY, 0.001, 0.0002]:  # [taker+slip, taker, maker-only]
                    r = basis_backtest(t, df, perp_one_way=perp_ow, spot_one_way=spot_ow)
                    m = r["metrics"]
                    rows.append(dict(w=w, z=z, perp_ow=perp_ow, spot_ow=spot_ow,
                                     trades=m.n_trades, sharpe=m.sharpe, apr=m.apr,
                                     maxdd=m.max_dd, gross=m.total_gross, fund=m.total_funding,
                                     cost=m.total_cost))
    return pd.DataFrame(rows)

R = sweep(df, signal_zfade)
R = R.sort_values("sharpe", ascending=False)
print("\nTop 15 by Sharpe (full-sample, IN-SAMPLE ONLY — will WF next):")
print(R.head(15).to_string())
print("\nBottom 5 (worst):")
print(R.tail(5).to_string())

print("\n--- Best per cost regime ---")
for (po, so), g in R.groupby(["perp_ow","spot_ow"]):
    best = g.sort_values("sharpe", ascending=False).iloc[0]
    print(f"perp_ow={po*1e4:.0f}bps spot_ow={so*1e4:.0f}bps : w={best.w} z={best.z} "
          f"trades={best.trades:.0f} sharpe={best.sharpe:.2f} APR={best.apr*100:.1f}% cost={best.cost*100:.1f}%")
