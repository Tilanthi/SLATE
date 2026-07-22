"""Cross-sectional long-short alpha hunt across the altcoin basket.

This is the most literature-supported place crypto alpha actually lives: rank
coins cross-sectionally each bar, long the top of the ranking, short the bottom,
market-neutral. Low-turnover (smoothed ranks) so it survives costs. Three styles:
  * carry    : long low-funded / short high-funded
  * momentum : long winners / short losers (trailing return)
  * reversal : long losers / short winners
Honest: CEX costs, real 8h funding, IS/OOS, DSR, PBO.
"""
import json, os
import numpy as np, pandas as pd
from slate_core.backtest.honest import backtest, bars_per_year_from_index, CEX
from slate_core.backtest.validation import deflated_sharpe, cscv_pbo

CACHE = "sol_data_cache"


def load_panel():
    coins = [f[len("BASKET_"):-len("_1d.json")] for f in os.listdir(CACHE)
             if f.startswith("BASKET_") and f.endswith("_1d.json")
             and os.path.exists(f"{CACHE}/BASKET_{f[len('BASKET_'):-len('_1d.json')]}" + "_FUNDING.json")]
    coins = sorted(set(coins))
    closes, fund = {}, {}
    for c in coins:
        d = pd.DataFrame(json.load(open(f"{CACHE}/BASKET_{c}_1d.json")))
        d["t"] = pd.to_datetime(d["timestamp"]); d = d.set_index("t").sort_index()
        closes[c] = d["close"]
        fr = pd.DataFrame(json.load(open(f"{CACHE}/BASKET_{c}_FUNDING.json")))
        fr["t"] = pd.to_datetime(fr["fundingTime"], unit="ms")
        fr = fr.set_index("t").sort_index()["fundingRate"].astype(float)
        fund[c] = fr.reindex(d.index, method="ffill").fillna(0.0)
    C = pd.DataFrame(closes).dropna()          # aligned daily closes (inner)
    F = pd.DataFrame({c: fund[c].reindex(C.index).fillna(0.0) for c in coins})
    return C, F, coins


def xs_targets(panel_values, k, long_top=True):
    """Rank coins each bar; +1 to the long side, -1 to the short side.
    long_top=True -> long the HIGH-ranked (winners/high-funding); False -> long low-ranked.
    Returns dict coin -> target array."""
    V = panel_values.values
    n, m = V.shape
    order = np.argsort(V, axis=1)              # ascending: col index of lowest..highest
    tg = {c: np.zeros(n) for c in panel_values.columns}
    for t in range(n):
        lows = order[t, :k]; highs = order[t, -k:]
        for j in lows:  tg[panel_values.columns[j]][t] = +1 if not long_top else -1
        for j in highs: tg[panel_values.columns[j]][t] = -1 if not long_top else +1
    return tg


def backtest_xs(C, F, targets, is_frac=0.6):
    coins = list(targets.keys())
    rets = {}
    for c in coins:
        sub = pd.DataFrame({"close": C[c].values, "funding": F[c].values}, index=C.index)
        rets[c] = backtest(targets[c], sub, venue=CEX)["returns"]
    minl = min(len(r) for r in rets.values())
    R = np.column_stack([r[:minl] for r in rets.values()])
    port = R.mean(axis=1)                       # equal-weight, long+short nets out
    ppy = bars_per_year_from_index(C.index)
    k = int(minl * is_frac)
    oos = port[k:]
    osh = oos.mean() / oos.std() * ppy**.5 if oos.std() else 0
    ish = port[:k].mean() / port[:k].std() * ppy**.5 if port[:k].std() else 0
    return {"is_sh": ish, "oos_sh": osh, "oos_ret": float((1+np.nan_to_num(oos)).prod()-1),
            "oos_returns": oos, "ppy": ppy, "oos_bars": len(oos),
            "turnover": float(np.mean(np.abs(np.diff(np.sign(R.mean(1)), prepend=0))))}


def main():
    C, F, coins = load_panel()
    print(f"basket panel: {len(coins)} coins, {len(C)} aligned daily bars, "
          f"{C.index[0].date()} -> {C.index[-1].date()}")
    print("=" * 90)
    print("CROSS-SECTIONAL LONG-SHORT (market-neutral, CEX daily, honest costs)")
    print("=" * 90)
    n_trials = 9
    pool = []
    for style, k, smooth in [("carry", 4, 3), ("momentum", 4, 7), ("momentum", 4, 30),
                             ("reversal", 4, 3), ("reversal", 4, 7),
                             ("value(dev)", 4, 30)]:
        if style == "carry":
            sig = F.rolling(smooth).mean()
            tg = xs_targets(sig, k, long_top=False)   # long low-funding, short high
        elif style == "momentum":
            sig = C.pct_change(smooth)
            tg = xs_targets(sig, k, long_top=True)    # long winners, short losers
        elif style == "reversal":
            sig = C.pct_change(smooth)
            tg = xs_targets(sig, k, long_top=False)   # long losers, short winners
        else:  # value: deviation from MA
            sig = (C / C.rolling(smooth).mean() - 1.0)
            tg = xs_targets(sig, k, long_top=False)   # long oversold, short overbought
        r = backtest_xs(C, F, tg)
        d = deflated_sharpe(r["oos_sh"], n_trials=n_trials, n_bars=r["oos_bars"], ppy=r["ppy"])
        flag = "SIG" if d["dsr_p"] > 0.95 else "ns"
        print(f"  [{flag}] {style:14s} k={k} smooth={smooth:3d}  "
              f"IS={r['is_sh']:+.2f} OOS={r['oos_sh']:+.2f}  ret={r['oos_ret']:+.2%}  "
              f"DSR_p={d['dsr_p']:.3f}")
        pool.append(r["oos_returns"])
    # PBO across the styles
    P = np.column_stack([np.pad(p, (0, max(0, max(len(x) for x in pool)-len(p))), 'constant')
                         for p in pool])
    # trim to common length
    minl = min(len(p) for p in pool)
    Pc = np.column_stack([p[:minl] for p in pool])
    pbo = cscv_pbo(Pc, ppy=365, n_groups=8)
    print(f"\n  PBO across cross-sectional styles: {pbo['pbo']:.2f} -> {pbo['verdict']}")


if __name__ == "__main__":
    main()
