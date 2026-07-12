# Phase 1b stream availability — probe findings (2026-07-12)

Run `python3 -m slate_core.data.probe_1b_streams` against Binance USDT-M (SOLUSDT,
last 7 days). Findings that scope Phase 1b:

## Available historically (daily) — build in 1b
- **Open interest** — `/futures/data/openInterestHist` → 200, 7 daily rows
  (`sumOpenInterest`, `sumOpenInterestValue`). ✅
- **Long/short account ratio** — `/futures/data/topLongShortAccountRatio` → 200,
  7 daily rows (`longShortRatio`, `longAccount`, `shortAccount`). ✅
- **Long/short position ratio** — `/futures/data/topLongShortPositionRatio` → 200,
  7 daily rows. ✅

## NOT publicly available — defer / proxy
- **Liquidations** — `/fapi/v1/allForceOrders` returns no usable public response
  (restricted); `/fapi/v1/forceOrders` returns 401 (requires a valid API key and
  is account-scoped, not market-wide). ❌ historical market-wide liquidations are
  not available from Binance public endpoints.
  - **Decision**: implement a *derived liquidation proxy* in Phase 3 (large
    adverse bar + OI drop = likely forced unwind) rather than ingest a feed, OR
    add a third-party feed (e.g. Coinglass) as a later task. Liquidation-cascade
    strategies use the proxy until a real feed is wired.

## Snapshot only — must be derived
- **Basis (mark vs index)** — `/fapi/v1/premiumIndex` returns a current snapshot
  (`markPrice`, `indexPrice`) but **no history**. ❌ no historical basis endpoint.
  - **Decision**: derive a historical basis *proxy* from the funding-rate-implied
    premium (funding history IS available, Task 2) or from OHLCV vs a spot index
    series, and label it as derived. Never fabricate.

## Net
Phase 1b = **OI + L/S account ratio + L/S position ratio** (all confirmed
available), plus a **derived basis proxy** from funding. Liquidations move to a
derived proxy in Phase 3 (or a third-party feed later). 1a (OHLCV + funding) is
unaffected and shipped.
