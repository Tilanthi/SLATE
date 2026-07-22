"""(1) Bracket the MM rebate result across optimistic/realistic/adverse fills.
(2) Build an HONEST diversified portfolio of the weak daily edges (carry + trend
    + mean-reversion) and measure whether diversification lifts Sharpe to
    significance — the regime-switch idea, but evaluated honestly.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from slate_core.backtest.data import load_cex_daily, load_cex_hourly
from slate_core.backtest.honest import backtest, bars_per_year_from_index, CEX
from slate_core.backtest.market_maker import mm_backtest
from slate_core.backtest import strategies as S
from run_deep_analysis import bootstrap_sharpe_ci


def strat_ret(df, fn, params, venue=CEX, is_frac=0.6):
    t = fn(df, **params)
    r = backtest(t, df, venue=venue)
    k = int(len(df) * is_frac)
    return r["returns"], k


def main():
    df = load_cex_daily()
    ppy = bars_per_year_from_index(df.index)

    # ---- (1) MM fill-model bracket on CEX SOL hourly (best config hs=0.003) ----
    print("=" * 80)
    print("1. MARKET-MAKER fill-model bracket (CEX SOL 1h, hs=0.003, mp=1, sk=0)")
    print("=" * 80)
    hr = load_cex_hourly()
    for fa in ["quote", "realistic", "adverse"]:
        r = mm_backtest(hr, half_spread=0.003, max_pos=1, inv_skew=0.0,
                        fill_at=fa, venue=CEX)
        k = int(len(hr) * 0.6)
        oos = r["returns"][k:]
        ci = bootstrap_sharpe_ci(oos, ppy)
        sig = "SIG" if ci[0] > 0 else "ns"
        print(f"  [{sig}] fill_at={fa:9s}: OOS_sh={r['sharpe']:+.2f}  "
              f"CI=[{ci[0]:+.2f},{ci[2]:+.2f}]  ret={r['total_ret']:+.2%}  "
              f"fills={r['n_fills']}")

    # ---- (2) honest diversified daily portfolio ----
    print("\n" + "=" * 80)
    print("2. DIVERSIFIED DAILY PORTFOLIO (cex_daily, 1080 bars 2023-2026)")
    print("=" * 80)
    # fixed, a-priori params (not cherry-picked per fold) for each edge family
    members = {
        "carry_trend":  (S.carry_funding,        {"thr": 0.0001}),
        "trend_ema":    (S.trend_ema_cross,      {"fast": 20, "slow": 100}),
        "meanrev_rsi":  (S.meanrev_rsi,          {"ob": 70, "os_": 30}),
        "meanrev_z":    (S.meanrev_zscore,       {"lb": 20, "z": 2.0}),
        "trend_donch":  (S.breakout_donchian,    {"lb": 55}),
    }
    streams, k = {}, int(len(df) * 0.6)
    print(f"\n  {'member':14s} {'IS_sh':>7s} {'OOS_sh':>7s} {'OOS_ret':>8s} {'OOS_ci95':>8s}")
    for name, (fn, p) in members.items():
        rets, _ = strat_ret(df, fn, p)
        is_sh = rets[:k].mean()/rets[:k].std()*ppy**.5 if rets[:k].std() else 0
        oos = rets[k:]
        ci = bootstrap_sharpe_ci(oos, ppy)
        streams[name] = rets
        print(f"  {name:14s} {is_sh:+7.2f} {oos.mean()/oos.std()*ppy**.5:+7.2f} "
              f"{float(np.sum(oos)):+8.2%} {ci[2]:+8.2f}")
    # correlation matrix (OOS)
    R = pd.DataFrame({n: streams[n][k:] for n in streams})
    print(f"\n  OOS correlation matrix:\n{R.corr().round(2).to_string()}")
    # equal-weight portfolio (sum/3 of the 3 distinct families: carry, trend, meanrev)
    for combo_name, picks in [("carry+trend+meanrev", ["carry_trend", "trend_ema", "meanrev_rsi"]),
                              ("all_5", list(members.keys()))]:
        minl = min(len(streams[n]) for n in picks)
        P = np.zeros(minl)
        for n in picks:
            P += streams[n][:minl] / len(picks)
        oos = P[k:]
        ci = bootstrap_sharpe_ci(oos, ppy)
        sig = "SIG" if ci[0] > 0 else "ns"
        eq = np.cumprod(1 + np.nan_to_num(P))
        print(f"\n  PORTFOLIO [{combo_name}]: IS={P[:k].mean()/P[:k].std()*ppy**.5:+.2f}  "
              f"OOS_sh={oos.mean()/oos.std()*ppy**.5:+.2f}  CI=[{ci[0]:+.2f},{ci[2]:+.2f}]  "
              f"ret={float(eq[-1]-1):+.2%}  maxdd={float(-(eq/np.maximum.accumulate(eq)-1).min()):.2f}")


if __name__ == "__main__":
    main()
