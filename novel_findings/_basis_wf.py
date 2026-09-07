"""Walk-forward basis strategy: re-fit (w,z) on each fold's train, evaluate OOS.
Also test robustness by excluding FTX crash window."""
import sys, json
sys.path.insert(0, "novel_findings")
from _basis_backtest import (load_basis, basis_backtest, signal_zfade,
                              PERP_ONE_WAY, SPOT_ONE_WAY)
import numpy as np, pandas as pd

df = load_basis("SOL")

# Walk-forward: 5 folds, expanding window. On each fold, pick best (w,z) on train.
def wf_run(df, n_folds=5, min_train=400, cost_perp=PERP_ONE_WAY, cost_spot=SPOT_ONE_WAY,
           verbose=True):
    n = len(df)
    fold = max(1, (n - min_train) // n_folds)
    folds_meta, oos_rets = [], []
    windows = [30, 60, 90, 120]
    zs = [1.5, 2.0, 2.5, 3.0]
    for f in range(n_folds):
        train_end = min_train + f*fold
        test_end = min(train_end + fold, n)
        if train_end >= n or test_end <= train_end: break
        train, test = df.iloc[:train_end], df.iloc[train_end:test_end]
        # grid search on TRAIN only
        best = None
        for w in windows:
            for z in zs:
                t = signal_zfade(train, window=w, z_entry=z)
                r = basis_backtest(t, train, perp_one_way=cost_perp, spot_one_way=cost_spot)
                m = r["metrics"]
                if best is None or m.sharpe > best[0]:
                    best = (m.sharpe, w, z, m.apr)
        # apply best to TEST
        w, z = best[1], best[2]
        t_test = signal_zfade(test, window=w, z_entry=z)
        r_test = basis_backtest(t_test, test, perp_one_way=cost_perp, spot_one_way=cost_spot)
        m_test = r_test["metrics"]
        folds_meta.append(dict(fold=f, train_bars=len(train), test_bars=len(test),
                               best_w=w, best_z=z, train_sharpe=best[0],
                               test_sharpe=m_test.sharpe, test_apr=m_test.apr,
                               test_trades=m_test.n_trades, test_maxdd=m_test.max_dd))
        oos_rets.append(r_test["returns"])
        if verbose:
            print(f"  fold {f}: train={len(train)}b test={len(test)}b  best(w={w},z={z}) "
                  f"train_sharpe={best[0]:.2f} -> test_sharpe={m_test.sharpe:.2f} "
                  f"test_apr={m_test.apr*100:.1f}% test_trades={m_test.n_trades:.0f} test_maxdd={m_test.max_dd*100:.1f}%")
    oos = np.concatenate(oos_rets) if oos_rets else np.array([])
    if len(oos):
        mu = np.nan_to_num(oos).mean(); sd = np.nan_to_num(oos).std(ddof=1)
        oos_sharpe = mu/sd*np.sqrt(365) if sd>0 else 0
        oos_apr = (1+mu)**365 - 1
        # compound equity
        eq = np.cumprod(1+np.nan_to_num(oos))
        running = np.maximum.accumulate(eq)
        dd = (eq-running)/np.where(running>0,running,1)
        oos_maxdd = -dd.min()
        oos_total_ret = eq[-1]-1
    else:
        oos_sharpe=oos_apr=oos_maxdd=oos_total_ret=0
    print(f"  >> OOS concat: sharpe={oos_sharpe:.2f} APR={oos_apr*100:.1f}% maxdd={oos_maxdd*100:.1f}% total_ret={oos_total_ret*100:.1f}%")
    return dict(folds=folds_meta, oos_sharpe=oos_sharpe, oos_apr=oos_apr,
                oos_maxdd=oos_maxdd, oos_total_ret=oos_total_ret, oos_rets=oos)

print("=" * 70)
print("WALK-FORWARD — realistic taker costs (perp 20bps + spot 12bps)")
print("=" * 70)
res_taker = wf_run(df, cost_perp=PERP_ONE_WAY, cost_spot=SPOT_ONE_WAY)

print("\n" + "=" * 70)
print("WALK-FORWARD — optimistic maker costs (perp 10bps + spot 2bps)")
print("=" * 70)
res_maker = wf_run(df, cost_perp=0.0005+5e-4, cost_spot=0.0002)

# Robustness: exclude FTX crash window (Nov 2022)
print("\n" + "=" * 70)
print("ROBUSTNESS: exclude FTX crash (drop 2022-09 to 2023-03)")
print("=" * 70)
df_post = df[df.index >= "2023-04-01"].copy()
print(f"Post-FTX bars: {len(df_post)}  ({df_post.index.min().date()} -> {df_post.index.max().date()})")
res_post = wf_run(df_post, cost_perp=PERP_ONE_WAY, cost_spot=SPOT_ONE_WAY)

# Robustness: equal-weight basket across SOL/BTC/ETH (per-coin WF then sum)
print("\n" + "=" * 70)
print("ROBUSTNESS: 3-coin basket (SOL+BTC+ETH), each WF'd independently, equal-weight")
print("=" * 70)
all_oos = []
for coin in ["SOL","BTC","ETH"]:
    d = load_basis(coin)
    print(f"\n--- {coin} ---")
    r = wf_run(d, cost_perp=PERP_ONE_WAY, cost_spot=SPOT_ONE_WAY)
    all_oos.append((coin, r["oos_rets"], r["oos_sharpe"]))

# Sum equal-weight returns across the 3 coins (truncated to min length)
minlen = min(len(x[1]) for x in all_oos)
basket = np.zeros(minlen)
for _, r, _ in all_oos:
    oos = np.nan_to_num(r[:minlen])
    basket += oos/3.0
mu = basket.mean(); sd = basket.std(ddof=1)
print(f"\n3-coin basket OOS: sharpe={mu/sd*np.sqrt(365):.2f} APR={(1+mu)**365-1:+.1%}")
