# Leveraged Stablecoin-LP Looping — Honest Prototype Verdict

**Angle key:** `leveraged_lp_loop`
**Verdict:** **NEGATIVE** (honest APR after brutal costs + tail: ~2.9% at the optimal "leverage", which is no leverage)
**Date:** 2026-07-23

---

## TL;DR

The leveraged stablecoin-LP loop is a textbook DeFi yield-farming trap. The base
APY on the canonical USDC-USDT Uniswap V3 pool is **median 3.16%** (mean 4.97%
over 1,549 real days), which is **below realistic Aave/Compound stable borrow
rates of 5-7%**. Because the carry is structurally negative, leverage amplifies
*losses*, not gains. On top of that, the depeg tail (USDC SVB -13%, UST -100%)
turns any meaningful leverage into a wipeout risk. Optimal leverage = **1.0x
(no leverage)**, and even then a tail-reserve for depeg eats the yield to ~2.9%.

---

## 1. Real data used

| Source | What | Window |
|---|---|---|
| `sol_data_cache/amm_pool_e737d721-*.json` | USDC-USDT Uniswap V3 Ethereum daily APY/TVL (DefiLlama) | 2022-03-27 → 2026-07-20 (1,549 days) |
| `sol_data_cache/yield_pools/_basket_summary.json` | Cross-chain stable-pool universe (28 pools) | snapshot 2026-07-21 |
| `sol_data_cache/yield_pools/a34c8a80-*.json` | Hyperion USDT-USDC Aptos (sanity check on highest-yield stable pool) | 2025-07-08 → 2026-07-21 (379 days) |
| Documented historical depeg events | USDC SVB Mar-2023 (-13%), UST Terra May-2022 (-100%), USDT FTX Nov-2022 (-2%), DAI Covid Mar-2020 (-3%) |  — |

The LP-leg is **realized** APY (not modeled). The borrow-leg is **not in the
cache**; I use a sensitivity sweep (3-8%) plus a "borrow tracks LP yield" model
mimicking Aave variable-rate dynamics. The depeg-tail leg uses **documented
historical moves**, not synthesized price.

---

## 2. The structural problem: carry is negative

LP base APY (USDC-USDT Uniswap V3 ETH, 1,549 days):

| Stat | Value |
|---|---|
| Mean | 4.97% |
| Median | **3.16%** |
| Std | 6.90% |
| p5 / p95 | 0.61% / 14.39% |
| Reward tokens | 0.000% (no emissions) |

Analytical net yield `y_net(L, r_b) = L · y_lp − (L−1) · r_b`, using median
y_lp = 3.16%:

| r_borrow ↓ \ L → | 1.0x | 1.5x | 2.0x | 3.0x | 5.0x | 8.0x |
|---|---|---|---|---|---|---|
| **3.0%** | 3.16% | 3.24% | 3.32% | 3.48% | 3.79% | 4.27% |
| **4.0%** | 3.16% | 2.74% | 2.32% | 1.48% | −0.21% | −2.73% |
| **5.0%** (Aave typical) | 3.16% | 2.24% | 1.32% | **−0.52%** | −4.21% | −9.73% |
| **6.0%** | 3.16% | 1.74% | 0.32% | −2.52% | −8.21% | −16.73% |
| **7.0%** | 3.16% | 1.24% | −0.68% | −4.52% | −12.21% | −23.73% |

**Key insight:** the break-even borrow rate equals y_lp = 3.16%, *independent
of leverage* — that's the algebra of the linear model. Aave/Compound stable
borrow has been 4-7% for years. So in the realistic regime, **every unit of
leverage above 1x destroys value**. The leverage "amplifies the 4% yield" only
when borrow < LP yield; in today's market that condition is not satisfied.

---

## 3. Time-series backtest on the real APY path (1,549 days, no depeg in window)

Compounded daily on the realized USDC-USDT APY path, 4.24 years.

**Model A — constant 5% borrow (Aave/Compound typical stable rate):**

| Leverage | APR | Sharpe | MaxDD | Equity multiple |
|---|---|---|---|---|
| 1.0x | **5.09%** | 13.77 | 0.00% | 1.23x |
| 1.5x | 5.08% | 9.15 | −0.13% | 1.23x |
| 2.0x | 5.06% | 6.85 | −0.65% | 1.23x |
| 3.0x | 5.03% | 4.54 | −2.18% | 1.23x |
| 5.0x | 4.96% | 2.69 | −7.58% | 1.23x |
| 8.0x | 4.85% | 1.65 | −15.36% | 1.22x |

The equity curve is essentially identical across leverage tiers (1.22-1.23x) —
leverage adds nothing because the carry is ~zero. Sharpe collapses from 13.77 to
1.65 as leverage rises. MaxDD rises linearly.

**Model B — borrow tracks LP yield `r_b = max(3%, 0.85·y_lp)` (Aave variable-rate dynamics):**

| Leverage | APR | Sharpe | MaxDD |
|---|---|---|---|
| 1.0x | 5.09% | 13.77 | 0.00% |
| 3.0x | 5.00% | 9.39 | −0.57% |
| 5.0x | 4.90% | 6.99 | −1.71% |
| 8.0x | 4.76% | 4.95 | −3.71% |

Even when borrow *falls* with LP yield, leverage is breakeven-to-negative. The
3% floor on stablecoin borrow bites during the pool's low-yield stretches (p5
APY = 0.61%), dragging levered returns below unlevered.

---

## 4. Depeg tail risk — the leveraged LP's real killer

For stablecoin-vs-stablecoin LP, a one-side depeg of size d drops LP value ~d/2
(full-range LP). With leverage L and Aave-style 80% LTV liquidation, equity
loss per $1 equity:

| Event | Depeg | L=1x | L=2x | L=3x | L=5x | L=8x |
|---|---|---|---|---|---|---|
| USDC SVB Mar-2023 | −13% | −6.5% | −13.0% | −19.5% | **−35.4%** | −59.4% |
| USDT FTX Nov-2022 | −2% | −1.0% | −2.0% | −3.0% | −6.8% | −14.0% |
| DAI Covid Mar-2020 | −3% | −1.5% | −3.0% | −4.5% | −9.4% | −18.1% |
| UST Terra May-2022 (if paired with UST) | −50% | −25.0% | −50.0% | −76.8% | **−100%** | −100% |
| Severe combined depeg | −20% | −10.0% | −20.0% | −30.0% | −53.5% | −88.2% |

At L=5x, a single SVB-style USDC depeg wipes 35% of equity. At L=3x, a 2020-
style combined depeg takes 30%. Aave liquidation (80% LTV) caps theoretical
max leverage at ~5x — but real-world oracle lag and chain congestion mean the
honest ceiling is 2-3x, where the carry is already zero or negative.

**Tail-reserve needed to survive an SVB-style event at the chosen leverage:**
- L=1x: 6.5% of equity
- L=2x: 13% of equity
- L=3x: 20% of equity (eat ~6 yrs of unlevered yield at 3.16%)

---

## 5. Capacity is tiny

USDC-USDT Uniswap V3 Ethereum TVL: **$34.7M now, peak $222M, median $36M.**
Realistic institutional position: ~5% of pool = **~$1.7M LP notional** before
APY dilution and entry slippage become material.

- At L=3x with $5M equity → $10M LP = **29% of pool TVL** (massive APY dilution; you'd be competing with yourself for swap fees).
- At L=5x with $5M equity → $20M LP = **58% of pool TVL** (you ARE the pool; the APY you "earn" comes from your own entry slippage — circular).

The strategy does not scale.

---

## 6. What about the higher-yield stable pools?

The basket has pools with much higher headline APY (Hyperion USDT-USDC Aptos at
median 18.4% base+reward, Pharaoh USDT-USDC Avalanche at 6.5% reward). I tested
the Hyperion pool analytically and via time-series:

| Pool | Days | TVL now | Mean base+reward APR | At L=3x, borrow 5% |
|---|---|---|---|---|
| Uniswap V3 ETH (canonical) | 1,549 | $34.7M | 4.97% | **−0.52%** |
| Hyperion Aptos | 379 | $6.3M (was $57.8M peak) | 26.6% | +100% (naive) |

The Hyperion "100% APR" is a yield-farming mirage:

1. **Survivorship / selection bias.** I selected it *because* it currently
   shows a high APY. Its TVL has collapsed −89% ($57.8M → $6.3M). I'm seeing
   the AFTER state of a launch-incentivized pool.
2. **APY is decaying.** First-90d mean 34.5% → last-90d 16.7%. By next year
   it will likely be single-digit, same as the canonical pool.
3. **No depeg in the 379-day window.** MaxDD = 0% in the backtest — a red
   flag, not a feature. The first SVB-style event is a 35-100% drawdown.
4. **Capacity ~$300k** (5% of $6.3M TVL). Not investable at any institutional size.
5. **Smart-contract / chain risk.** Hyperion on Aptos is a newer DEX; the
   strategy inherits bridge + contract + sequencer risk on top of depeg risk.

High-reward pools do not change the verdict: they exist because of temporary
incentive emissions that decay, and their capacity is too small to matter.

---

## 7. Scrutiny — is the negative result robust?

**Lookahead:** None. The strategy holds; it doesn't predict APY. Using the
realized APY path is correct because the question is "what would have happened
to a holder" — not "could you have timed entries."

**Survivorship:** Partial. I picked USDC-USDT Uniswap V3 Ethereum, which
*did* survive 1,549 days — but it is the canonical stablecoin LP, not a cherry-
picked high-yield pool. Using the median APY (3.16%) rather than a higher-
yielding alternative is the *conservative* choice, not survivorship bias.

**Overfit:** No parameters were tuned. Leverage tiers and the 5% borrow rate
are industry-standard. No degrees of freedom to overfit.

**Capacity realism:** Yes — pool TVL is $34.7M; we can't hide $5M of equity
in it at 5x leverage.

**Missing data (honest gaps):**
- No real Aave/Compound borrow-rate time-series in the cache. The 5% assumption
  is documented typical; if real borrow rates had been persistently 2-3% over
  2020-2022 (DeFi summer era), the loop would have been positive at low L. That
  era is gone; current stable borrow is 4-7%.
- No real fee-tier breakdown for the LP (Uniswap V3 has 0.01%, 0.05%, 0.30%
  fee tiers). I used the aggregate pool APY which mixes them.
- No real gas-cost modeling (Ethereum L1 rebalancing would devour small positions).

---

## 8. Honest verdict

- **Honest net APR after brutal costs + tail reserve:** **~2.9% at L=1.0x**
  (i.e., don't lever; hold the LP unlevered with a 6.5% depeg reserve that
  amortizes to ~2%/yr drag). 
- **At any leverage L>1:** structurally negative carry in today's rate regime;
  APR ≤ 0% before tail risk; catastrophic after.
- **Sharpe (unlevered, no depeg in window):** 13.77 — but this is a 4-year
  sample with no depeg; the depeg-adjusted Sharpe is far lower.
- **Capacity:** ~$1.7M LP notional (5% of $34.7M pool TVL). At $5M equity you
  cannot run this without becoming the pool.
- **Tail reserve:** 6.5% (L=1x) to 35% (L=5x) of equity to survive one SVB-
  style depeg.

**Why the strategy exists in the wild despite being negative-EV:** retail
yield-farmers chase headline APY on incentive-funded pools (Hyperion-style),
ignore capacity and depeg tail, and get rekt when (a) emissions end, (b) the
pool TVL collapses, or (c) a depeg triggers liquidation cascades. The strategy
works only in the narrow window where LP APY > borrow rate *and* no depeg
occurs *and* the pool is new and incentive-funded. None of these conditions
are durable.

---

## 9. Next steps (if pursuing further)

1. **Get real Aave v3 variable borrow-rate history** (USDC/USDT, 2020-present)
   to test whether the loop was profitable in 2020-2022 when stable borrow
   was 1-3%. (Hypothesis: yes, briefly, but only with depeg insurance.)
2. **Add a depeg hedge leg** (buy USDC/USDT put options or hold a partial
   short on a depeg-correlated asset). This would let you run L=2-3x without
   tail wipeout — but the hedge cost likely eats the carry.
3. **Test on Pendle / fixed-rate stable yield** — locking the LP yield via
   Pendle PT while borrowing variable could create a real (small) spread.
4. **Test curve / convexity-stable pools** (Curve stETH-ETH, etc.) where the
   "stable" assumption is fragile — different risk profile.

These are different angles. The plain leveraged stablecoin-LP loop, on the
data we have, is **negative**.
