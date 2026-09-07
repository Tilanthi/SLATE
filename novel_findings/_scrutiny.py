"""Final scrutiny: placebo (random-mask) + capacity sweep + daily-resampled variant.

A) PLACEBO: replace the persistence mask with a RANDOM mask calibrated to the
   same average occupancy as persistence. If placebo does as well, persistence
   isn't the driver — turnover reduction is. Run 50 random seeds.

B) CAPACITY: re-run at AUM $1M, $10M, $100M, $500M to find where impact erodes
   the edge.

C) ALTERNATIVE PERSISTENCE DEFINITION: try halflife-based filter (rolling AR(1)
   converted to half-life; enter if half-life > H days) — robustness check.
"""
from __future__ import annotations
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, "/Users/gjw255/astrodata/SWARM/SLATE")
sys.path.insert(0, "/Users/gjw255/astrodata/SWARM/SLATE/novel_findings")
from slate_core.backtest import backtest, CEX, bars_per_year_from_index
from _panel import build_panel
from _strat import cross_sectional_rank_signal, naive_target, persistence_mask_v1
from _oos import aggregate, resample_target, metrics


def placebo_random_mask(fund_last, persistence_mask, seed=0):
    """Random mask with same per-coin occupancy as persistence_mask."""
    rng = np.random.default_rng(seed)
    out = pd.DataFrame(0.0, index=fund_last.index, columns=fund_last.columns)
    pm = persistence_mask.reindex(fund_last.index).fillna(0.0)
    for c in pm.columns:
        occ = pm[c].mean()
        n_on = int(occ * len(pm))
        idxs = rng.choice(len(pm), size=n_on, replace=False)
        v = np.zeros(len(pm)); v[idxs] = 1.0
        out[c] = v
    return out


def main():
    close, fund_sum, fund_last, vol = build_panel()
    rank_signal = cross_sectional_rank_signal(fund_last)
    tgt_naive = naive_target(rank_signal, top_n=3)
    pmask = persistence_mask_v1(fund_last, window=30, tau=0.5)

    # restrict to OOS window (last 750 days) to match the WF eval
    oos_idx = close.index[-750:]

    print("="*78)
    print("A) PLACEBO TEST — random mask with same occupancy, OOS window (750d)")
    print("="*78)
    print(f"   Persistence mask avg occupancy: {pmask.mean().mean()*100:.1f}%")
    tgt_naive_w = resample_target(tgt_naive.loc[oos_idx], freq="W")
    tgt_pers_w = resample_target((tgt_naive*pmask).loc[oos_idx], freq="W")
    a_n = aggregate(tgt_naive_w, close, fund_sum, vol)
    a_p = aggregate(tgt_pers_w, close, fund_sum, vol)
    print(f"   NAIVE  (no mask):   Sharpe {metrics(a_n)['sharpe']:+.2f} | APR {metrics(a_n)['ann_ret']*100:+.2f}%")
    print(f"   PERSIST mask:       Sharpe {metrics(a_p)['sharpe']:+.2f} | APR {metrics(a_p)['ann_ret']*100:+.2f}%")
    placebo_sharpe = []
    for s in range(30):
        rmask = placebo_random_mask(fund_last, pmask, seed=s)
        tgt_r = resample_target((tgt_naive*rmask).loc[oos_idx], freq="W")
        a_r = aggregate(tgt_r, close, fund_sum, vol)
        placebo_sharpe.append(metrics(a_r)["sharpe"])
    placebo_sharpe = np.array(placebo_sharpe)
    print(f"   PLACEBO (30 seeds): Sharpe mean={placebo_sharpe.mean():+.2f} std={placebo_sharpe.std():.2f} "
          f"range=[{placebo_sharpe.min():+.2f}, {placebo_sharpe.max():+.2f}]")
    print(f"   PERSIST z-score vs placebo: {(metrics(a_p)['sharpe']-placebo_sharpe.mean())/placebo_sharpe.std():+.2f}")
    print(f"   P( placebo >= persist ): {(placebo_sharpe >= metrics(a_p)['sharpe']).mean()*100:.0f}%")

    print("\n" + "="*78)
    print("B) CAPACITY SWEEP — persistence variant, OOS window")
    print("="*78)
    for cap in [1_000_000, 10_000_000, 100_000_000, 500_000_000, 1_000_000_000]:
        a = aggregate(tgt_pers_w, close, fund_sum, vol, capital=cap, impact=True)
        m = metrics(a)
        print(f"   AUM ${cap/1e6:>6.0f}M: Sharpe {m['sharpe']:+.2f} | APR {m['ann_ret']*100:+.2f}% | maxDD {m['max_dd']*100:.1f}%")

    print("\n" + "="*78)
    print("C) ROBUSTNESS — alternative persistence filter (half-life > H days)")
    print("="*78)
    # half-life = log(0.5)/log(ar1) when 0<ar1<1
    ar1 = pmask  # not exactly; rebuild
    for c in fund_last.columns:
        s = fund_last[c]
        x = s.values
        if len(x) < 60: continue
    for H in [2, 3, 5]:
        mask = pd.DataFrame(0.0, index=fund_last.index, columns=fund_last.columns)
        for c in fund_last.columns:
            s = fund_last[c]
            def _hl(x):
                x = x[~np.isnan(x)]
                if len(x)<5: return np.nan
                phi = np.corrcoef(x[:-1],x[1:])[0,1]
                if 0 < phi < 1: return np.log(0.5)/np.log(phi)
                return np.nan
            hl = s.rolling(30, min_periods=10).apply(_hl, raw=True)
            mask[c] = (hl > H).astype(float)
        tgt_h = resample_target((tgt_naive*mask).loc[oos_idx], freq="W")
        a_h = aggregate(tgt_h, close, fund_sum, vol)
        m = metrics(a_h)
        print(f"   halflife>{H}d: Sharpe {m['sharpe']:+.2f} | APR {m['ann_ret']*100:+.2f}% | occupancy {mask.mean().mean()*100:.0f}%")


if __name__ == "__main__":
    main()
