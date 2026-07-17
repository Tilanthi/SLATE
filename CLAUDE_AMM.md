# SLATE AMM LP Layer (Uniswap V3 Yield)

Detailed reference for the AMM LP pipeline. Moved out of CLAUDE.md.

## Architecture

A third discovery engine for **yield provision** (not speculation): provides
concentrated liquidity on Uniswap V3 stablecoin pairs, earning swap fees while
managing IL. The dex.pdf analysis identifies this as a 5–15% APY structural edge.
Lives in `slate_core/amm/`.

## Components

- **`amm_math.py`**: Uniswap V3 formulas (tick↔price, liquidity↔amounts, IL).
- **`lp_backtester.py`**: simulates LP positions — accrues swap fees (pool_volume ×
  fee_tier × your share), tracks IL, gas, rebalancing. Lookahead-safe.
- **`delta_neutral.py`**: LP + perp short hedge. Removes IL in ranging markets;
  **loses in trending markets** (SOL 7x = −68% APY). Needs a regime filter.
- **`lp_fitness.py`**: two-window IS/OOS evaluator using APY% (time-normalized).
  `min_trades=1` (LP strategies rebalance rarely).
- **`lp_controller.py` + `lp_service.py`**: evolves `lp_fn(bar)` via LLM evolution.
  Separate `amm_verdicts.jsonl` + `amm_evolution.db`.
- **`pool_data.py`**: fetches USDCUSDT/FDUSDUSDT/TUSDUSDT from Binance.
- **`lp_seeds.py`**: 3 archetypes (stablecoin_tight, stablecoin_wide, vol_conditioned_lp).

## Backtest Results

USDC/USDT LP (365 days real data):
- ±20bps range: **10.8% APY**, ~$0 IL, 352/355 in-range days
- ±50bps+: 10.8% APY (saturates — always in range)
- 0.05% fee tier: 18.0% APY (higher per-swap fees)

Cross-pair: all three stablecoin pairs converge to ~10.8% APY at adequate range width.

Delta-neutral on SOL (2023-2026): **−68% APY** — the perp short bleeds in a 7x bull run.
This strategy needs a ranging-market regime filter.

## CEX Funding Archetypes

Two archetypes added to `SEED_ARCHETYPES`:
- **funding_reversal**: LONG when funding < 1st percentile (short squeeze reversal).
- **funding_carry**: SHORT when funding > median + 0.00005 (carry trade).

Real Binance funding merged into daily candles via `merge_funding` (forward-filled
8h rates). `load_daily_data(trim_to_funding=True)` drops pre-funding bars.
Backtester reads `df['funding']` when available (falls back to synthetic).

## Run It

`SLATE_PIPELINE=amm`; endpoints `/api/amm/{status,start,stop}`.

## Codebase Audit (2026-07-17)

All 214 `slate_core` Python files parse cleanly and import successfully.
Fixed 5 broken files (3 syntax errors + 2 NameErrors) — same truncation pattern
as ASTRA. `backoff` dependency added.
