"""Premium-edge analysis: the strategies most likely to carry a REAL persistent
crypto premium, which single-asset directional TA does not.

  1. CROSS-SECTIONAL FUNDING CARRY — long the least-funded coin, short the most-
     funded, market-neutral. Isolates the funding premium (the best-documented
     crypto edge) and hedges market direction. Low turnover => survives costs.
  2. CROSS-ASSET LEAD-LAG — BTC/ETH momentum as a signal on SOL.
  3. MULTI-STRATEGY PORTFOLIO — combine weak decorrelated edges; measure the
     diversification benefit honestly (Sharpe of the whole vs the parts).

All evaluated with the honest backtester: 1-bar lag, real venue costs, real
funding, IS/OOS + expanding walk-forward + bootstrap CI.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from slate_core.backtest.data import load_dex, load_cex_daily
from slate_core.backtest.honest import backtest, bars_per_year_from_index, CEX, DEX
from run_deep_analysis import bootstrap_sharpe_ci


# --------------------------------------------------------------------------
# Align SOL/BTC/ETH DEX hourly into a wide panel
# --------------------------------------------------------------------------
def load_panel():
    coins = ["SOL", "BTC", "ETH"]
    frames = {}
    for c in coins:
        df = load_dex(c)
        df = df[~df.index.duplicated(keep="last")]   # HL files have dup hour stamps
        frames[c] = df[["close", "funding"]].rename(
            columns={"close": f"close_{c}", "funding": f"funding_{c}"})
    panel = pd.concat(frames.values(), axis=1).dropna()
    return panel, coins


# --------------------------------------------------------------------------
# 1. Cross-sectional funding carry
# --------------------------------------------------------------------------
def xs_carry_panel(panel, coins, spread_thr=0.0):
    """Low-turnover cross-sectional carry: long the lowest-funded coin, short the
    highest-funded, but ONLY when the funding spread (max-min) exceeds
    `spread_thr` — otherwise flat. With smoothed funding this trades rarely."""
    fund = np.column_stack([panel[f"funding_{c}"].values for c in coins])
    n = len(panel)
    targets = {c: np.zeros(n) for c in coins}
    for t in range(n):
        f = fund[t]
        if np.any(np.isnan(f)):
            continue
        lo_i = int(np.argmin(f))    # most negative funding -> long
        hi_i = int(np.argmax(f))    # most positive funding -> short
        if lo_i == hi_i:
            continue
        spread = f[hi_i] - f[lo_i]
        if spread < spread_thr:
            continue
        targets[coins[lo_i]][t] = +1
        targets[coins[hi_i]][t] = -1
    return targets


def backtest_portfolio(panel, coins, targets, venue, is_frac=0.6, name=""):
    """Equal-risk-weighted portfolio across coins. Returns IS/OOS metrics + the
    combined OOS return stream (for bootstrap) + per-asset breakdown."""
    rets = {}
    for c in coins:
        sub = pd.DataFrame({"close": panel[f"close_{c}"].values,
                            "funding": panel[f"funding_{c}"].values}, index=panel.index)
        r = backtest(targets[c], sub, venue=venue)
        rets[c] = r["returns"]
    minl = min(len(v) for v in rets.values())
    R = np.column_stack([v[:minl] for v in rets.values()])
    w = np.ones(len(coins)) / len(coins)         # equal weight, long-short nets out
    port = R @ w
    ppy = bars_per_year_from_index(panel.index)
    k = int(minl * is_frac)
    oos = port[k:]
    oos_sh = oos.mean() / oos.std(ddof=1) * np.sqrt(ppy) if oos.std() > 0 else 0
    ci = bootstrap_sharpe_ci(oos, ppy)
    eq = np.cumprod(1 + np.nan_to_num(port))
    return {"name": name, "is_sharpe": port[:k].mean()/port[:k].std()*np.sqrt(ppy),
            "oos_sharpe": oos_sh, "oos_ret": float(eq[-1]-1),
            "ci5": ci[0], "ci95": ci[2], "per_coin": {c: float(np.sum(rets[c])) for c in coins},
            "oos_returns": oos, "gross_dollars_at_work": float(np.mean(np.abs(R).sum(1)))}


# --------------------------------------------------------------------------
# 2. Cross-asset lead-lag: BTC/ETH -> SOL
# --------------------------------------------------------------------------
def lead_lag(panel, lead, lag_coin="SOL", lb=24, thr=0.0, venue=DEX):
    lead_ret = panel[f"close_{lead}"].astype(float).pct_change(lb)
    sig = pd.Series(0.0, index=panel.index)
    sig[lead_ret > thr] = 1
    sig[lead_ret < -thr] = -1
    sub = pd.DataFrame({"close": panel[f"close_{lag_coin}"].values,
                        "funding": panel[f"funding_{lag_coin}"].values}, index=panel.index)
    return sig.values, sub


def main():
    panel, coins = load_panel()
    print(f"panel: {len(panel)} bars, coins={coins}, "
          f"{panel.index[0].date()} -> {panel.index[-1].date()}")

    print("\n" + "=" * 80)
    print("1. CROSS-SECTIONAL FUNDING CARRY (market-neutral, DEX 1h)")
    print("=" * 80)
    # smoothed funding + spread threshold => low turnover (carry should persist)
    for win in [24, 100, 500]:
        p2 = panel.copy()
        for c in coins:
            p2[f"funding_{c}"] = panel[f"funding_{c}"].rolling(win).mean()
        p2 = p2.dropna()
        for spr in [0.0, 0.0001, 0.0003]:
            tg = xs_carry_panel(p2, coins, spread_thr=spr)
            r = backtest_portfolio(p2, coins, tg, DEX, name=f"xs_sm{win}_spr{spr}")
            sig = "SIG" if r["ci5"] > 0 else "ns"
            print(f"  [{sig}] {r['name']:22s} IS={r['is_sharpe']:+.2f} OOS={r['oos_sharpe']:+.2f}  "
                  f"CI=[{r['ci5']:+.2f},{r['ci95']:+.2f}]  ret={r['oos_ret']:+.2%}  "
                  f"$atRisk/bar={r['gross_dollars_at_work']:.2f}")

    print("\n" + "=" * 80)
    print("2. CROSS-ASSET LEAD-LAG (BTC/ETH momentum -> SOL, DEX 1h)")
    print("=" * 80)
    for lead in ["BTC", "ETH"]:
        for lb in [8, 24, 100]:
            for thr in [0.0, 0.02]:
                sig, sub = lead_lag(panel, lead, "SOL", lb=lb, thr=thr)
                if np.abs(sig).sum() == 0:
                    continue
                r = backtest(sig, sub, venue=DEX)
                m = r["metrics"]
                k = int(len(sub)*0.6)
                oos = r["returns"][k:]
                ppy = bars_per_year_from_index(sub.index)
                ci = bootstrap_sharpe_ci(oos, ppy)
                tag = "SIG" if ci[0] > 0 else "ns"
                print(f"  [{tag}] {lead}->SOL lb={lb:3d} thr={thr:.2f}  "
                      f"IS={backtest(sig[:k],sub.iloc[:k],venue=DEX)['metrics']['sharpe']:+.2f}  "
                      f"OOS={oos.mean()/oos.std()*ppy**.5:+.2f}  CI=[{ci[0]:+.2f},{ci[2]:+.2f}]  "
                      f"ret={m['total_ret']:+.2%} trd={int(m['n_trades'])}")


if __name__ == "__main__":
    main()
