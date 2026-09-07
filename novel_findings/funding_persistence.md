# Funding carry with PERSISTENCE timing — verdict

**Angle key:** `funding_persistence`
**Verdict:** **marginal** (real edge, statistically significant, but too small in absolute terms to be a standalone strategy)
**Date:** 2026-07-23

---

## TL;DR

Funding rates DO autocorrelate strongly (median full-sample AR(1)=0.78, half-life
2–5 days), and the autocorrelation VARIES over time (rolling-30d AR(1) ranges
0.14→0.92). So timing carry on a persistence filter is structurally well-motivated.

Tested on real Binance perp data for 24 coins, 2022-06 → 2026-07 (~1500 days),
via the no-lookahead `slate_core.backtest.honest` evaluator (held[t]=target[t-1]):

| Variant (weekly rebalance, top-3 long/short) | OOS Sharpe | OOS APR (net) | maxDD |
|---|---|---|---|
| NAIVE carry             | +0.90 | **+0.84%** | -0.9% |
| PERSIST (AR(1)>0.5)     | **+1.39** | **+0.60%** | -0.3% |

Bootstrap 95% CI on Sharpe (block bootstrap, 2000 reps, 10d blocks):
- NAIVE   +0.90  [-0.50, +2.29], P(>0)=89%
- PERSIST +1.39  [+0.11, +2.56], P(>0)=98%

**Persistence timing DOES beat naive carry** — both on Sharpe and on maxDD — but
the absolute APR (~0.6% net) is too small to be attractive as a standalone
strategy. The edge is real (placebo z=+2.18) but tiny.

---

## Why naive carry loses (decomposition, full sample)

| Component | NAIVE (daily rebal) | PERSIST (daily) |
|---|---|---|
| Funding income | +1.18% | +0.37% |
| Gross price PnL | +1.82% | +1.54% |
| **Transaction cost** | **-11.42%** | **-2.08%** |
| NET | -8.42% | -0.17% |

Naive daily carry makes money on both funding AND price (positive), but the daily
rebalancing of a 6-name book costs 11.42% over 4 years. The persistence filter's
biggest effect is **turnover reduction** (14% occupancy → 7× less trading).

Going to **weekly rebalancing** captures most of the same turnover saving, and is
where naive carry turns slightly positive (+0.84% APR).

---

## Critical scrutiny — placebo test

The persistence filter reduces turnover. Maybe ANY mask that trades less would
do the same. To test this I generated 30 random masks with the **same average
occupancy (14.4%)** as the persistence mask, on the same OOS window:

- Persistence mask Sharpe: **+1.52**
- Placebo mean Sharpe: -0.00, std 0.70, range [-1.27, +1.20]
- **z-score of persistence vs placebo: +2.18**
- P(placebo ≥ persistence): **0%** (across 30 seeds)

Persistence is NOT just turnover reduction. The signal contains real predictive
information about which funding regimes will persist.

---

## Robustness

- **Half-life filter** (alt persistence definition): H>2d gives Sharpe +1.17
  (positive), H>3d gives +0.38, H>5d gives -0.41 (too strict). Weaker than the
  AR(1) threshold version but same sign.
- **Forecast filter (V2)**: AR(1) forecast of funding stays extreme — similar
  performance to regime filter in-sample.
- **Top-N sensitivity**: top-1 through top-5 all positive with persistence;
  top-1 has the largest persistence lift (naive -0.44 → persist +0.44).

## Capacity

Stable from $1M to $1B AUM (Sharpe 1.52 → 1.31). These are the most liquid
perps; capacity is not the binding constraint below $1B.

---

## Caveats (be skeptical)

1. **Survivorship bias**: the 24-coin basket is "still-listed" Binance perps.
   Coins delisted during 2022–2026 aren't in the sample. If those coins had
   more funding reversals, the real edge is smaller. Cannot fix without
   delisting data.
2. **Absolute APR is tiny**: 0.6% net is below money-market. Not a standalone
   strategy. Useful only as one leg of a diversified premia portfolio.
3. **Wide bootstrap CI**: PERSIST CI [+0.11, +2.56] just barely excludes zero.
   The edge could be as small as +0.1 Sharpe.
4. **In-sample tuning**: top_n=3, freq=W, tau=0.5, window=30 were chosen by
   looking at full-sample IS. Walk-forward OOS (750d, 6 folds) preserved the
   edge but the param choice was not strictly pre-registered.
5. **Funding data 2022-06 → 2023-07 missing for some coins**: the persistence
   characterization warms up over the first 30 days.
6. **24/7 funding settlement timing**: assumes funding at end-of-day applies
   to all 3 daily settlements. The honest evaluator scales by settlements/bar.

---

## Pipeline / reproducibility

Scripts (research, not committed to slate_core):
- `novel_findings/_panel.py` — panel data builder + persistence characterization
- `novel_findings/_strat.py` — naive vs persistence-timed strategy, full-sample
- `novel_findings/_decomp.py` — PnL decomposition + frequency/N sensitivity
- `novel_findings/_oos.py` — walk-forward + block bootstrap
- `novel_findings/_scrutiny.py` — placebo, capacity, robustness

Data (REAL, from Binance via `sol_data_cache/`):
- `BASKET_*_FUNDING.json` — 8h funding for 24 coins, ~3300 records each
- `BASKET_*_1d.json` — daily OHLCV for 24 coins, ~1500 records each

---

## Conclusion

**Persistence timing is a real but marginal edge.** It beats naive carry in a
statistically meaningful way (placebo z=+2.18, bootstrap P(>0)=98%, lower maxDD)
but the absolute net APR (~0.6%) is too small to deploy alone. The structural
insight — that funding autocorrelation varies and timing on it filters out the
bad (mean-reverting) funding regimes — is sound and confirmed by the data. As a
component of a diversified risk-premia portfolio (alongside e.g. spot basis,
liquidation, etc.), this could plausibly contribute a small uncorrelated return
stream. As a standalone strategy, it does not clear the bar.
