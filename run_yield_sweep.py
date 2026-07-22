"""Yield-side sweep: (A) stablecoin LP approaches, (B) emissions-farming rotation
with explicit decay correction.

REALIZED returns are computed FORWARD from the decision date, so post-selection
emissions decay is captured automatically (you select a pool at its peak
apyReward, then earn the decaying forward yield). We also quantify the 'decay
drag' = headline apyReward at selection minus the forward apyReward actually
realized during the hold — the honest number, not the marketing number.
"""
import json, glob, os
import numpy as np, pandas as pd

YP = "sol_data_cache/yield_pools"


def load_pool(pid):
    d = json.load(open(f"{YP}/{pid}.json"))
    df = pd.DataFrame(d)
    df["t"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("t").sort_index()
    df.index = df.index.tz_localize(None).normalize()
    return df[["apyBase", "apyReward", "il7d", "tvlUsd"]].apply(pd.to_numeric, errors="coerce")


def build_panel():
    summ = json.load(open(f"{YP}/_basket_summary.json"))
    stable, emiss = {}, {}
    for p in summ:
        try:
            df = load_pool(p["pool"])
            if len(df) < 60:
                continue
            df = df[~df.index.duplicated(keep="last")]
            tag = p["tag"]
            (stable if tag == "stable" else emiss)[p["pool"]] = (p, df)
        except Exception:
            pass
    return stable, emiss


def daily_net_return(df, use_il=True):
    """Realized daily LP return: (fees + emissions)/365 minus a conservative
    daily IL drag from |il7d|/7. For stables IL≈0."""
    gross = (df["apyBase"].fillna(0) + df["apyReward"].fillna(0)) / 100.0 / 365.0
    il_drag = (df["il7d"].fillna(0).abs() / 100.0 / 7.0) if use_il else 0.0
    return gross - il_drag


def stats(rets, name):
    rets = rets.dropna()
    if len(rets) < 30:
        return None
    yrs = len(rets) / 365.0
    eq = (1 + rets).prod()
    apr = eq ** (1 / yrs) - 1 if yrs > 0 and eq > 0 else float("nan")
    sd = rets.std() * np.sqrt(365)
    sh = apr / sd if sd > 0 else float("nan")
    return {"name": name, "days": len(rets), "apr": apr, "vol": sd, "sharpe": sh,
            "total": eq - 1}


def panel_ret(panel):
    """Equal-weight daily return across available pools (handles ragged panel)."""
    R = pd.DataFrame({pid: daily_net_return(df) for pid, (p, df) in panel.items()})
    return R.mean(axis=1)


def rotation(panel, select="apyReward", hold=30, topk=1, use_il=True):
    """Causal rotation: every `hold` days, rank pools by trailing-7d mean of
    `select`, hold the top-k, earn FORWARD realized net return. Returns the
    strategy return series + the decay-drag diagnostic."""
    R = pd.DataFrame({pid: daily_net_return(df, use_il) for pid, (p, df) in panel.items()})
    S = pd.DataFrame({pid: df[select].fillna(0) for pid, (p, df) in panel.items()})
    trailing = S.rolling(7, min_periods=3).mean()
    idx = R.index
    strat = pd.Series(0.0, index=idx)
    sel_apy, real_apy = [], []
    start = 7
    for t0 in range(start, len(idx) - hold, hold):
        scores = trailing.iloc[t0].dropna()
        if len(scores) == 0:
            continue
        picks = scores.sort_values(ascending=False).head(topk).index.tolist()
        window = R.iloc[t0:t0 + hold][picks]
        strat.iloc[t0:t0 + hold] = window.mean(axis=1).values
        # decay diagnostic: headline apyReward at selection vs realized during hold
        sel_headline = S.iloc[t0][picks].mean()
        realized = window.mean(axis=1).mean() * 365 * 100   # annualized % net realized
        sel_apy.append(sel_headline); real_apy.append(realized)
    return strat, np.nanmean(sel_apy), np.nanmean(real_apy)


def main():
    stable, emiss = build_panel()
    print(f"loaded: {len(stable)} stable, {len(emiss)} emissions pools")
    ppy = 365

    print("\n" + "=" * 92)
    print("PART A — STABLECOIN LP (realized net yield, fees - IL, ~zero IL)")
    print("=" * 92)
    print(f"{'pool':22s}{'chain':12s}{'apr':>8s}{'vol':>7s}{'sharpe':>8s}{'days':>6s}")
    for pid, (p, df) in stable.items():
        s = stats(daily_net_return(df), "")
        if s:
            print(f"{(p['symbol'] or '')[:21]:22s}{(p['chain'] or '')[:11]:12s}"
                  f"{s['apr']*100:7.2f}%{s['vol']*100:6.2f}%{s['sharpe']:8.2f}{s['days']:6d}")
    print("\n  -- portfolio strategies --")
    eq = panel_ret(stable)
    s = stats(eq, "equal-weight all stable pools")
    print(f"  equal-weight stable portfolio:   apr={s['apr']*100:.2f}%  sharpe={s['sharpe']:.2f}  ({s['days']}d)")
    for hold in [30, 90]:
        r, _, _ = rotation(stable, select="apyBase", hold=hold, topk=1)
        s2 = stats(r, "")
        print(f"  rotate->top stable pool/{hold}d:    apr={s2['apr']*100:.2f}%  sharpe={s2['sharpe']:.2f}  ({s2['days']}d)")

    print("\n" + "=" * 92)
    print("PART B — EMISSIONS FARMING (decay-corrected: forward realized after selection)")
    print("=" * 92)
    print(f"{'pool':22s}{'apr_net':>9s}{'mean_apyR':>10s}{'now_apyR':>9s}{'days':>6s}")
    for pid, (p, df) in emiss.items():
        s = stats(daily_net_return(df), "")
        if not s: continue
        ar_mean = df["apyReward"].mean(); ar_now = df["apyReward"].dropna().iloc[-1]
        print(f"{(p['symbol'] or '')[:21]:22s}{s['apr']*100:8.2f}%{ar_mean:9.1f}%{ar_now:8.1f}%{s['days']:6d}")
    print("\n  -- rotation strategies (the decay-corrected test) --")
    eqe = panel_ret(emiss)
    se = stats(eqe, "")
    print(f"  equal-weight emissions portfolio (buy-hold all): apr={se['apr']*100:.2f}%  sharpe={se['sharpe']:.2f}")
    for hold, k in [(30, 1), (30, 3), (7, 1)]:
        r, headline, realized = rotation(emiss, select="apyReward", hold=hold, topk=k)
        s2 = stats(r, "")
        drag = headline - realized
        print(f"  rotate->top{k} by apyReward, hold {hold:2d}d: apr={s2['apr']*100:5.2f}%  "
              f"sharpe={s2['sharpe']:.2f}  | headline_apyR={headline:4.1f}% realized={realized:4.1f}% "
              f"DECAY-DRAG={drag:4.1f}%")


if __name__ == "__main__":
    main()
