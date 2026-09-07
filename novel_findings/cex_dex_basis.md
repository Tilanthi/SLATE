# CEX<->DEX Basis Arbitrage (Binance vs Hyperliquid) — Brutal Verdict

**Angle key:** `cex_dex_basis`
**Verdict:** **NEGATIVE** (no retail-tradable edge exists at the hourly timeframe)
**Honest best APR:** approximately **-30% to -45%** (every parameterization loses heavily).
**Honest best Sharpe:** approximately **-7 to -19** (most active coin, retail taker fees).

---

## The Hypothesis

Align Binance (`BASKET_{coin}USDT_1h`) and Hyperliquid (`HYPERLIQUID_{coin}_1h`)
hourly bars on the same UTC timestamp. Compute the basis:

    basis_bps = (HL_close - Binance_close) / Binance_close * 10000

Trade it as a stat-arb: when basis is wide, go LONG the cheap venue / SHORT the
expensive venue; unwind when it reverts. The basis is mean-reverting (AR(1)
half-life 1.5–2 hours), so the gross mechanic is real — the question is whether
it survives brutal retail taker costs.

## The Real Data

| coin | bars | window | mean (bps) | std | median \|b\| | p99 \|b\| | max \|b\| |
|------|------|--------|------------|-----|--------------|-----------|-----------|
| SOL  | 5002 | 2025-12-19 → 2026-07-15 | +1.06 | 2.81 | 1.53 | 9.94 | 42.0 |
| BTC  | 5001 | 2025-12-19 → 2026-07-15 | +0.71 | 2.05 | 1.06 | 7.54 | 14.2 |
| ETH  | 5001 | 2025-12-19 → 2026-07-15 | +0.85 | 2.23 | 1.17 | 8.27 | 12.1 |

Frequency of |basis| exceeding thresholds (SOL, 5002 bars):
- > 10 bps: 0.96 % of bars
- > 20 bps: 0.04 % of bars
- > 34.5 bps (ONE-WAY taker cost): **0.04 % of bars** (~2 bars total)
- > 69 bps (ROUND-TRIP taker cost): **0.00 % of bars** (never)
- BTC/ETH never exceed 34.5 bps in the entire 7-month sample.

The basis essentially sits at the no-arbitrage band defined by venue cost
differences. By the time the hourly bar closes, faster participants have already
competed it down to ~1–3 bps.

## The Cost Wall

Mirroring `slate_core/backtest/honest.py`:

| leg | one-way taker cost |
|-----|-------------------|
| CEX (Binance) | 0.05 % fee + 15 bps slip = **20 bps** |
| DEX (HL retail) | 0.045 % fee + 10 bps slip = **14.5 bps** |
| **Round trip** (both legs × 2) | **69 bps of notional** |

Break-even: per-trade gross edge (entry=10 bps, exit=5 bps) is only **~7–9 bps**.
You need a round-trip cost below that to profit; the actual round-trip is
**~10× larger**. No realistic cost regime rescues it.

## Honest Backtest Results (1-bar execution lag; `held[t] = target[t-1]`)

### Retail taker-taker (the honest case)
| coin | entry (bps) | trades | gross % | cost % | net % | APR % | Sharpe |
|------|-------------|--------|---------|--------|-------|-------|--------|
| SOL  | 5  | 104 | +2.83 | -35.71 | **-28.04** | **-43.8** | **-18.7** |
| SOL  | 10 | 17  | +0.61 | -5.69  | **-4.96**  | **-8.5**   | **-7.1**  |
| SOL  | 15 | 3   | +0.11 | -0.86  | **-0.75**  | **-1.3**   | -2.8   |
| BTC  | 5  | 39  | +0.82 | -13.46 | **-11.88** | **-19.9**  | -11.4  |
| BTC  | 10 | 3   | +0.09 | -1.03  | **-0.94**  | **-1.6**   | -3.0   |
| ETH  | 5  | 68  | +1.88 | -23.29 | **-19.28** | **-31.3**  | -15.1  |
| ETH  | 10 | 7   | +0.30 | -2.42  | **-2.09**  | **-3.6**   | -4.8   |

Higher entry thresholds barely ever trigger (1 trade in 7 months for SOL at
entry≥20 bps; never for BTC/ETH at entry≥15 bps). Net PnL is negative across
**every** coin and **every** parameterization.

### Cost-regime sensitivity (the real test of "is there ANY edge here?")

For SOL, entry=10 bps, exit=5 bps, 17 trades:

| cost regime | cost % | net % | APR % | Sharpe |
|-------------|--------|-------|-------|--------|
| zero-cost ceiling (gross only) | 0    | +0.61 | +1.07 | +4.46 |
| maker-maker (optimistic; ignores fill risk) | -0.58 | +0.03 | +0.06 | +0.25 |
| cex-maker / dex-whale-rebate (UNREAL for retail) | -0.17 | +0.45 | +0.78 | +3.40 |
| **taker-taker (HONEST retail)** | **-5.69** | **-4.96** | **-8.52** | **-7.14** |

Even if execution were FREE, the gross edge is only ~1%/7mo (~+1% APR). With
maker pricing (still optimistic — no fill-risk modeling), it's flat. Only an
impossible "CEX-maker + DEX-whale-rebate" regime — which requires >$500M 14-day
volume on HL to unlock a -1 bps maker rebate — yields a marginal +0.8% APR, and
even that disappears once you model adverse selection on the maker fills.

## Why It Fails (the structural reason)

1. **The basis IS mean-reverting** — half-life ~1.5 hours, AR(1) ~0.65. The
   statistical property is real.
2. **But the basis magnitude is tiny** — median |basis| is 1–2 bps, well inside
   any reasonable cost band. The market is already efficient at this timescale.
3. **Round-trip cost (~69 bps) is ~10× the per-trade gross edge (~7 bps).** The
   strategy needs ~10× cost compression to break even; nothing retail achieves
   that. You would need to be a co-located HFT market-maker on BOTH venues
   simultaneously (rebate-tier HL + maker Binance + zero slippage) to clear
   single-digit bps edges — and even then the band is thin.
4. **Capital friction dominates.** A basis arb round-trip requires collateral on
   BOTH venues simultaneously. HL is non-custodial; assets must already be on
   HL. Cross-venue transfers add latency that further erodes any edge.

## Lookahead / Bias Checks

- **Lookahead:** None. Signal at bar `t` is computed from basis at `t` (close
  prices observable at end of `t`); position held during bar `t+1`. `held[t] =
  target[t-1]` exactly as in `slate_core/backtest/honest.py`.
- **Survivorship/selection:** None. SOL/BTC/ETH are the three deepest markets on
  both venues — no cherry-picking of favorable coins. The result holds across
  all three.
- **Overfitting:** None. Two parameters (entry, exit) swept; the verdict
  (negative) is monotone in cost across the entire grid — there is no
  parameterization that becomes positive under honest costs.
- **Bid-ask realism:** The hourly close prices UNDERSTATE the cost you'd face
  (no half-spread crossing included beyond the modelled 10–15 bps slippage). So
  if anything, real performance is worse than reported.

## Files

- `novel_findings/cex_dex_basis.py` — main analysis + threshold sweep
- `novel_findings/cex_dex_basis_robustness.py` — cost-regime sensitivity +
  break-even analysis

## Bottom Line

**Retail cannot arb CEX-DEX basis at the hourly timeframe.** The basis is real
and mean-reverting but lives at ~1–3 bps — firmly inside the no-arb band set by
69 bps round-trip retail taker costs. Even free execution yields <2% APR.
Single-digit-bps edges require co-located HFT infrastructure on both venues,
rebate-tier HL status, and zero slippage — none of which are available to
retail. This is consistent with both venues being deep, efficient, and already
arbitraged by professionals at sub-second timescales.

Honest verdict: **NEGATIVE.** No deployable retail edge exists here.
