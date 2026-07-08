# rust_trend_tilanthi

Shareable point-in-time WFO reproduction repo for the FRAMA 5m seven-offset crypto futures runs.

This repo contains only the pieces needed to rebuild and rerun the 2024 and 2025 WFO results:

- Rust WFO/backtest engine under `src/`
- Python Optuna orchestration under `python/rust_trend_optuna/`
- Binance USD-M 1-minute local data store under `data/binance_um_1m/`
- compact reference rollups under `reference_results/`
- report generator `generate_institutional_quant_report.py`

It intentionally excludes old research notebooks/scripts, `.venv`, `target`, raw per-offset source-run artifacts, and prior submission packages.

## Prerequisites

- Rust toolchain `1.89`
- Python `3.11+`
- `uv`

On a new machine:

```sh
uv sync
uv run maturin develop --release
cargo build --release
```

The WFO runner invokes Optuna through `uv run python -m rust_trend_optuna`, so `maturin develop` is required to build the local Rust/Python extension before running WFO.

The final institutional HTML report generator uses `numpy` and `pandas`. If it is missing in the local Python used by `python3`, install it with:

```sh
uv add pandas
```

Even if that report step is unavailable, the Rust runner still writes core CSV/JSON/HTML rollup artifacts.

## Data

The packaged local data store includes the top-7 Binance USD-M symbols:

`BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT, DOGEUSDT, SUIUSDT`

Verify coverage before rerunning:

```sh
cargo run --release -- data verify --preset binance-um-top7-2025 --start 2024-01-01 --end 2026-01-01
```

## Reproduce 2024

Configured WFO window: `2024-01-01` to `2025-01-01` exclusive.

Report/OOS equity starts after the initial 2-week IS window, so the stitched OOS curve begins around `2024-01-15`.

```sh
cargo run --release -- wfo daily-offset-ensemble \
  --name frama-5m-7offset-stacked-consensus-pit-2024-immediate \
  --strategy-set frama-5m-confirm \
  --symbols BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT,DOGEUSDT,SUIUSDT \
  --offsets 0,1,2,3,4,5,6 \
  --trials 500 \
  --seed 42 \
  --min-profit-factor 1.10 \
  --candidate-min-profit-factor 1.10 \
  --tpe-consensus-min-passing-windows 4 \
  --account-balance 10000 \
  --is-weeks 2 \
  --oos-weeks 1 \
  --step-weeks 1 \
  --gap-weeks 0 \
  --start-date 2024-01-01 \
  --end-date 2025-01-01
```

Reference result:

- `reference_results/2024_immediate_touch/rollup_summary.json`
- starting capital: `$70,000`
- final balance: `$158,659.00`
- total OOS PnL: `$88,659.00`
- net return: `126.66%`
- max drawdown: `3.86%`
- profit factor: `1.220`
- trades: `71,449`
- provenance: `PASS point-in-time optimizer boundary`

## Reproduce 2025

Configured WFO window: `2025-01-01` to `2026-01-01` exclusive.

```sh
cargo run --release -- wfo daily-offset-ensemble \
  --name frama-5m-7offset-stacked-consensus-pit-full \
  --strategy-set frama-5m-confirm \
  --symbols BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT,DOGEUSDT,SUIUSDT \
  --offsets 0,1,2,3,4,5,6 \
  --trials 500 \
  --seed 42 \
  --min-profit-factor 1.10 \
  --candidate-min-profit-factor 1.10 \
  --tpe-consensus-min-passing-windows 4 \
  --account-balance 10000 \
  --is-weeks 2 \
  --oos-weeks 1 \
  --step-weeks 1 \
  --gap-weeks 0 \
  --start-date 2025-01-01 \
  --end-date 2026-01-01
```

Reference result:

- `reference_results/2025_full/rollup_summary.json`
- starting capital: `$70,000`
- final balance: `$183,024.63`
- total OOS PnL: `$113,024.63`
- net return: `161.46%`
- max drawdown: `4.19%`
- profit factor: `1.270`
- trades: `80,011`
- provenance: `PASS point-in-time optimizer boundary`

## Compare A New Run To Reference

After rerunning, compare a generated daily-offset rollup directory against a reference summary:

```sh
python3 repro/compare_rollup_summary.py \
  reference_results/2024_immediate_touch/rollup_summary.json \
  runs/wfo/<new_2024_daily_offset_dir>/rollup_summary.json

python3 repro/compare_rollup_summary.py \
  reference_results/2025_full/rollup_summary.json \
  runs/wfo/<new_2025_daily_offset_dir>/rollup_summary.json
```

Small floating-point differences are normal across platforms, but material differences in trades, PF, PnL, or provenance should be investigated.

## Notes

- Optimizer mode is `point_in_time_fold_local`.
- Existing global-TPE artifacts are intentionally not included.
- Primary OOS artifacts stitch selected folds only; missing selections are not backfilled with failed candidates.
- Individual offset source-run diagnostics can be stricter than the stacked rollup gate. The reference rollups preserve those diagnostic fields.
