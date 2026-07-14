# Phase 1 — Multi-stream data layer for regime-led discovery

**Status:** design (awaiting implementation plan)
**Date:** 2026-07-12
**Scope:** one phase of a larger restructure (see Context). This spec covers **only the data layer**.

---

## Context — the larger restructure (5 phases)

SLATE's discovery currently searches *parameters of fixed simple templates* on
OHLCV for one asset, and the corrected gates now correctly save nothing (every
current strategy loses money on daily SOL after costs). The restructure flips
the pipeline to **regime-led, long/short, quantitative, stigmergically-coordinated
discovery**:

1. **Data layer** *(this spec)* — multi-stream ingest for a ~10-perp basket.
2. **Regime + pheromone core** — regime classifier + a pheromone field porting
   EpiDISC's dynamics (evaporation/reinforcement, a REGIME pheromone type) in-project.
3. **Specialist agents + re-enable swarm** — funding/carry, liquidation, basis,
   cross-sectional-factor, vol-regime agents; wire the (functional but disabled)
   `slate_core/swarm/` into the live loop.
4. **Evolution + validation restructure** — niche by (regime × family), explicit
   long/short, regime-respecting walk-forward validation with multiple-comparisons
   correction.
5. **Verification** — end-to-end multi-stream backtests, honest edge check.

Decisions locked with the user: **full perp data stack** (funding-first phasing),
**~10-perp basket**, **repair/re-enable SLATE's own swarm**, **hybrid substrate**
(SLATE orchestration + port EpiDISC pheromone dynamics in-project).

Each phase is its own spec → plan → implement cycle. **Data is first** because
every downstream layer consumes it and the regime/agent designs must be made
against real funding/OI/liquidation data, not guesses.

---

## 1. Goal

Build a deterministic, real-data-only ingest + storage + loader that serves the
full daily-aligned perp data stack for a basket of ~10 Binance USDT-M perpetuals,
so the regime classifier (Phase 2) and specialist agents (Phase 3) can detect
funding-stress, positioning, liquidation-risk, and basis regimes.

### Non-goals (later phases)
- Regime classification, pheromone field, specialist agents, signal evolution,
  validation. This phase produces **data only**.

---

## 2. Asset universe (~10 liquid Binance USDT-M perps)

Proposed basket (verify each is tradeable with liquid history during fetch):
`BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT, DOGEUSDT, ADAUSDT, AVAXUSDT,
LINKUSDT, LTCUSDT`. Defined as a single config list so it is easy to amend.

---

## 3. Data streams (per asset, all aligned to daily)

| Stream | Binance endpoint | Daily aggregate | Phase |
|---|---|---|---|
| OHLCV | `/fapi/v1/klines` (`interval=1d`) | as-is | 1a |
| Funding rate | `/fapi/v1/fundingRate` | mean of the day's funding events (typically 3) | 1a |
| Open interest | `/futures/data/openInterestHist` (`period=1d`) | last value of day | 1b |
| Liquidations | `/fapi/v1/allForceOrders` (historical; `forceOrders` for recent) | sum USD liquidated, split long/short | 1b |
| Long/short ratio | `/futures/data/topLongShortAccountRatio` + `topLongShortPositionRatio` (`period=1d`) | last | 1b |
| Basis | perp mark vs spot index (from `/fapi/v1/premiumIndex`) | mean; basis% = (mark−index)/index | 1b |

**Daily alignment rule (no lookforward):** each stream is aggregated so a row
dated `D` uses only information available at or before end-of-day `D`. Funding =
mean of events with `fundingTime` ≤ end of `D`; OI = last value of `D`;
liquidations = sum of force orders in `D`; L/S ratio = last snapshot of `D`;
basis = mean of `D` snapshots. All streams join on the daily date index.

---

## 4. Fetcher design

- Extend the existing `slate_core/connectors/binance_usdt_perpetual.py` (which
  already has `get_funding_rate`) with a **historical multi-symbol multi-stream
  fetcher** (new module `slate_core/data/multi_stream_fetcher.py`).
- One function per stream: `fetch_ohlcv(symbol, start, end)`,
  `fetch_funding_history(symbol, start, end)`, `fetch_open_interest_history(...)`,
  `fetch_liquidations(...)`, `fetch_long_short_ratio(...)`, `fetch_basis(...)`.
- Each handles Binance pagination (`startTime`/`endTime`/`limit`), rate limits
  (honor weight budget; sleep on 429/418), and HTTP retries with backoff.
- **Real data only.** No synthetic generation, no interpolation across gaps
  larger than a configured threshold (mark missing rows explicitly).

## 5. Storage layout

- Directory: `data/multi_stream/` (gitignored — data is fetched, not committed;
  the existing `sol_data_cache/SOLUSDT_perpetual_1h_6m.csv` IS tracked, but the
  larger multi-stream set is kept local).
- Parquet per `(symbol, stream)`: e.g. `data/multi_stream/SOLUSDT/funding_1d.parquet`.
- A small `manifest.json` records coverage per symbol/stream (date range, row
  count, last-fetched) so the loader and refresh logic know what's present.

## 6. Loader API

A single deterministic loader the regime layer and backtester call:

```python
load_regime_data(symbols: list[str], start: str, end: str,
                 streams: list[str] = None) -> dict[str, pd.DataFrame]
# -> {symbol: daily-indexed DataFrame with all available streams as columns}
```

- Reads parquet, joins streams on the daily index, forward-fills only within a
  small gap (configurable, default 1 day) and marks larger gaps as NaN.
- Deterministic: same inputs → identical frame (no RNG, stable column order).
- Validates no lookforward (dates monotonic, no future-dated rows).

---

## 7. Phasing

- **1a** — OHLCV (multi-symbol, daily) + funding-rate history. Reuses the
  existing OHLCV fetching; adds `fetch_funding_history`. Gets cross-sectional
  carry/momentum and funding-regime detection working against real data.
- **1b** — open interest, liquidations, long/short ratio, basis. Unlocks
  positioning-regime and liquidation-cascade inputs.

1a is independently useful (funding is the perp-specific edge the prior audit
flagged as the only positive signal). Ship and verify 1a before 1b.

---

## 8. Constraints

- **Real data only** (project rule); no synthetic OHLCV or fabricated funding.
- **Daily+ timeframe** (project rule: sub-daily indicators are not profitable);
  intraday streams are aggregated to daily on ingest.
- **Brutally realistic**: this layer carries raw data; cost realism is applied
  downstream by the existing backtester (maker 0.02% / taker 0.05% / 15bps /
  80% fill).
- Binance rate-limit aware; idempotent (re-running refreshes gaps, doesn't dup).

## 9. Error handling

- HTTP 429/418 → back off and retry (Binance weight budget).
- Missing stream for a symbol/date → explicit NaN + manifest note; loader never
  silently fabricates.
- Partial/short history → load what exists; the regime layer (Phase 2) decides
  how to handle sparse assets.
- Fetch failures logged with symbol/stream/reason; never crash the server
  (data refresh runs in the background or as a CLI, decoupled from the live loop).

## 10. Testing

- **Per-stream ingest tests**: a known small date range is fetched (or a fixture)
  and the daily aggregate matches the expected rule (e.g. daily funding = mean
  of the day's events; daily liquidations = sum).
- **Alignment test**: joining streams on the daily index produces no
  future-dated rows; dates are monotonic; no lookforward.
- **Loader determinism**: `load_regime_data` returns an identical frame across
  calls for the same inputs.
- **Gap handling**: a deliberate gap is marked NaN (not interpolated) beyond the
  configured threshold.
- All tests use real Binance data (small fixture ranges) or committed fixture
  parquet — never synthetic market values.

---

## 11. Out of scope (explicit)

Regime classification, pheromone field, specialist agents, signal-code
evolution, validation restructure, and any live-trading wiring. Phase 1 delivers
**data + loader**; nothing here trades or discovers.

---

## 12. Known data-availability risks (resolve at start of 1b)

Phase 1a streams (OHLCV, funding history) are well-served by stable Binance
endpoints. Phase 1b has two streams whose **historical** availability is
uncertain and must be confirmed before building them:

- **Liquidations**: Binance's public `allForceOrders` historical access has been
  restricted/deprecated. Options to evaluate during 1b: the per-account
  `forceOrders` (account-scoped, not market-wide), the Binance Vision data
  warehouse dumps (`data.binance.vision`), or a third-party feed (e.g.
  Coinglass). If none yields clean daily history, liquidation-cascade strategies
  move to a later phase or a derived proxy (e.g., large-bar + OI-drop detection).
- **Basis (mark vs index)**: `/fapi/v1/premiumIndex` is a current snapshot, not
  history. Historical basis may be reconstructed from funding-rate-implied
  premium or a mark-price kline series if available; otherwise it is derived
  (approximated) and labelled as such, never fabricated.

1a is not blocked by either risk and ships first. The 1b work item begins with an
availability check for these two streams and adjusts scope per the findings.

