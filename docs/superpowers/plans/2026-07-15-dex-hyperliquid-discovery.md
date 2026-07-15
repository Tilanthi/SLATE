# DEX Hyperliquid Discovery Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a separate, DEX-focused discovery pipeline for Hyperliquid that reuses SLATE's venue-agnostic verification "crown jewel" (chokepoint, funnel, two-window gate, overfit penalty, activity-credit, complexity cap, sandbox) while replacing only the venue-specific economics: HL data, a bar-level maker/taker/rebate backtester, and a richer DEX action model (directional + market-making archetypes).

**Architecture:** A new `slate_core/dex/` subtree (data → backtester → strategies → evolution) runs alongside the CEX pipeline with its own DBs and `/api/dex/*` endpoints, selected by a run-mode switch. The CEX code path is untouched. v1 is bar-level + first-party candles; L2/microstructure realism is deferred behind a pluggable seam.

**Tech Stack:** Python 3.14, pandas/numpy, pytest (asyncio_mode=auto), the existing `hyperliquid-python-sdk` pattern (raw `requests` POST to `https://api.hyperliquid.xyz/info`), reused `slate_core/discovery/evolution/*` infrastructure.

## Global Constraints
- **Real data only** — HL candles/funding from the first-party API; no synthetic OHLCV (funding may be modeled if absent, clearly flagged).
- **Paper/discovery only** — never place live HL orders; the pipeline evaluates strategies in a backtester, not against the exchange.
- **Reuse the crown jewel** — `ProgramDatabase`/`append_verified` (chokepoint), `verdict_log` (funnel), `signal_sandbox` (AST cage + `signal_complexity`), the subprocess-eval pattern, `LLMPool`, `MetaPromptStore`. Do not reimplement them.
- **CEX untouched** — no edits under `slate_core/discovery/` that change CEX behavior; only additive imports are allowed if needed.
- **Separate stores** — `slate_core/dex_discoveries.db`, `slate_core/dex_verdicts.jsonl`; separate `/api/dex/*` endpoints.
- **Realistic HL economics** — perp taker 0.045% / maker 0.015% with maker rebates at high maker-fraction; zero gas; oracle rejection; min-notional; funding accrual.
- **TDD** — every component test-first; suite must stay green; restart server after code changes.

## File Structure (new `slate_core/dex/`)
- `data/hyperliquid_client.py` — thin REST client: `candles(coin, interval, start, end)`, `funding_history(coin)`, `meta()`. Respects 500/req pagination + 5000-candle cap.
- `data/load_data.py` — `load_candles(path)` + accumulating store `refresh_store(coin, interval)` (poll + append, cap-aware). `REAL_DATA_DEFAULT`.
- `backtester/economics.py` — `HLFeeSchedule` (maker/taker/rebate), `oracle_ok(px, oracle)`, `min_notional_ok(sz, px)`.
- `backtester/fill_model.py` — `bar_fill(order, bar, oracle)` → maker/taker/no-fill, honoring touch + Alo + oracle rejection.
- `backtester/dex_backtester.py` — `DexBacktester.backtest(strategy, bars, config)` → result dict (PnL, fees, rebates, funding, fills, inventory, maker_fraction).
- `strategies/action.py` — `Order(side, px, sz, tif)` + `DexStrategy` protocol `act(state) -> list[Order]`; `BarState`.
- `strategies/directional.py` — `DirectionalStrategy` (long/short/flat + maker routing).
- `strategies/market_maker.py` — `MarketMakerStrategy` (quote offsets + inventory skew + rebate).
- `evolution/dex_fitness.py` — `evaluate_dex_fitness(strategy, bars, config) -> DexFitnessResult`; reuses two-window + activity-credit + min_fitness gates; DEX death-stages (`no_fills`, `oracle_rejected`, `capped`, `not_profitable`).
- `evolution/dex_controller.py` — async DEX evolution step reusing `ProgramDatabase` + `verdict_log` + `signal_sandbox` + `LLMPool`.
- `evolution/dex_service.py` — server-hosted DEX loop; `/api/dex/{status,start,stop}`; run-mode switch `SLATE_PIPELINE=cex|dex` (default cex).

## Phased Tasks
- **P0 — Data layer:** client + loader + accumulating store; tests against a stubbed/paginated response.
- **P1 — Economics + fill model:** fee schedule (rebate math), oracle/min-notional, bar-level maker/taker fill; TDD the economics exactly.
- **P2 — Backtester:** walk bars, execute `act()` orders, track PnL/fees/rebates/funding/inventory; reuse `PerpetualFuturesBacktester`'s lookahead discipline (strategy sees only past bars).
- **P3 — Action model + archetypes:** `Order`/`DexStrategy` protocol; directional + MM archetypes; tests on synthetic bars.
- **P4 — DEX evolution:** `evaluate_dex_fitness` (reuse gates); `dex_controller` reusing crown jewel; DEX seed archetypes; sandbox-compiled `act()`.
- **P5 — Service + endpoints + mode switch:** `dex_service`, `/api/dex/*`, `SLATE_PIPELINE` switch; CEX still default.
- **P6 — Harden + verify:** overfit cage on DEX backtester (lookahead), full suite green, server restart, CLAUDE.md note, commit, push.

Each task below is test-first; full code is written at implementation time against these interfaces.
