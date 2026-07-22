"""Demonstrate the three-tier realism stack on real data.

1. Event engine (simple mode) == vectorized honest engine (the generalization).
2. Realism layers (impact, partial fills, latency) shave the Sharpe -> the gap.
3. DSR + PBO on the survivor pool -> the multiple-testing verdict.
4. Capacity (impact-vs-AUM) for the survivors.
5. Live-calibration self-test.
"""
import numpy as np, pandas as pd
from slate_core.backtest.data import load_cex_daily
from slate_core.backtest.honest import backtest, CEX, bars_per_year_from_index
from slate_core.backtest.event_engine import EventBacktester
from slate_core.backtest.validation import cscv_pbo, deflated_sharpe
from slate_core.backtest.calibration import simulate_live_fills, calibrate
from slate_core.backtest import strategies as S

df = load_cex_daily()
ppy = bars_per_year_from_index(df.index)
# the diversified daily portfolio members
members = {"carry": (S.carry_funding, {"thr": 0.0001}),
           "trend": (S.trend_ema_cross, {"fast": 20, "slow": 100}),
           "meanrev": (S.meanrev_rsi, {"ob": 70, "os_": 30})}

def portfolio_target(df):
    """Equal-weight blended target (each member contributes its target/3)."""
    out = np.zeros(len(df))
    for fn, p in members.values():
        out = out + np.nan_to_num(fn(df, **p)) / 3
    return out

tgt = portfolio_target(df)

print("=" * 84)
print("1. EVENT ENGINE vs VECTORIZED (simple mode must match; realism shaves it)")
print("=" * 84)
vec = backtest(tgt, df, venue=CEX)
ev_simple = EventBacktester(CEX, capital=1.0, impact=False, participation_cap=1.0,
                            liquidate_end=False).run(tgt, df)
print(f"  vectorized honest Sharpe        : {vec['metrics']['sharpe']:+.3f}")
print(f"  event engine (simple, matches)  : {ev_simple['metrics']['sharpe']:+.3f}")
# now add realism layers (taker, impact at $5M AUM, 10% participation, 1-bar latency)
ev_real = EventBacktester(CEX, capital=5e6, impact=True, participation_cap=0.10,
                          latency_bars=0).run(tgt, df)
print(f"  event engine (realistic $5M AUM): {ev_real['metrics']['sharpe']:+.3f}  "
      f"(impact_mean={ev_real['metrics']['impact_bps_mean']:.2f}bps, fills={ev_real['metrics']['n_fills']})")
print(f"  -> realism haircut: {vec['metrics']['sharpe']:.3f} -> {ev_real['metrics']['sharpe']:.3f}")

print("\n" + "=" * 84)
print("2. CAPACITY (square-root impact vs AUM) for the daily portfolio")
print("=" * 84)
print("  ", vec["metrics"]["capacity"])

print("\n" + "=" * 84)
print("3. MULTIPLE-TESTING: DSR on the survivor (547 directional trials)")
print("=" * 84)
for name, sh in [("diversified portfolio", vec['metrics']['sharpe']),
                 ("funding carry single-coin", backtest(S.carry_funding(df, thr=0.0001), df, venue=CEX)['metrics']['sharpe'])]:
    d = deflated_sharpe(sh, n_trials=547, n_bars=int(len(df)*0.4), ppy=ppy)
    print(f"  {name:28s} SR={sh:+.2f}  hurdle={d['hurdle_sharpe_annual']:.2f}  "
          f"DSR_p={d['dsr_p']:.3f}  -> {d['verdict']}")

print("\n" + "=" * 84)
print("4. PBO on the directional strategy POOL (is the selection overfit?)")
print("=" * 84)
# build a pool of ~30 daily strategy return streams (the grid survivors region)
pool = []
for fam, name, fn, params in S.expand_grid()[:30]:
    try:
        t = fn(df, **params)
        if np.nansum(np.abs(t)) > 0:
            pool.append(backtest(t, df, venue=CEX)["returns"])
    except Exception:
        pass
P = np.column_stack(pool)
pbo = cscv_pbo(P, ppy=ppy, n_groups=8)
print(f"  pool of {P.shape[1]} daily strategies: PBO={pbo['pbo']:.2f}  -> {pbo['verdict']}")

print("\n" + "=" * 84)
print("5. LIVE-CALIBRATION self-test (recovers a known impact model)")
print("=" * 84)
from slate_core.backtest.honest import Venue
truth = Venue("truth", 0, 0, 15.0, 8, 0.0, 0.4, 1.0)
res = calibrate(simulate_live_fills(truth, n=300, seed=3), CEX)
print(f"  true base=15bps k=0.40  ->  fitted base={res['base_bps']:.2f}bps "
      f"k={res['impact_k']:.3f}  R2={res['r2']:.3f}  ({res['status']})")
print(f"  feed calibrated venue back into the backtester: base={res['calibrated_venue'].slippage_bps:.1f}bps "
      f"k={res['calibrated_venue'].impact_k:.3f}")
