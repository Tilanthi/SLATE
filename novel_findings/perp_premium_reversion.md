# Perp Premium / Basis Mean-Reversion — Honest Verdict: NEGATIVE

**Angle key:** `perp_premium_reversion`
**Verdict:** `negative` — real mean-reversion exists statistically but is NOT tradeable
at retail CEX costs. Walk-forward OOS Sharpe **-2.00**, APR **-2.1%/yr**.
**Date:** 2026-07-23

---

## The hypothesis (genuine, not on the ruled-out list)

When a perpetual trades at an extreme premium/discount to spot, fade it: the
basis mean-reverts as cash-and-carry arbers carry it back. **Distinct from the
ruled-out list:** the signal is the **perp-minus-spot price gap** (the basis), not
the funding rate (naive carry), not EMA/trend, not mean-reversion on price.

## Real data used (no synthesis)

- **Spot reference:** freshly fetched real Binance **SPOT** klines for SOL/BTC/ETH
  (`sol_data_cache/SPOT_BINANCE_NOVELFINDINGS.json`, 2022-06-01→2026-07-22, 1,513
  bars each). Verified as SPOT via the `/api/v3/klines` endpoint, distinct from the
  perp feed.
- **Perp price:** existing cached `BASKET_{SOL,BTC,ETH}USDT_1d.json` (Binance
  perp, 1,500 bars 2022-06-13→2026-07-21).
- **Funding:** `BASKET_*_FUNDING.json` (real Binance 8h funding incl. `markPrice`).
- Cross-checked: Binance `markPrice` (composite spot index) tracks the traded
  spot price within a few bps — the basis is real, not a feed artifact.

## Honest backtester (custom, mirrors `slate_core.backtest.honest` principles)

- **1-bar decision lag** (no lookahead): `held[t] = target[t-1]`.
- **Causal z-score**: rolling mean/std over a window that **ends at** bar t
  (inclusive); position held during t+1.
- **Delta-neutral execution**: long basis = long perp + short spot; short basis =
  short perp + long spot. PnL per bar = `held · (perp_ret − spot_ret) + funding`.
- **Brutal costs on BOTH legs:** perp taker 0.05% + 15bps slip = **20bps
  one-way**; spot taker 0.10% + 2bps slip = **12bps one-way**. Round-trip = **64
  bps per entry/exit** (32 bps × 2 legs × 2 sides).
- **Real funding carry** (perp side only): `-rate · 3_settlements/day · held`.

## Statistical fact: the basis DOES mean-revert

Forward 1-day basis change by current z-score bucket (SOL, 1,500 days):

| z-bucket    | fwd Δbasis (bps) | n     |
|-------------|------------------|-------|
| z < -2      | **+12.2**        | 290   |
| -2 < z < -1 | +0.8             | 1,900 |
| -1 < z < 0  | +0.7             | 5,020 |
| 0 < z < 1   | -0.7             | 5,000 |
| 1 < z < 2   | -2.0             | 1,730 |
| z > 2       | **-4.2**         | 460   |

Monotone reversion is real. **But:** average reversion is 12 bps/day at the
extremes, while round-trip cost is 64 bps. You need the trade to stay on ~5–10
days to amortize cost, during which the basis usually normalizes and the carry
stops paying.

## Walk-forward results (the only honest Sharpe)

Expanding-window 5-fold walk-forward, re-fitting (window, z-entry) on each
fold's train, evaluated OOS. SOL only (BTC/ETH basis std is just 3–4bps — even
less tradeable):

| Cost regime                       | OOS Sharpe | OOS APR | OOS MaxDD |
|-----------------------------------|------------|---------|-----------|
| Taker (perp 20bps + spot 12bps)   | **-2.00**  | -2.1%   | 6.4%      |
| Optimistic maker (perp 10 + spot 2)| -0.15     | -0.1%   | 1.8%      |
| Exclude FTX window                | -2.10      | -1.4%   | 3.1%      |
| 3-coin basket (SOL+BTC+ETH)       | -3.23      | -2.0%   | —         |

**Every configuration loses money out of sample.** Even at maker fees that
assume unrealistic fill reliability.

## The smoking gun: it's a crisis-only artefact

Decomposing the in-sample PnL by period (best in-sample config: w=120, z=3):

| Period                    | Gross PnL | Net PnL |
|---------------------------|-----------|---------|
| FTX window (121 days)     | **+16.5%**| **+15.9%**|
| All other 1,379 days      | +1.55%    | **-6.5%**|

The strategy's entire positive expectation comes from the Nov 2022–Mar 2023
FTX-collapse dislocation (SOL basis hit **-1,690bps** on 2022-11-09). Outside
that one crisis, **the strategy loses 6.5% net over 4 years**. This is not an
edge — it is a single historical accident.

Additional negative results:
- **Conditional entry** (basis extreme AND funding aligned): 5–11 trades total,
  uniformly negative (Sharpe -0.9 to -1.7). Doesn't help.
- **Soft tanh sizing**: best variant Sharpe +0.10 (one config) — disappears
  after walk-forward.
- **BTC/ETH**: basis std is only 3-4bps (vs SOL 44bps). No chance at retail
  costs; walk-forward Sharpe -2.3 to -2.7.

## Per-trade economics (why it fails)

Best in-sample config (w=120, z=3), taker costs, 18 trades over 4 years:

- Average gross profit per trade: **~100 bps** (basis reversion)
- Average funding carry per trade: ~+16 bps
- Average cost per trade: **~64 bps** (round trip, both legs)
- Net per trade: ~+50 bps — but **variance is huge** (some +500bps, many -50bps)
- Over 18 trades: 18% gross − 12% cost + 3% funding = ~9% total over 4 years
  = **~2%/yr gross of fees, ~0%/yr at realistic taker costs**, and **negative
  OOS**.

## Capacity

**Not the binding constraint.** Only 5 entries/year; SOL daily spot+perp volume
>$1B. At $5M AUM each entry is <0.5% of daily volume, well below the 15bps-slip
regime already priced in. Capacity is >$50M. The binding constraint is that the
edge itself is ~0 even at zero impact.

## Why this fails (economic reasoning)

1. **Basis arb is the most competitive trade in crypto.** HFT firms and
   exchange-internal MMs with sub-5bps all-in costs (rebates + colo + internal
   matching) dominate it. Retail at 64bps round-trip is structurally excluded.
2. **The reversion we measure IS the reversion captured by those lower-cost
   arbers.** They are the mechanism. We're trying to ride the wake of faster,
   cheaper money.
3. **Funding is the COST of carrying basis, not a bonus.** When basis is very
   negative (perp at discount), funding goes negative (shorts pay longs), which
   helps a long-basis trade — but the funding is itself a *consequence* of the
   basis dislocation, already priced.
4. **Crisis dependence is fatal.** An edge that fires only during market
   dislocations (FTX, 3AC, Luna) is not a strategy — it's a short-vol position
   disguised as a basis trade. The "alpha" is just rare-event insurance
   underwriting without the premium.

## Verdict

**NEGATIVE.** Honest walk-forward OOS: APR **-2.1%**, Sharpe **-2.00**. The
statistical basis mean-reversion is real but is captured entirely by lower-cost
arbers; at retail CEX costs there is no tradeable edge. The in-sample illusion
comes entirely from the FTX-collapse window.

## What would change the verdict (untestable with current data)

- **VIP/wholesale fee tier** (<5bps all-in): walk-forward APR likely swings to
  +1–3%/yr. But this requires >$50M monthly volume on Binance, defeating the
  purpose for an independent operator.
- **Sub-second execution with colo + maker fills** (true HFT infrastructure):
  could capture the 12bps/day reversion. Out of scope.
- **Cross-venue basis** (Binance perp vs Bybit/OKX perp, or CEX perp vs DEX
  perp) where dislocations are larger: not the angle tested here, but a
  different angle worth a separate probe. The DEX (HL) `premium` field in
  `FUNDING_SOL.json` could enable a perp-perp cross-venue basis test with
  different fee structure.

## Files

- `novel_findings/_basis_backtest.py` — data loader, honest backtester, signals.
- `novel_findings/_basis_sweep.py` — full parameter sweep (in-sample).
- `novel_findings/_basis_wf.py` — walk-forward + FTX-exclusion + 3-coin basket.
- `novel_findings/_basis_final.py` — per-trade economics, FTX decomposition,
  conditional-entry variants.
- `sol_data_cache/SPOT_BINANCE_NOVELFINDINGS.json` — freshly fetched real
  Binance SPOT daily klines (SOL/BTC/ETH), used as the spot reference.
