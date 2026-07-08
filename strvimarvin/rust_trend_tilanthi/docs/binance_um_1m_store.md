# Binance USD-M 1m Candle Store

This project keeps Binance USD-M futures 1-minute candles in a local, gitignored
Parquet store for Rust backtests.

## Market Set

Preset: `binance-um-top7-2025`

Symbols:

- `BTCUSDT`
- `ETHUSDT`
- `SOLUSDT`
- `XRPUSDT`
- `DOGEUSDT`
- `BNBUSDT`
- `SUIUSDT`

Default range: `2025-01-01` inclusive to `2026-01-01` exclusive. That is
`525,600` one-minute rows per symbol.

## Commands

```sh
cargo run --release -- data sync \
  --preset binance-um-top7-2025 \
  --start 2025-01-01 \
  --end 2026-01-01

cargo run --release -- data verify \
  --preset binance-um-top7-2025 \
  --start 2025-01-01 \
  --end 2026-01-01
```

The store root defaults to `data/binance_um_1m/v1`. Override it with
`RUST_TREND_BINANCE_UM_1M_ROOT`.

## Source And Repair Policy

Primary source:

`https://data.binance.vision/data/futures/um/monthly/klines/{SYMBOL}/1m/{SYMBOL}-1m-{YYYY-MM}.zip`

Each archive is checked against its `.CHECKSUM` SHA-256 file before parsing.
If archive rows are missing, the store backfills those exact minute ranges from
Binance USD-M `/fapi/v1/klines`. If the API still has holes, remaining rows are
inserted as zero-volume flat candles from the prior close and marked synthetic.

## Path Contract

```text
data/binance_um_1m/v1/klines/{SYMBOL}/{YYYY}/{YYYY-MM}.parquet
data/binance_um_1m/v1/_meta/manifest.jsonl
data/binance_um_1m/v1/_meta/coverage.json
data/binance_um_1m/v1/_meta/schema_version.txt
```

The data directory is intentionally gitignored. Source code, docs, schema, and
commands are tracked; bulky market data stays local.

## Parquet Schema

| column | type | notes |
| --- | --- | --- |
| `open_time_ms` | `i64` | UTC minute open timestamp |
| `open` | `f64` | price |
| `high` | `f64` | price |
| `low` | `f64` | price |
| `close` | `f64` | price |
| `volume_base` | `f64` | base asset volume |
| `quote_volume` | `f64` | quote asset volume |
| `trade_count` | `u32` | number of trades |
| `taker_buy_volume_base` | `f64` | taker buy base volume |
| `taker_buy_quote_volume` | `f64` | taker buy quote volume |
| `source` | `u8` | `0=archive`, `1=api_backfill`, `2=synthetic_flat` |

## Extending Data

To add more history, run `data sync` with an earlier `--start`. To add newer
months, run it with a later `--end`. To add markets, add symbols or a preset in
the Rust data module and rerun sync. Existing verified monthly files are skipped
unless `--force` is provided.

After any extension, run `data verify` for the intended full range. Verification
requires exactly one row per minute in `[start, end)` for every symbol.

References:

- Binance public data archives: https://github.com/binance/binance-public-data
- Binance USD-M klines API: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Kline-Candlestick-Data
