# SLATE DEX Discovery Layer (Hyperliquid)

Detailed reference for the DEX pipeline. Moved out of CLAUDE.md.

## Architecture

Separate discovery pipeline for Hyperliquid (DEX), exploiting what CEX can't:
**maker rebates** (zero gas; maker 0.015% < taker 0.045%) and **sub-daily timescales**.
Lives in `slate_core/dex/` with its own DB + verdict log. CEX code untouched.

## Crown Jewel Reuse

The venue-agnostic infrastructure is shared: write chokepoint (`append_verified`),
funnel (`verdict_log`), AST sandbox + complexity cap, `FitnessResult` gates,
`ProgramDatabase`, `LLMPool`. The DEX evolved unit is a CEX-form
`signal_fn(df,i,params)->{-1,0,1}`.

## Components

- **`dex/data/`**: HL candles + funding, 5,000-candle accumulating store.
- **`dex/backtester/`**: maker/taker fee split + rebates, oracle rejection,
  min-notional, leverage cap, slippage (1bps taker), lookahead-safe.
- **`dex/strategies/`**: `act(state)->list[Order]` action model with Directional
  (Market-executed) and MarketMaker (two-sided quoting) archetypes.
- **L2 feed**: `bar_fill_l2` queue gate + pluggable `l2_provider` seam.
- **Evolvable MM**: `quote_fn(state)->(half_spread_bps, inv_skew_bps, size)`
  sandbox-compiled via `compile_function`.
- **Slippage**: taker fills walk the book (1bps); maker fills exact price.
  `HLFeeSchedule.slippage_bps` configurable.

## Validation & Gates

- **Complexity cap**: 350 AST nodes (vs CEX 200; measured DEX signals cluster 201-350).
- **Walk-forward**: 5 anchored folds, must profit on ALL. Selectable via
  `EvolutionConfig.validation` ("walkforward" | "two_window").
- **5 anomaly seeds**: funding-carry, residual-MR, vol-regime, liquidation-aware,
  imbalance-fade + real per-bar funding.
- **P1–P5**: concurrent eval, hash-dedup, failure-feedback prompt.

## L2 Microstructure Infrastructure

- **Accumulator** (`com.slate.l2accumulator`): L2 snapshots (1/sec, 20 levels) +
  WebSocket trades for SOL/BTC/ETH, 24/7. ~259K snapshots + ~704K trades accumulated.
- **Tick backtester** (`l2_tick_backtester.py`): replays L2 event-by-event.
- **Result**: no edge at 1Hz resolution. The real HL edge (Cyril wallet: $1,297/3d,
  67% win, 5-7s holds, 99% maker entry) needs sub-second + queue priority + VIP fees.

## Runnable Targets

`SLATE_DEX_TARGET=` `directional` (default) | `market_maker` | `pairs` | `cross_market`.
Pairs legs: `SLATE_DEX_COIN`/`SLATE_DEX_COIN_B`. Data: `SLATE_DEX_DATA_PATH`.

## Honest State

0 stored discoveries across ALL bar-level experiments (5 strategy classes × 3
timescales × 3 markets). The edge is real but lives at a finer resolution than candle bars.
