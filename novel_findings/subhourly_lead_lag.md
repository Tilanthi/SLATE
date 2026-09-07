# Sub-hourly Cross-Asset Lead-Lag (BTC/ETH -> SOL on Hyperliquid)

**Angle key:** `subhourly_lead_lag`
**Verdict:** **NEGATIVE** — no exploitable edge exists at 5m, 15m, or 1h. Costs kill it
by ~100x even in the gross-per-trade comparison, AND the underlying signal is zero.
**Honest APR:** -100% (total capital loss) at every timescale, every variant.
**Honest Sharpe:** -10 to -290.

---

## What was tested

Real Hyperliquid candle data (no synthesis). Native sub-hourly resolution for the
leader coins was **fetched from the HL API** (the cached files only had BTC/ETH at
1h, which is too coarse for a clean sub-hourly test):

| file | bars | span |
|------|------|------|
| `HLFETCH_BTC_5m.json` / `HLFETCH_ETH_5m.json` | 5030 | 17 d (Jul 5 → Jul 23 2026) |
| `HLFETCH_BTC_15m_full.json` / `HLFETCH_ETH_15m_full.json` | 5011 | 52 d (Jun 1 → Jul 23 2026) |
| `HLFETCH_SOL_5m_ext.json` (SOL 5m extended via API) | 7218 | 25 d |
| `HYPERLIQUID_SOL_15m.json`, `HYPERLIQUID_*_1h.json` | cached | — |

Honest evaluator: `slate_core.backtest.backtest` (1-bar causal lag,
`held[t] = target[t-1]`), DEX venue (taker 0.045% + 10 bps slip = 0.055% one-way),
square-root market impact at $1M AUM.

## Three independent tests, all null

### Test 1 — Cross-correlation function (BTC/ETH vs SOL, no trading)
| grid | lag=-1 | **lag=0** | lag=+1 | lag=+2 | lag=+3 | lag=+10 |
|------|-------|-----------|--------|--------|--------|---------|
| 5m BTC | -0.014 | **0.829** | -0.009 | -0.003 | -0.022 | +0.032 |
| 5m ETH | +0.007 | **0.855** | -0.004 | -0.006 | -0.030 | +0.015 |
| 15m BTC | -0.029 | **0.860** | -0.015 | +0.012 | -0.002 | -0.022 |
| 1h BTC | -0.021 | **0.853** | +0.001 | -0.019 | +0.012 | +0.009 |

Contemporaneous correlation (lag 0) is huge (0.83–0.88): BTC/ETH/SOL move together
within the same bar. **Off-diagonal lags are all near zero** (-0.03 to +0.03). BTC
does not lead SOL at any tested timescale.

### Test 2 — Partial correlation (the honest lead-lag test)
`corr(SOL[t+1], leader[t])` controlling for `leader[t+1]`:
| grid | partial corr |
|------|-------------|
| 5m BTC | -0.0007 |
| 5m ETH | -0.0187 |
| 15m BTC | +0.0090 |
| 15m ETH | -0.0064 |
| 1h BTC | +0.0163 |
| 1h ETH | -0.0267 |

All within ±2 SE of zero (SE ≈ 1/sqrt(n) ≈ 0.014). No incremental predictive power.

### Test 3 — Honest backtest, 4 signal variants × 6 grids (24 combinations)
Signals: `sign(leader_ret)`, `sign(leader_kbar_sum)`, `clip(z(leader_ret),-1,1)`,
`sign(ema(leader_ret))`. **Every single combination loses ~100% of capital net of
costs.** Sharpe ratios: -10 to -290.

## The cost hurdle (the prompt's explicit question)

At 5m, `sign(leader_ret)` flips position on **essentially every bar** (turnover 5227
over 5028 bars). Gross edge per unit turnover:

| grid | gross / trade (bps) | DEX one-way cost (bps) | edge/cost ratio |
|------|--------------------|------------------------|-----------------|
| 5m BTC | -0.17 | 55 | — (negative) |
| 5m ETH | +0.19 | 55 | **0.003x** |
| 15m BTC | -0.02 | 55 | — |
| 1h BTC | +0.58 | 55 | **0.011x** |
| 1h ETH | +0.47 | 55 | **0.009x** |

The gross edge per trade is **100–300x too small** to clear even the flat cost
hurdle, before considering market impact. The high-frequency lead-lag edge is not
just unprofitable — it is bounded at essentially zero signal.

## CRITICAL: the forward-fill lookahead trap

The literal angle instruction ("resample BTC/ETH 1h to 5m/15m via forward-fill")
contains a fatal but subtle lookahead. An hourly candle indexed by its **open time
H:00** has a `close` value known only at **H+1:00**. Naive `reindex(method='ffill')`
uses that future close as of H:00, manufacturing a fake edge:

| grid | naive ffill lag-1 corr | causal ffill lag-1 corr |
|------|------------------------|--------------------------|
| 15m BTC | **+0.2212** (gross APY +4.1M% — LOOKAHEAD) | **+0.0066** (gross APY +196%) |
| 15m ETH | **+0.2235** (gross APY +6.2M% — LOOKAHEAD) | **-0.0056** (gross APY +20%) |

The honest construction (shift leader forward 1h before forward-fill, so the hour-H
close is only available at H+1:00) collapses the correlation to ≈ 0, matching the
native-resolution result. **Any future "resample-coarser-leader-to-finer-grid" test
on OHLC data MUST shift the leader by its bar length before ffill**, or it will
manufacture a 1-bar (here, 1-hour) lookahead.

## Why this is the expected (and correct) result

BTC/SOL/ETH share Hyperliquid's single matching engine. The cross-asset price
relationship is arbitraged near-instantaneously by HFT makers watching all three
books simultaneously. Within-venue cross-asset lead-lag at 5–15 min would be a free
lunch; it does not exist. The exploitable lead-lag in crypto (per Alexander/Daigler,
Dimpfl/Jank, Caporin/McAleer) is **cross-venue** (Binance → slower exchanges /
regional venues), which needs multi-venue tick/L2 data not available here.

## Reproducibility

Scripts (in repo root, scratch — not committed):
- `scratch_subhourly_leadlag.py` — CCF table (Test 1)
- `scratch_subhourly_backtest.py` — 4 variants × 6 grids backtest (Test 3)
- `scratch_subhourly_diagnostic.py` — partial corr + breakeven cost (Tests 2 + hurdle)
- Forward-fill lookahead audit inline in this session

Fetched real data (in `sol_data_cache/`, uniquely named `HLFETCH_*`):
`HLFETCH_{BTC,ETH}_{5m,15m_full}.json`, `HLFETCH_SOL_5m_ext.json`.

## Bottom line

The 1h lead-lag was already ruled out; this test extends the null to 5m and 15m.
**There is no sub-hourly cross-asset lead-lag edge on Hyperliquid, and even if a
ghost of one existed, the 55 bps one-way DEX cost is ~100x the gross edge per
trade.** The high-frequency lead-lag edge is bounded at zero on this single venue.
