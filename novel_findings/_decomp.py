"""Decompose PnL + test rebalance frequency variants.

Questions:
  1. WHY does naive carry lose? (funding income vs price move vs cost)
  2. Does weekly rebalance (lower turnover) help?
  3. Does continuous sizing (proportional to funding × persistence) help?
"""
from __future__ import annotations
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, "/Users/gjw255/astrodata/SWARM/SLATE")
sys.path.insert(0, "/Users/gjw255/astrodata/SWARM/SLATE/novel_findings")
from slate_core.backtest import backtest, CEX, bars_per_year_from_index
from _panel import build_panel
from _strat import cross_sectional_rank_signal, naive_target, rolling_ar1, persistence_mask_v1


def decompose(target_wide, close_wide, fund_sum_wide, vol_wide, capital=1_000_000.0, impact=True):
    """Decompose aggregate PnL into funding income, gross price PnL, and cost."""
    funding_income = []
    gross_pnl = []
    cost_pnl = []
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
        m = res["metrics"]
        funding_income.append(m["total_funding"] * cap_c / capital)  # fractional of total capital
        gross_pnl.append(m["gross_ret"] * cap_c / capital)
        cost_pnl.append((m["total_cost"]) * cap_c / capital)
    return {
        "funding": sum(funding_income),
        "gross_price": sum(gross_pnl),
        "cost": sum(cost_pnl),
        "net": sum(funding_income) + sum(gross_pnl) - sum(cost_pnl),
    }


def rebalance_to_freq(daily_tgt: pd.DataFrame, freq: str = "W") -> pd.DataFrame:
    """Sample target at end of each `freq` period and forward-fill (reduces turnover)."""
    out = daily_tgt.resample(freq).last().reindex(daily_tgt.index, method="ffill")
    out = out.reindex(columns=daily_tgt.columns)
    return out.fillna(0.0)


def aggregate(target_wide, close_wide, fund_sum_wide, vol_wide, capital=1_000_000.0, impact=True):
    per_bar_rets = []
    for c in target_wide.columns:
        tgt = target_wide[c].dropna()
        if tgt.abs().sum() == 0: continue
        df = pd.DataFrame({"close": close_wide[c], "volume": vol_wide[c],
                           "funding": fund_sum_wide[c]/3.0}).dropna(subset=["close"])
        df = df.loc[df.index.intersection(tgt.index)]
        tgt = tgt.reindex(df.index).fillna(0.0)
        if len(df) < 30: continue
        cap_c = capital/24.0
        res = backtest(tgt.values, df, venue=CEX, impact=impact, capital=cap_c)
        per_bar_rets.append(pd.Series(res["returns"], index=df.index) * cap_c)
    agg = pd.concat(per_bar_rets, axis=1).sum(axis=1) / capital
    ppy = bars_per_year_from_index(agg.index)
    sharpe = agg.mean()/agg.std(ddof=1)*np.sqrt(ppy) if agg.std(ddof=1) > 0 else 0
    ann = (1+agg).prod()**(ppy/len(agg)) - 1
    eq = (1+agg).cumprod(); max_dd = float(((eq/np.maximum.accumulate(eq))-1).min())
    return {"sharpe": float(sharpe), "ann_ret": float(ann), "max_dd": max_dd, "turnover_daily": float(agg.diff().abs().mean())}


def main():
    close, fund_sum, fund_last, vol = build_panel()
    rank_signal = cross_sectional_rank_signal(fund_last)
    tgt_naive = naive_target(rank_signal, top_n=3)

    print("="*78)
    print("PnL DECOMPOSITION (full sample, $1M total capital)")
    print("="*78)
    for label, tgt in [("NAIVE carry", tgt_naive),
                       ("PERSIST v1 (tau=0.5)", tgt_naive * persistence_mask_v1(fund_last, 30, 0.5))]:
        d = decompose(tgt, close, fund_sum, vol)
        print(f"\n{label}:")
        print(f"  Funding income:   {d['funding']*100:+.2f}%")
        print(f"  Gross price PnL:  {d['gross_price']*100:+.2f}%")
        print(f"  Total cost:       {d['cost']*100:.2f}%")
        print(f"  NET:              {d['net']*100:+.2f}%")

    print("\n" + "="*78)
    print("REBALANCE FREQUENCY (naive / persist-v1-tau0.5)")
    print("="*78)
    mask = persistence_mask_v1(fund_last, 30, 0.5)
    for freq, fname in [("D","daily"), ("W","weekly"), ("2W","biweekly"), ("ME","monthly")]:
        for label, base in [("naive", tgt_naive), ("persist", tgt_naive * mask)]:
            tgt = rebalance_to_freq(base, freq=freq)
            r = aggregate(tgt, close, fund_sum, vol)
            print(f"  {fname:10s} {label:8s}: Sharpe {r['sharpe']:+.2f} | APR {r['ann_ret']*100:+.2f}% | maxDD {r['max_dd']*100:.1f}%")

    print("\n" + "="*78)
    print("TOP-N SENSITIVITY (weekly rebalance)")
    print("="*78)
    for n in [1, 2, 3, 5, 8]:
        tgt_n = naive_target(rank_signal, top_n=n)
        for label, base in [("naive", tgt_n), ("persist", tgt_n * mask)]:
            tgt = rebalance_to_freq(base, freq="W")
            r = aggregate(tgt, close, fund_sum, vol)
            print(f"  top-{n} {label:8s}: Sharpe {r['sharpe']:+.2f} | APR {r['ann_ret']*100:+.2f}% | maxDD {r['max_dd']*100:.1f}%")


if __name__ == "__main__":
    main()
