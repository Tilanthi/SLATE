"""Final honest validation of the best candidate (diversified daily portfolio)
and the MM rebate bracket. This is the evidence base for the report.

Tests applied to any survivor before it can be called 'real':
  * per-calendar-year Sharpe (consistency across regimes, not just one window)
  * stationary BLOCK bootstrap 90% CI (preserves return autocorrelation)
  * walk-forward stability (each fold positive?)
  * cost-sensitivity (does it survive 2x costs?)
  * param robustness (is it an artifact of one parameter set?)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from slate_core.backtest.data import load_cex_daily, load_cex_hourly
from slate_core.backtest.honest import backtest, bars_per_year_from_index, CEX
from slate_core.backtest.market_maker import mm_backtest
from slate_core.backtest import strategies as S


def block_bootstrap_sharpe(returns, ppy, n=2000, bl=20, seed=0):
    """Stationary block bootstrap (block length bl) preserving autocorrelation."""
    rng = np.random.RandomState(seed)
    m = len(returns)
    if m < bl * 3:
        return (0, 0, 0)
    rets = np.asarray(returns)
    shs = []
    for _ in range(n):
        idx = (rng.randint(0, m - bl) + np.arange(bl)) if rng.random() > 0 else None
        # build a resample of length m by concatenating random blocks
        out = []
        while len(out) < m:
            start = rng.randint(0, m - 1)
            length = rng.geometric(1 / bl)
            out.extend(rets[start:start + length].tolist())
        s = np.array(out[:m])
        sd = s.std(ddof=1)
        shs.append(s.mean() / sd * np.sqrt(ppy) if sd > 0 else 0)
    return tuple(np.percentile(shs, q) for q in (5, 50, 95))


def portfolio_returns(df, members, venue=CEX):
    streams = {}
    for name, (fn, p) in members.items():
        streams[name] = backtest(fn(df, **p), df, venue=venue)["returns"]
    minl = min(len(v) for v in streams.values())
    P = np.zeros(minl)
    for v in streams.values():
        P += v[:minl] / len(streams)
    return P


def main():
    df = load_cex_daily()
    ppy = bars_per_year_from_index(df.index)
    idx = df.index

    members = {
        "carry":     (S.carry_funding,     {"thr": 0.0001}),
        "trend":     (S.trend_ema_cross,   {"fast": 20, "slow": 100}),
        "meanrev":   (S.meanrev_rsi,       {"ob": 70, "os_": 30}),
    }
    P = portfolio_returns(df, members)
    eq = np.cumprod(1 + np.nan_to_num(P))

    print("=" * 82)
    print("DIVERSIFIED DAILY PORTFOLIO — final honest validation (cex_daily, 3yr)")
    print("  carry(funding thr=0.0001) + trend(ema 20/100) + meanrev(rsi 70/30), equal-weight")
    print("=" * 82)
    full_sh = P.mean() / P.std(ddof=1) * np.sqrt(ppy)
    print(f"  full-sample Sharpe={full_sh:+.2f}  total_ret={float(eq[-1]-1):+.2%}  "
          f"max_dd={float(-(eq/np.maximum.accumulate(eq)-1).min()):.2f}")

    print("\n  --- per-calendar-year Sharpe (consistency across regimes) ---")
    yr = pd.Series(P, index=idx).groupby(idx.year)
    for y, s in yr:
        sd = s.std(ddof=1)
        sh = s.mean() / sd * np.sqrt(ppy) if sd > 0 else 0
        print(f"    {y}: Sharpe={sh:+.2f}  ret={float((1+s).prod()-1):+.2%}  bars={len(s)}")

    print("\n  --- block-bootstrap 90% CI (full sample) ---")
    ci = block_bootstrap_sharpe(P, ppy)
    print(f"    Sharpe CI=[{ci[0]:+.2f}, {ci[1]:+.2f}, {ci[2]:+.2f}]  "
          f"{'SIG(>0)' if ci[0] > 0 else 'not significant'}")

    print("\n  --- walk-forward stability (5 expanding folds, fixed a-priori params) ---")
    n = len(P); min_tr = int(n*0.4); fold = (n-min_tr)//5
    for f in range(5):
        te = min_tr + f*fold; ts = min(te+fold, n)
        seg = P[te:ts]
        sd = seg.std(ddof=1)
        sh = seg.mean()/sd*np.sqrt(ppy) if sd>0 else 0
        print(f"    fold {f} ({idx[te].date()}->{idx[ts-1].date()}): Sharpe={sh:+.2f}  ret={float((1+seg).prod()-1):+.2%}")

    print("\n  --- cost sensitivity (multiply fees+slippage) ---")
    for mult in [1.0, 1.5, 2.0]:
        # re-run with scaled slippage (fee side fixed at venue; approximate via slippage)
        slip = (CEX.taker_fee*mult + CEX.slippage_bps*mult)  # scale both
        # recompute portfolio returns at higher cost via a venue override
        from slate_core.backtest.honest import Venue
        v = Venue("cex_x", maker_fee=CEX.maker_fee*mult, taker_fee=CEX.taker_fee*mult,
                  slippage_bps=CEX.slippage_bps*mult, funding_interval_hours=8)
        Pm = portfolio_returns(df, members, venue=v)
        eqm = np.cumprod(1+np.nan_to_num(Pm))
        print(f"    {mult:.1f}x costs: Sharpe={Pm.mean()/Pm.std()*ppy**.5:+.2f}  "
              f"ret={float(eqm[-1]-1):+.2%}")

    print("\n  --- param robustness (perturb each member's params) ---")
    perturbs = {
        "carry thr 0.00005/0.0002": {"carry": (S.carry_funding, {"thr": 0.00005}),
                                      "trend": members["trend"], "meanrev": members["meanrev"]},
        "carry thr 0.0002":         {"carry": (S.carry_funding, {"thr": 0.0002}),
                                      "trend": members["trend"], "meanrev": members["meanrev"]},
        "trend 10/200":             {"carry": members["carry"],
                                      "trend": (S.trend_ema_cross, {"fast":10,"slow":200}),
                                      "meanrev": members["meanrev"]},
        "trend 50/200":             {"carry": members["carry"],
                                      "trend": (S.trend_ema_cross, {"fast":50,"slow":200}),
                                      "meanrev": members["meanrev"]},
        "rsi 65/35":                {"carry": members["carry"], "trend": members["trend"],
                                      "meanrev": (S.meanrev_rsi, {"ob":65,"os_":35})},
    }
    for label, mem in perturbs.items():
        Pr = portfolio_returns(df, mem)
        print(f"    {label:26s}: Sharpe={Pr.mean()/Pr.std()*ppy**.5:+.2f}  "
              f"ret={float((1+np.nan_to_num(Pr)).prod()-1):+.2%}")

    # ---- MM slippage bracket ----
    print("\n" + "=" * 82)
    print("MARKET-MAKER rebate — slippage bracket (CEX SOL 1h, hs=0.003, mp=1)")
    print("=" * 82)
    hr = load_cex_hourly()
    for slip in [0, 3, 5, 10]:
        r = mm_backtest(hr, half_spread=0.003, max_pos=1, inv_skew=0.0,
                        extra_slip_bps=slip, venue=CEX)
        ci = block_bootstrap_sharpe(r["returns"][int(len(hr)*0.6):], ppy)
        sig = "SIG" if ci[0] > 0 else "ns"
        print(f"  [{sig}] +{slip:2d}bps slip: Sharpe={r['sharpe']:+.2f}  "
              f"CI=[{ci[0]:+.2f},{ci[2]:+.2f}]  ret={r['total_ret']:+.2%}")


if __name__ == "__main__":
    main()
