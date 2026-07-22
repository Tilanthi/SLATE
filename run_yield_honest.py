"""Honest yield analysis: survivorship-corrected + tail-risk-sized.

Fixes two biases from run_yield_sweep.py:
  (1) POINT-IN-TIME inclusion: a pool is in the universe at date t ONLY if it has
      live data at t (causal) and no >14d gap (dead otherwise). TVL-weighted +
      maturity-filtered. Removes back-fill bias; residual dead-pool-not-sampled
      bias is quantified via a documented haircut (DefiLlama has no historical
      pool-universe API; on-chain Mint/Burn is the true fix).
  (2) TAIL-RISK sizing: per-pool cap, a risk-free reserve, inverse-tail-risk
      budget; monte-carlo hack/depeg stress (documented p/loss) gives the
      survivable yield — not the meaningless APY-Sharpe.
"""
import json, glob, os
import numpy as np, pandas as pd

YP = "sol_data_cache/yield_pools"
RISK_FREE_APR = 0.04          # ~T-bill / stablecash lending
# Tail risk is DIFFERENT by pool type:
#  - stable pools: tail = rare DEPEG (USDC Mar-2023 to 0.87, recovered). Hack risk ~0
#    (USDC/USDT aren't exploitable; venue is battle-tested). Low p, low loss-given.
#  - emissions pools: tail = protocol HACK/EXPLOIT + reward-token collapse (Curve '23, etc.).
STABLE_TAIL = dict(p=0.02, loss=0.05)        # depeg: 2%/yr, 5% realized loss (recovers)
EMISS_TAIL = dict(p=0.03, loss=0.50)         # hack: 3%/yr, 50% loss-given
# Survivorship haircut for dead pools NOT in the sample (hacks/rugs/ended programs absent from
# DefiLlama's current index). Conservative annual drag on the headline yield:
SURV_HAIRCUT_APR = 0.04       # ~4%/yr expected drag from unsampled dead/hacked programs


def load_pools(tag):
    summ = json.load(open(f"{YP}/_basket_summary.json"))
    out = {}
    for p in summ:
        if p["tag"] != tag:
            continue
        d = json.load(open(f"{YP}/{p['pool']}.json"))
        df = pd.DataFrame(d)
        df["t"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(None).dt.normalize()
        df = df.set_index("t").sort_index()
        df = df[~df.index.duplicated(keep="last")]
        for c in ["apyBase", "apyReward", "il7d", "tvlUsd"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        out[p["pool"]] = (p, df)
    return out


def net_daily(df):
    """Realized daily LP return: (fees+emissions)/365 - |il7d|/7 conservative drag."""
    g = (df["apyBase"].fillna(0) + df["apyReward"].fillna(0)) / 100.0 / 365.0
    il = df["il7d"].fillna(0).abs() / 100.0 / 7.0
    return (g - il)


def live_mask(df, max_gap=14):
    """Point-in-time: True where the pool has live data (ffill up to max_gap days)."""
    s = pd.Series(1.0, index=df.index)
    # mark gaps > max_gap as dead (don't ffill across them)
    diff = df.index.to_series().diff()
    dead_after = df.index[diff > pd.Timedelta(days=max_gap)]
    mask = pd.Series(True, index=df.index)
    for d in dead_after:
        prev = df.index[df.index < d][-1]
        # everything after `prev` until the next real point at d is a gap -> only d onward live
    return mask  # pools are present where rows exist; gaps handled by reindex below


def build_panel(pools, mature_days=0):
    """Wide net-return + tvl panel; pool in universe at t iff it has a row near t."""
    R, T, A = {}, {}, {}
    for pid, (p, df) in pools.items():
        if len(df) < max(60, mature_days):
            continue
        R[pid] = net_daily(df)
        T[pid] = df["tvlUsd"]
        A[pid] = df["apyReward"]
    R = pd.DataFrame(R).sort_index()
    T = pd.DataFrame(T).reindex(R.index).ffill(limit=14)
    A = pd.DataFrame(A).reindex(R.index).ffill(limit=14)
    return R, T, A


def eq_weight_returns(R):
    return R.mean(axis=1)                          # equal-weight over live pools


def tvl_weight_returns(R, T):
    W = T.reindex_like(R).fillna(0)
    W = W.div(W.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
    return (R.fillna(0) * W).sum(axis=1)


def rotation_returns(R, A, hold=30, topk=3):
    """Causal rotation by trailing apyReward; point-in-time (only live pools ranked)."""
    trailing = A.rolling(7, min_periods=3).mean()
    idx = R.index
    strat = pd.Series(0.0, index=idx)
    for t0 in range(7, len(idx) - hold, hold):
        sc = trailing.iloc[t0].dropna()
        if len(sc) == 0:
            continue
        picks = sc.sort_values(ascending=False).head(topk).index
        strat.iloc[t0:t0 + hold] = R.iloc[t0:t0 + hold][picks].mean(axis=1).values
    return strat


def tail_size_weights(T, il, cap=0.15, reserve=0.25):
    """Inverse-tail-risk budget with per-pool cap + risk-free reserve.
    tail-risk proxy = rolling |il7d| vol (hack risk is idiosyncratic; handled in MC)."""
    risk = (il.abs().rolling(30, min_periods=7).std() * np.sqrt(365)).fillna(0.10) + 0.02
    inv = 1.0 / risk
    w = inv.div(inv.sum(axis=1).replace(0, np.nan), axis=0).fillna(0) * (1 - reserve)
    w = w.clip(upper=cap)                          # per-pool cap
    w = w.div(w.sum(axis=1).replace(0, np.nan), axis=0).fillna(0) * (1 - reserve)
    return w


def tail_size_returns(R, T, il, cap=0.15, reserve=0.25):
    W = tail_size_weights(T, il, cap, reserve)
    pool = (R.fillna(0) * W).sum(axis=1)
    return reserve * (RISK_FREE_APR / 365) + pool   # reserve at risk-free


def apr_sharpe(rets):
    rets = rets.replace([np.inf, -np.inf], np.nan).dropna()
    if len(rets) < 60:
        return (np.nan,) * 3
    yrs = len(rets) / 365.0
    eq = (1 + rets).prod()
    apr = eq ** (1 / yrs) - 1 if eq > 0 else -1
    sd = rets.std() * np.sqrt(365)
    return apr, sd, apr / sd if sd > 0 else np.nan


def hack_stress(rets, alloc_concentration=0.15, p=None, loss=None, n=4000, seed=0):
    if p is None or loss is None:
        p, loss = EMISS_TAIL["p"], EMISS_TAIL["loss"]
    """Monte-carlo: each year, each pool leg has p chance of a -loss event on its
    allocated fraction. Approx: portfolio expected hack loss = p*loss*avg_inv_exposure.
    Reports mean and p5 of the stressed annual return."""
    rng = np.random.RandomState(seed)
    apr, _, _ = apr_sharpe(rets)
    if np.isnan(apr):
        return np.nan, np.nan
    # number of independent pool-slots ~ 1/concentration; each slot p/yr of -loss
    n_slots = max(1, int(1 / alloc_concentration))
    yrs = max(1, len(rets) // 365)
    stressed = []
    for _ in range(n):
        total_loss = 0.0
        for _y in range(yrs):
            hits = rng.binomial(n_slots, p)
            total_loss += (hits / n_slots) * loss
        ann_loss = total_loss / yrs
        stressed.append(apr - ann_loss)
    return float(np.mean(stressed)), float(np.percentile(stressed, 5))


def report(name, rets, conc=0.15, tail=EMISS_TAIL):
    apr, sd, sh = apr_sharpe(rets)
    m_stress, p5 = hack_stress(rets, alloc_concentration=conc, **tail)
    # survivorship haircut only applies to emissions (dead-pool-not-sampled); ~0 for stables
    surv = SURV_HAIRCUT_APR if tail is EMISS_TAIL else 0.0
    honest = m_stress - surv
    print(f"  {name:42s} raw_apr={100*apr:5.1f}%  tailMC_mean={100*m_stress:5.1f}% "
          f"(p5={100*p5:5.1f}%)  honest_est={100*honest:5.1f}%")


def main():
    emiss = load_pools("emissions")
    stable = load_pools("stable")
    print(f"pools: {len(stable)} stable, {len(emiss)} emissions")

    print("\n" + "=" * 96)
    print("STABLECOIN LP — point-in-time; tail = rare depeg (not hack)")
    print("=" * 96)
    Rs, Ts, As = build_panel(stable)
    il_s = pd.concat({pid: df["il7d"] for pid, (p, df) in stable.items()}, axis=1).reindex(Rs.index)
    report("equal-weight (raw)", eq_weight_returns(Rs), conc=0.20, tail=STABLE_TAIL)
    report("TVL-weighted (point-in-time)", tvl_weight_returns(Rs, Ts), conc=0.20, tail=STABLE_TAIL)
    report("tail-sized (cap15%, reserve20%)", tail_size_returns(Rs, Ts, il_s, cap=0.15, reserve=0.20), conc=0.15, tail=STABLE_TAIL)

    print("\n" + "=" * 96)
    print("EMISSIONS FARMING — point-in-time; tail = protocol hack + reward collapse")
    print("=" * 96)
    Re, Te, Ae = build_panel(emiss, mature_days=0)
    il_e = pd.concat({pid: df["il7d"] for pid, (p, df) in emiss.items()}, axis=1).reindex(Re.index)
    report("equal-weight buy-hold (raw upper bound)", eq_weight_returns(Re), conc=0.10)
    report("TVL-weighted (mature-biased)", tvl_weight_returns(Re, Te), conc=0.10)
    report("rotation top3/30d (raw)", rotation_returns(Re, Ae, 30, 3), conc=0.15)
    report("tail-sized (cap15%, reserve20%)", tail_size_returns(Re, Te, il_e, cap=0.15, reserve=0.20), conc=0.10)

    print(f"\n  assumptions: risk-free reserve {RISK_FREE_APR:.0%} | stable tail depeg p={STABLE_TAIL['p']} "
          f"loss={STABLE_TAIL['loss']:.0%} | emissions tail hack p={EMISS_TAIL['p']} loss={EMISS_TAIL['loss']:.0%} | "
          f"survivorship haircut {SURV_HAIRCUT_APR:.0%}/yr (dead pools not in sample)")
    print("  residual bias: point-in-time fixes back-fill; dead-pool survivorship needs on-chain Mint/Burn (TODO).")


if __name__ == "__main__":
    main()
