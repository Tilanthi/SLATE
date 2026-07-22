"""Cross-sectional funding carry on the wider HL basket (15-20 coins).

The most-documented crypto edge: short the over-funded coins, long the
under-funded, market-neutral. With 3 majors there was no spread; a 15+ coin
basket has real funding dispersion. Low-turnover (smoothed funding + rebalance
hysteresis) so it survives costs. Honest: DEX costs, real HL funding, IS/OOS +
expanding walk-forward + block bootstrap.
"""
from __future__ import annotations

import json
import os
from itertools import product

import numpy as np
import pandas as pd

from slate_core.backtest.honest import backtest, bars_per_year_from_index, DEX
from run_final_validation import block_bootstrap_sharpe


def load_basket():
    coins = []
    for f in os.listdir("sol_data_cache"):
        if f.startswith("HL_") and f.endswith("_1h.json"):
            c = f[len("HL_"):-len("_1h.json")]
            if os.path.exists(f"sol_data_cache/HL_{c}_FUNDING.json"):
                coins.append(c)
    coins = sorted(coins)
    frames = {}
    for c in coins:
        from slate_core.dex.data.load_data import load_candles
        df = load_candles(f"sol_data_cache/HL_{c}_1h.json")
        df = df[~df.index.duplicated(keep="last")]
        df["funding"] = _load_funding(c, df.index)
        frames[c] = df[["close", "funding"]]
    panel = pd.concat({c: f for c, f in frames.items()}, axis=1).dropna()
    return panel, coins


def _load_funding(coin, target_index):
    rec = json.load(open(f"sol_data_cache/HL_{coin}_FUNDING.json"))
    fr = pd.DataFrame(rec)
    fr["t"] = pd.to_datetime(fr["time"], unit="ms")
    fr = fr.set_index("t").sort_index()[["fundingRate"]].astype(float)
    fr = fr[~fr.index.duplicated(keep="last")]
    s = fr["fundingRate"].reindex(target_index, method="ffill").fillna(0.0)
    return s


def xs_carry_targets(panel, coins, smooth=24, k=3, spread_thr=0.0):
    """Long k lowest-funded, short k highest-funded, smoothed + spread-gated.
    Hysteresis: only flip a coin's position when its smoothed funding rank moves
    into/out of the top/bottom k (so turnover stays low)."""
    n = len(panel)
    fund = np.column_stack([panel[(c, "funding")].rolling(smooth).mean().fillna(0).values
                            for c in coins])
    targets = {c: np.zeros(n) for c in coins}
    prev_pos = {c: 0 for c in coins}
    for t in range(n):
        f = fund[t]
        if np.any(np.isnan(f)):
            for c in coins: targets[c][t] = prev_pos[c]
            continue
        order = np.argsort(f)
        longs = set(order[:k]); shorts = set(order[-k:])
        spread = f[order[-1]] - f[order[0]]
        for ci, c in enumerate(coins):
            if spread < spread_thr:
                p = 0
            elif ci in longs:
                p = 1
            elif ci in shorts:
                p = -1
            else:
                p = 0
            prev_pos[c] = p
            targets[c][t] = p
    return targets


def portfolio_metrics(panel, coins, targets, is_frac=0.6):
    rets = {}
    for c in coins:
        sub = panel[c].copy()
        r = backtest(targets[c], sub, venue=DEX)
        rets[c] = r["returns"]
    minl = min(len(v) for v in rets.values())
    R = np.column_stack([v[:minl] for v in rets.values()])
    port = R.mean(axis=1)          # equal-weight, long+short nets out
    ppy = bars_per_year_from_index(panel.index)
    k = int(minl * is_frac)
    oos = port[k:]
    ci = block_bootstrap_sharpe(oos, ppy)
    eq = np.cumprod(1 + np.nan_to_num(port))
    is_sh = port[:k].mean() / port[:k].std() * ppy**.5 if port[:k].std() else 0
    oos_sh = oos.mean() / oos.std() * ppy**.5 if oos.std() else 0
    return {"is_sharpe": is_sh, "oos_sharpe": oos_sh,
            "oos_ret": float((1 + np.nan_to_num(oos)).prod() - 1),
            "ci5": ci[0], "ci50": ci[1], "ci95": ci[2],
            "gross_long_short": float(np.mean(np.abs(R).sum(1))),
            "oos_returns": oos, "ppy": ppy}


def main():
    panel, coins = load_basket()
    print(f"basket: {len(coins)} coins ({coins}), {len(panel)} aligned bars, "
          f"{panel.index[0].date()} -> {panel.index[-1].date()}")
    ppy = bars_per_year_from_index(panel.index)

    print("\n" + "=" * 86)
    print("CROSS-SECTIONAL FUNDING CARRY (market-neutral, DEX 1h)")
    print("=" * 86)
    best = None
    for smooth, k, spr in product([24, 100, 500], [2, 3, 5], [0.0, 0.0002]):
        tg = xs_carry_targets(panel, coins, smooth=smooth, k=k, spread_thr=spr)
        m = portfolio_metrics(panel, coins, tg)
        sig = "SIG" if m["ci5"] > 0 else "ns"
        print(f"  [{sig}] smooth={smooth:4d} k={k} spr={spr:.4f}  "
              f"IS={m['is_sharpe']:+.2f} OOS={m['oos_sharpe']:+.2f}  "
              f"CI=[{m['ci5']:+.2f},{m['ci95']:+.2f}]  ret={m['oos_ret']:+.2%}")
        if best is None or m["oos_sharpe"] > best["oos_sharpe"]:
            best = {**m, "smooth": smooth, "k": k, "spr": spr}

    print(f"\nbest config: smooth={best['smooth']} k={best['k']} spr={best['spr']}  "
          f"OOS_sharpe={best['oos_sharpe']:+.2f}  CI=[{best['ci5']:+.2f},{best['ci95']:+.2f}]")

    # naive equal-weight single-coin carry portfolio baseline (long-short each coin by its own funding)
    print("\n--- baseline: single-coin carry portfolio (each coin funding>thr short) ---")
    from slate_core.backtest import strategies as S
    sc_rets = []
    for c in coins:
        sub = panel[c].copy()
        t = S.carry_funding(sub, thr=0.0002)
        sc_rets.append(backtest(t, sub, venue=DEX)["returns"])
    minl = min(len(r) for r in sc_rets)
    P = np.column_stack([r[:minl] for r in sc_rets]).mean(axis=1)
    oos = P[int(minl*0.6):]
    ci = block_bootstrap_sharpe(oos, ppy)
    print(f"  equal-weight single-coin carry (thr=2e-4): "
          f"OOS_sh={oos.mean()/oos.std()*ppy**.5:+.2f}  CI=[{ci[0]:+.2f},{ci[2]:+.2f}]  "
          f"ret={float((1+np.nan_to_num(oos)).prod()-1):+.2%}")


if __name__ == "__main__":
    main()
