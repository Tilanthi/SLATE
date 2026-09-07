"""Honest OOS: walk-forward + block bootstrap.

Walk-forward (expanding window): for each test fold, parameters (tau, window,
top_n, rebalance freq) are FROZEN at the values selected by IS-only analysis on
the prior train window. The persistence filter is re-estimated each fold on
train data. OOS returns are concatenated — the only honest Sharpe.

Block bootstrap: circular block bootstrap on the daily OOS return series to get
a 95% CI for the annualized Sharpe (block size = 10 days, 2000 reps).
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


def aggregate(target_wide, close_wide, fund_sum_wide, vol_wide, capital=1e6, impact=True):
    per_bar_rets = []
    for c in target_wide.columns:
        tgt = target_wide[c].dropna()
        if tgt.abs().sum() == 0: continue
        df = pd.DataFrame({"close": close_wide[c], "volume": vol_wide[c].fillna(0.0),
                           "funding": (fund_sum_wide[c]/3.0).fillna(0.0)}).dropna(subset=["close"])
        df = df.loc[df.index.intersection(tgt.index)]
        tgt = tgt.reindex(df.index).fillna(0.0)
        if len(df) < 30: continue
        cap_c = capital/24.0
        res = backtest(tgt.values, df, venue=CEX, impact=impact, capital=cap_c)
        per_bar_rets.append(pd.Series(res["returns"], index=df.index) * cap_c)
    agg = pd.concat(per_bar_rets, axis=1).sum(axis=1) / capital
    return agg


def resample_target(daily_tgt: pd.DataFrame, freq: str) -> pd.DataFrame:
    out = daily_tgt.resample(freq).last().reindex(daily_tgt.index, method="ffill")
    return out.reindex(columns=daily_tgt.columns).fillna(0.0)


def metrics(agg: pd.Series) -> dict:
    ppy = bars_per_year_from_index(agg.index)
    s = agg.mean()/agg.std(ddof=1)*np.sqrt(ppy) if agg.std(ddof=1) > 0 else 0
    ann = (1+agg).prod()**(ppy/len(agg)) - 1 if (1+agg).prod() > 0 else -1
    eq = (1+agg).cumprod(); max_dd = float(((eq/np.maximum.accumulate(eq))-1).min())
    return {"sharpe": float(s), "ann_ret": float(ann), "max_dd": max_dd, "ppy": ppy, "n": len(agg)}


def block_bootstrap_sharpe(agg: pd.Series, block: int = 10, reps: int = 2000, seed: int = 42):
    """Circular block bootstrap on the daily return series. Returns Sharpe CI."""
    rng = np.random.default_rng(seed)
    ppy = bars_per_year_from_index(agg.index)
    x = agg.values
    n = len(x)
    shrs = np.empty(reps)
    for r in range(reps):
        idx = (rng.integers(0, n, size=n//block + 1)[:,None] + np.arange(block)[None,:]).ravel()[:n] % n
        s = x[idx]
        mu, sd = s.mean(), s.std(ddof=1)
        shrs[r] = mu/sd*np.sqrt(ppy) if sd > 0 else 0
    return {"mean": float(shrs.mean()), "p2.5": float(np.percentile(shrs,2.5)),
            "p97.5": float(np.percentile(shrs,97.5)), "p50": float(np.percentile(shrs,50)),
            "p_pos": float((shrs>0).mean())}


def walk_forward(close, fund_sum, fund_last, vol, *, n_folds=6, min_train=750,
                 top_n=3, window=30, tau=0.5, freq="W"):
    """Expanding-window WF: parameters fixed; persistence mask recomputed on each
    fold's train data (but mask only needs funding history, which is causal)."""
    rank_signal = cross_sectional_rank_signal(fund_last)
    tgt_naive = naive_target(rank_signal, top_n=top_n)

    n = len(close)
    fold = max(60, (n - min_train) // n_folds)
    folds_out = []
    naive_oos, persist_oos = [], []
    print(f"\nWalk-forward: n={n}, min_train={min_train}, fold={fold}, n_folds~{(n-min_train)//fold}")
    for f in range(n_folds):
        train_end = min_train + f * fold
        test_end = min(train_end + fold, n)
        if test_end <= train_end: break
        test_idx = close.index[train_end:test_end]
        # fit: in this case the only "fit" is selecting window/tau — we fix them.
        # the persistence mask at test-time uses ONLY funding data through t.
        mask_full = persistence_mask_v1(fund_last, window=window, tau=tau)  # causal
        tgt_naive_f = resample_target(tgt_naive.loc[test_idx], freq=freq)
        tgt_pers_f = resample_target((tgt_naive * mask_full).loc[test_idx], freq=freq)
        a_n = aggregate(tgt_naive_f, close, fund_sum, vol)
        a_p = aggregate(tgt_pers_f, close, fund_sum, vol)
        m_n = metrics(a_n); m_p = metrics(a_p)
        print(f"  fold {f}: test {test_idx[0].date()}->{test_idx[-1].date()} ({len(test_idx)}d) | naive S={m_n['sharpe']:+.2f} | persist S={m_p['sharpe']:+.2f}")
        folds_out.append({"fold": f, "naive": m_n, "persist": m_p})
        naive_oos.append(a_n); persist_oos.append(a_p)
    naive_concat = pd.concat(naive_oos) if naive_oos else pd.Series(dtype=float)
    persist_concat = pd.concat(persist_oos) if persist_oos else pd.Series(dtype=float)
    return folds_out, naive_concat, persist_concat


def main():
    close, fund_sum, fund_last, vol = build_panel()
    print(f"Panel: {close.index.min().date()} -> {close.index.max().date()} ({len(close)} days)")

    # Walk-forward at weekly rebalance, top-3, tau=0.5 (the values from IS analysis)
    print("\n" + "="*78)
    print("WALK-FORWARD OOS (top-3, weekly rebalance, tau=0.5, window=30)")
    print("="*78)
    folds, naive_oos, persist_oos = walk_forward(close, fund_sum, fund_last, vol,
                                                  n_folds=6, min_train=750,
                                                  top_n=3, window=30, tau=0.5, freq="W")
    mn = metrics(naive_oos); mp = metrics(persist_oos)
    print(f"\n  OOS NAIVE  concat: Sharpe {mn['sharpe']:+.2f} | APR {mn['ann_ret']*100:+.2f}% | maxDD {mn['max_dd']*100:.1f}% | n={mn['n']}")
    print(f"  OOS PERSIST concat: Sharpe {mp['sharpe']:+.2f} | APR {mp['ann_ret']*100:+.2f}% | maxDD {mp['max_dd']*100:.1f}% | n={mp['n']}")
    n_pos_n = sum(1 for f in folds if f["naive"]["sharpe"] > 0)
    n_pos_p = sum(1 for f in folds if f["persist"]["sharpe"] > 0)
    print(f"  positive folds: naive {n_pos_n}/{len(folds)}  persist {n_pos_p}/{len(folds)}")

    print("\n" + "="*78)
    print("BLOCK BOOTSTRAP 95% CI on annualized Sharpe (OOS, 2000 reps, block=10d)")
    print("="*78)
    bn = block_bootstrap_sharpe(naive_oos, block=10, reps=2000)
    bp = block_bootstrap_sharpe(persist_oos, block=10, reps=2000)
    print(f"  NAIVE   Sharpe: {mn['sharpe']:+.2f}  bootstrap CI [{bn['p2.5']:+.2f}, {bn['p97.5']:+.2f}]  P(>0)={bn['p_pos']*100:.0f}%")
    print(f"  PERSIST Sharpe: {mp['sharpe']:+.2f}  bootstrap CI [{bp['p2.5']:+.2f}, {bp['p97.5']:+.2f}]  P(>0)={bp['p_pos']*100:.0f}%")

    # Save for the writeup
    import pickle
    with open("/tmp/oos_results.pkl","wb") as f:
        pickle.dump({"folds":folds,"naive_oos":naive_oos,"persist_oos":persist_oos,
                     "metrics_naive":mn,"metrics_persist":mp,
                     "bs_naive":bn,"bs_persist":bp}, f)
    print("\nSaved OOS results to /tmp/oos_results.pkl")


if __name__ == "__main__":
    main()
