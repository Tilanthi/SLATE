# New-Listing Early Momentum — NEGATIVE

**Angle key:** `new_listing_momentum`
**Verdict:** **NEGATIVE** (clear, robust negative EV; no tradable edge)
**Date:** 2026-07-23

## Hypothesis
Buy Binance USDT-perpetual listings in their first 1–7 days; exploit listing-day
inefficiency and attention-driven momentum. Hold 1–30 days.

## Data (all REAL, no synthesis)
- `sol_data_cache/exchange_info_test.json` — Binance fapi `exchangeInfo` snapshot,
  530 USDT-perps with `onboardDate` (listing date) populated.
- `sol_data_cache/listing_study/listings_raw.json` — **first 40 daily klines per
  listing, fetched from `fapi.binance.com/fapi/v1/klines`** for **419 listings
  onboarded 2023-01-09 → 2026-07-03** (range covers the entire post-2022 cohort).
- BTC benchmark from `BASKET_BTCUSDT_1d.json` for matched calendar-window returns.

Loader & cost model: `slate_core.backtest` conventions (taker 0.05% + 15 bps
slippage one-way = 0.20% round-trip; + 1 bp/day funding drag, charitable).

## Results

### Per-listing returns (net of 0.20% round-trip cost + funding)

| Strategy          | N   | Mean    | Median   | Hit% | t-stat | vs BTC same week |
|-------------------|-----|---------|----------|------|--------|------------------|
| S1 day-1 intraday | 419 | -0.22%  | —        | 38.9 | -0.18  | BTC +0.01%       |
| S2 24h            | 419 | -0.23%  | —        | 38.7 | -0.18  | BTC +0.01%       |
| S3 3-day          | 419 | -0.25%  | —        | 35.8 | -0.14  | BTC +0.11%       |
| **S4 7-day**      | 419 | **-0.97%** | **-11.38%** | **34.4** | -0.39 | BTC +0.71%       |
| S5 day-2 to 7     | 419 | -1.75%  | —        | 33.9 | -0.92  | BTC +0.52%       |
| S6 30-day         | 415 | +2.76%  | —        | 32.5 | +0.33  | BTC +2.31%       |

### The "edge" is a power-law illusion

7-day net-return distribution (skew = **+3.33**, std = 51%):
- p1 −63.7% / p5 −48.1% / **p50 −11.4%** / p95 +78.3% / p99 +191.7%
- 9.3% of listings moon >+50%; 4.5% lose more than half

Drop-the-top-N test on the 7-day mean:
```
drop top  0:  mean =  -0.98%   median = -11.38%
drop top  3:  mean =  -3.44%   median = -11.83%
drop top 10:  mean =  -6.77%   median = -12.53%
drop top 20:  mean =  -9.81%   median = -13.07%
drop top 50:  mean = -15.14%   median = -16.18%
```
The mean is held near zero only by **5–10 moonbags per cohort**; the median
experience is a double-digit loss. This is a lottery-ticket distribution, not a
tradable drift.

### Year-by-year (7-day hold, net)

| Year | N   | Mean    | Median   | Hit% |
|------|-----|---------|----------|------|
| 2023 | 67  | -0.91%  | -6.15%   | 38.8 |
| 2024 | 97  | +3.77%  | -6.42%   | 41.2 |
| 2025 | 211 | -2.37%  | -16.20%  | 30.8 |
| 2026 | 44  | -4.91%  | -22.41%  | 29.5 |

2024's apparent positivity is **entirely a top-tail artifact** — median is still
negative (-6.4%), and 2025-2026 got *worse* as Binance listed ever-smaller caps.

### Size & momentum continuation conditionals (7-day hold, net)
- Low day-1 volume (<$50M): N=63, mean -0.26%, t=-0.07 (no edge in small caps)
- High day-1 volume (≥$50M): N=356, mean -1.11%, t=-0.39 (no edge in big caps)
- Day-1 pumpers (>+5%) held day-2→7: N=113, mean +2.75%, **t=0.60 — not significant**
- Day-1 dumpers (<−5%) held day-2→7: N=191, mean -3.48%, t=-1.24 (weak continuation, not tradeable)

### APR / Sharpe projection (equal-weight portfolio, ~120 listings/yr)

| Concurrent positions | AUM/position | APR     | Sharpe |
|----------------------|--------------|---------|--------|
| 5  (20% each)        | heavy        | -23.6%  | -0.09  |
| 10 (10% each)        | moderate     | -11.8%  | -0.07  |
| 20 (5% each)         | diversified  | -5.9%   | -0.05  |

## Survivorship / selection / lookahead scrutiny

1. **Survivorship bias — material and uncorrectable here.** exchangeInfo only
   lists *currently TRADING* symbols; everything Binance delisted 2023-2026 is
   missing. Adding 5/10/15% delisted-at-(-80% to -90%) phantom losers moves the
   mean from -0.98% to -4.9% / -8.8% / -14.2%. The true EV is **materially worse**
   than the already-negative headline.
2. **No lookahead.** Buy at the listing-day `open` (a price we can observe and
   trade at on listing day); sell at known future-bar close. Causal & realistic.
3. **Cost realism.** 0.20% round-trip + 1bp/day funding is *charitable* for newly
   listed small-caps (real first-day spreads on Binance perps often 30-100 bps;
   funding on hot listings frequently spikes to 0.05-0.30%/8h = longs pay much
   more). Real costs push the result further negative.
4. **Selection bias.** None of the 419 listings were chosen by performance — the
   cohort is "all perps listed 2023-01-09 onward, ≥8 days ago, still trading."
   Selection only enters via survivorship (point 1).
5. **Spot-check vs known listings** confirms dispersion, not drift: TIA +332%
   (30d, lucky moonbag), ENA +60% (7d, lucky), WLD -47% (30d, typical), TRUMP -56%
   (30d, hype-fade typical), MELANIA -77% (30d, typical disaster), SAGA -68%
   (30d, typical), SUI -57% (30d, typical).

## Verdict

**NEGATIVE.** Buying new Binance perp listings in their first week has negative
expected value after honest costs, and the apparent mean-near-zero is entirely an
artifact of ~5-10 power-law moonbags per cohort (drop top-10 → mean collapses to
-6.8%; drop top-50 → -15.1%). The median 7-day return is **-11.4%**. Hit rate
(34%) is below BTC's over the matched week (54%). Even before survivorship, APR
is roughly -6% to -24% depending on sizing; with realistic survivorship
adjustment it's worse. **Do not deploy.**

## Capacity

Effectively unlimited at retail (most new listings have thin liquidity at the
very top of the book), but the edge is negative so capacity is moot. Above
~$50k/listing, first-bar slippage would worsen materially (we already model 15bps;
true first-bar impact on small caps is much larger).

## Reusable artifacts

- `sol_data_cache/listing_study/fetch_listings.py` — resumable fapi kline fetcher
- `sol_data_cache/listing_study/listings_raw.json` — 419 listings' first 40 days
- `sol_data_cache/listing_study/analyze.py` — strategy + BTC-benchmark tests
- `sol_data_cache/listing_study/diagnostics.py` — distribution + bias diagnostics
- `sol_data_cache/listing_study/summary_v2.json` — machine-readable stats

## What would change the verdict

A *selection* model that picks moonbags ex ante. None of the obvious ex-ante
splits (size, day-1 momentum, year, hold-length) produce a t-stat above ~1.2.
A real selector would need features we cannot test here (social volume, OI
build-up pattern, market-maker inventory, VC unlock schedule). Even then,
survivorship and first-bar slippage would have to be modeled explicitly.
