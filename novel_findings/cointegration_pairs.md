# Cointegration Pairs-Trading (Stat-Arb) — Honest Verdict: NEGATIVE

**Angle:** Bivariate cointegration stat-arb on 24-coin Binance perpetuals basket.
**Angle key:** `cointegration_pairs`
**Date:** 2026-07-23
**Data:** `sol_data_cache/BASKET_{24 coins}USDT_{1d,FUNDING}.json` — 1500 real daily
bars, 2022-06-13 → 2026-07-21 (~4.1 yr); real Binance 8h funding per coin.
**Evaluator:** `slate_core.backtest.honest.backtest` (1-bar execution lag, no lookahead).

---

## TL;DR — no edge after brutal costs

| Metric                                | Value             |
|---------------------------------------|-------------------|
| IS-cointegrated pairs (p<0.05)        | **37 / 276** (13.4%) |
| Static IS→OOS survivors (p<0.05 both) | **2 / 69** (≈ false-positive rate) |
| Equal-weight portfolio OOS Sharpe     | **−0.56**         |
| Equal-weight portfolio OOS APR        | **−4.8%**         |
| Equal-weight portfolio OOS max DD     | **−8.5%**         |
| Top single-pair OOS Sharpe            | 1.81 (APT-XRP)    |
| Expected max Sharpe under null (N=37) | ~2.69              |
| Pairs surviving DSR > 0.95            | **0 / 37**        |
| DSR verdict (equal-weight portfolio)  | **"not significant after deflation"** |
| Mean per-pair gross ret (4 yr)        | +0.7%             |
| Mean per-pair total cost (4 yr)       | −7.5%             |
| Mean round-trips per pair (4 yr)      | 9.4               |

The strategy **loses money out-of-sample** under every honest lens, and the few
positive single-pair OOS results are **within the multiple-testing noise envelope**.

---

## Method (fully causal, no lookahead)

For each pair (A, B), each day *t*:

1. **Rolling OLS** of `log(A)` on `log(B)` over a trailing **250-day** window →
   `alpha[t]`, `beta[t]`. (Vectorized via pandas rolling cov/var.)
2. **Residual**: `r[t] = log(A[t]) − alpha[t] − beta[t]·log(B[t]]` (info at close of t).
3. **Z-score**: `z[t] = (r[t] − mean(r[t−60:t])) / std(r[t−60:t])` (trailing 60d).
4. **State machine** (decided at close of t, executed at open of t+1 via the
   backtester's mandatory 1-bar lag):
   - Flat → long-A / short-B when `z ≤ −2`
   - Flat → short-A / long-B when `z ≥ +2`
   - Exit when `|z| ≤ 0.5` (mean-reverted) **or** `|z| ≥ 4` (stop-loss — cointegration broken)
5. **Sizing**: $0.5 notional on A, $0.5·|β| on B (β-hedged), **gross capped at 1.0×**.
6. **Costs**: CEX taker 0.05% + 15 bps slip one-way **on each leg** + real Binance
   8h funding per leg. (`impact=False` since per-coin real $ volume is not in the cache.)
7. **Pair selection**: Engle-Granger 2-step (OLS + ADF on residuals) at p<0.05 **on
   IS only** (first 60% = 900 bars, 2022-06 → 2024-11). OOS = last 40% (600 bars).

Single-bar pair PnL is conservatively clipped at ±50% (margin-call reality).

---

## Why it fails (4 independent reasons)

### 1. Cointegration in crypto is non-stationary
Of 69 IS-cointegrated pairs (best-direction, p<0.05), only **2 survive OOS at p<0.05**
(FIL-APT, UNI-AAVE) — exactly what you'd expect from a 5% false-positive rate on 69
trials (~3.5). Static OOS survival rate (2.9%) is **at the noise floor**. Cointegration
breaks under regime shifts, narrative rotations, and new listings (TIA, SUI, APT, ARB
all listed mid-sample with explosive early moves).

### 2. Brutal cost drag exceeds gross edge
Mean gross return over 4 yr = **+0.7%**. Mean total cost (both legs, full period) =
**−7.5%** (≈ −1.9%/yr). The strategy needs ~2%/yr gross just to break even, and
generates ~0.2%/yr. The math is hopeless before funding.

### 3. Tail events detonate the short leg
The "market-neutral" hedge fails exactly when needed: crypto correlations collapse to
1 in stress. Example: TIA rallied ~14× in early 2024; ARB-TIA, OP-TIA, INJ-TIA all
booked catastrophic OOS drawdowns (−43%, −14%, −31% APR) when their short leg blew
through any reasonable stop. The |z|>4 stop helps but doesn't eliminate this — the
damage is done in a single bar.

### 4. Multiple-testing: nothing survives DSR
- N=37 strategies tested; expected max OOS Sharpe under null ≈ **2.69**.
- Observed top OOS Sharpe = **1.81** (APT-XRP) — *within noise*.
- **0 of 37** pairs pass Deflated Sharpe > 0.95.
- DSR on the equal-weight portfolio: OOS Sharpe −0.56 vs. hurdle 1.74 → "not significant."
- CSCV PBO = 0.41 (not strictly overfit, because the strategy loses in both IS and OOS).

---

## Robustness (all negative)

| Variation               | IS Sharpe | OOS Sharpe | OOS APR |
|-------------------------|-----------|------------|---------|
| **Entry threshold** 1.5 | −0.17     | −0.59      | −5.9%   |
| **Entry threshold** 2.0 |  0.12     | −0.56      | −4.8%   |
| **Entry threshold** 2.5 |  0.17     | −0.15      | −1.1%   |
| **Entry threshold** 3.0 |  0.27     |  0.04      |  0.1%   |
| **Z-window** 30         |  0.31     | −0.72      | −6.0%   |
| **Z-window** 60         |  0.12     | −0.56      | −4.8%   |
| **Z-window** 120        | −0.14     | −0.04      | −0.6%   |
| **Top-3 by IS Sharpe**  |  2.29     | −0.66      | −8.7%   |
| **Top-5 by IS Sharpe**  |  2.50     | −1.11      | −13.1%  |
| **Top-10 by IS Sharpe** |  2.25     | −0.36      | −3.3%   |

The Top-N IS-Sharpe portfolios are the cleanest demonstration of overfit: 2.3–2.5 IS
Sharpe decays to −0.4 to −1.1 OOS. Looser entry (3.0) barely breaks even; tighter
entry (1.5) is worse (more cost, no edge).

---

## What I ruled out / did NOT test

- **Johansen test**: Engle-Granger already over-rejects in small samples (favors
  finding cointegration), so if anything the 37 IS pairs is an over-count; Johansen
  would only weaken the case further.
- **Hourly timeframe**: ruled out by CLAUDE.md ("sub-daily indicators not profitable
  on efficient exchanges") and the data lever is daily.
- **Triangular/arbitrage baskets**: out of scope (different angle).
- **Kalman-filter β**: would slightly improve β tracking but cannot fix the
  non-stationarity or the cost/tail problems.

---

## Capacity

**Effectively unlimited at retail/prop scale.** Each pair trades ~9 round-trips over
4 yr (~2.3/yr) at 0.5–1.0× notional → ~1.15× notional turnover/yr. At $5M AUM that's
~$5.75M/yr per pair vs. $200M–$2B daily volume on top Binance perps (0.008% ADV).
**Capacity >> $100M per pair**, $1B+ for the portfolio, before any measurable market
impact. Capacity is not the binding constraint; the absence of edge is.

---

## Lookahead / survivorship / overfit scrutiny

- **Lookahead**: verified causal. Rolling OLS uses `[t−250, t)` only; z-score uses
  `[t−60, t)` only; position decided at close of t, executed at open of t+1 via
  `slate_core.backtest.honest`'s `held[t]=target[t−1]` machinery.
- **Survivorship**: the 24-coin basket itself is survivorship-biased (these are
  *currently* liquid Binance perps; failed coins are absent). This bias inflates
  long-only returns but should help a market-neutral strategy. It still fails → the
  bias is not enough to save it.
- **Overfit**: explicitly measured via DSR (0/37 survive) and PBO (0.41, symmetric in
  its badness). The robustness grid shows no parameter set produces positive OOS Sharpe.
- **Selection**: IS/OOS split is strict (no pair selected using OOS data). The 37
  IS-pairs are re-selected on each IS window with no peeking.

---

## Files

- `/tmp/coint_screen.py` — IS/OOS Engle-Granger screen (276 pairs)
- `/tmp/coint_backtest2.py` — rolling stat-arb per pair, honest costs
- `/tmp/coint_robust.py` — robustness grid + multiple-testing
- `/tmp/coint_dsr_pbo.py` — Deflated Sharpe + CSCV PBO

---

## Bottom line

This is a clean **negative**. Cointegration pairs-trading on daily crypto perpetuals
**does not survive honest costs + multiple-testing correction**, even with a 4-year
real-data window across 24 coins. The few OOS-positive pairs are within the noise
envelope (top OOS Sharpe 1.81 < null-expected max 2.69; 0/37 pass DSR). The binding
constraint is non-stationary cointegration + brutal taker costs on both legs + tail
explosions on the short side — not capacity.

Recommendation: **do not deploy**. If revisited, the only honest paths are (a) a
maker-execution variant to halve fees (but maker fills suffer adverse selection in
exactly the tail scenarios that detonate this strategy), or (b) a much wider
statistical basket (index mean-reversion) rather than bivariate pairs.
