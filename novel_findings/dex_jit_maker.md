# Novel angle: DEX JIT liquidity / maker-of-last-resort — `dex_jit_maker`

**Verdict: NEGATIVE** (for the testable variant on HL CLOB). The literal Uniswap-v3 AMM
JIT is **untestable** here for lack of swap/mempool data, and is a qualitatively
different problem (its upper bound is positive).

**Honest APR (HL CLOB JIT, tested): ≈ -75 %** (representative; per-fill is -7.3 bps,
scales linearly with activity). **Honest Sharpe: ≈ -3** (consistent negative drift).

---

## What "JIT" means on each venue

| Venue | "Fee" captured by liquidity provider | Data we have |
|---|---|---|
| Uniswap v3 (AMM) | Pool fee 0.05 %–1 % (5–100 bps) per swap | **None** (no swap/mempool) |
| Hyperliquid (CLOB) | None — maker **PAYS** 1.5 bps; only the half-spread is captured (≈0.065 bps on SOL) | Trades + L2 ✓ |

The "JIT = capture the fee without persistent IL" framing only makes sense on an AMM.
On HL CLOB, the closest analog is **selective market-making**: place passive orders
only when a microstructure signal predicts low adverse selection. We tested that on
real data; the AMM JIT is untestable here.

---

## Tested result: HL CLOB selective MM ("maker-of-last-resort") is robustly negative

**Data** (`sol_data_cache/`): `TRADES_SOL.jsonl` (198,567 trades, 3.56 d),
`L2_SOL.jsonl` (437,797 snapshots at ~1.3 s spacing). Cross-checked on BTC (805,457
trades) and ETH (486,428 trades).

### Per-fill economics (H = 5 s exit, exit-slip = 1 bp, HL retail fees)

```
        capture   - MAKER - TAKER - slip - adverse =  pnl_per_fill
SOL:    ~0.07 bps - 1.5   - 4.5   - 1.0  - 1.10    =  -7.29 bps   (med -6.93)
BTC:                                                          =  -7.27 bps
ETH:                                                          =  -7.17 bps
```

Half-spread capture on HL SOL is **0.065 bps** (90th-pct spread is 0.13 bps — the
tick). The maker fee (1.5 bps) is **23× larger** than the capture. Before any adverse
selection the strategy already loses ≈ 7 bps/fill.

### Adverse selection saturates fast

Signed post-trade mid-move vs. maker (positive = adverse to maker):

```
H=  1 s:  mean +0.29 bps   (std 1.6)
H=  5 s:  mean +1.10 bps   (std 3.4)
H= 30 s:  mean +1.12 bps   (std 5.6)
H= 60 s:  mean +1.21 bps   (std 7.4)
H=300 s:  mean +1.30 bps   (std 14.9)
```

Saturates at ~1.1 bps within 5 s. HL SOL is highly efficient at this timescale.

### No causal signal can extract a positive edge (OOS, IS-fit thresholds)

IS = first 60 % of trades by time, OOS = last 40 %. All thresholds fit on IS only.

| Strategy (IS-fit threshold) | OOS mean pnl/fill | OOS sum_pnl |
|---|---:|---:|
| Baseline (every trade) | -7.28 bps | -578 k |
| (A) wide spread (> IS q90) | -7.13 bps | -94 k |
| (B) deep book (> IS med) | -7.34 bps | -255 k |
| (C) balanced flow (\|rsv_5s\| < IS q33) | -7.21 bps | -204 k |
| (D) small trade (< IS med) | -7.26 bps | -289 k |
| (E) low-toxicity composite | -7.43 bps | -21 k |

**Decile analysis on OOS** for every feature (spread, imbalance, depth, recent signed
vol, trade-size/depth, raw size): no decile of any feature produces positive OOS mean
pnl — all sit in [-7.74, -7.05] bps/fill. The market is too efficient at this
timescale to filter adverse selection.

### Even the perfect-foresight ceiling is small at realistic horizons

Oracle keeps only fills where pnl > 0 (knows the post-trade mid move):

| H | exit-slip 1 bp | n_kept / 198 567 | sum_pnl (bps) | avg/fill |
|---|---|---|---|---|
| 1 s | 1 bp | 1.6 % | +23 286 | +7.28 |
| **5 s** | **1 bp** | **0.8 %** | **+7 606** | **+4.96** |
| 30 s | 1 bp | 6.0 % | +49 462 | +4.14 |
| 60 s | 1 bp | 10.8 % | +108 964 | +5.08 |
| 300 s | 1 bp | 26.1 % | +489 720 | +9.43 |

At the JIT-realistic horizon H=5 s, an **oracle** finds only **1 533 / 198 567 = 0.8 %**
of fills are profitable. The ceiling assumes (i) perfect foresight and (ii) 100 % fill
rate on those trades — both impossible. Realistic extraction is a single-digit % of
the ceiling, which leaves it well inside the negative.

### Capacity-aware APR (SOL, $1 M capital, $10 k/fill, share of trades)

| fill share | fills/day | APR | Sharpe (daily) |
|---:|---:|---:|---:|
| 1 % | 576 | -153 % | -31 |
| 5 % | 2 769 | -733 % | -35 |
| 20 % | 11 193 | -2 978 % | -34 |

At any reasonable activity the strategy loses money proportionally to turnover. The
"APR" depends entirely on how aggressively you churn; structurally it is bounded
above by 0.

---

## Why the result is robust (skeptic check)

1. **Lookahead?** None. Mid at trade time uses the last L2 snapshot strictly before
   the trade. Mid at H uses the last snapshot strictly before t+H. Features use only
   past trades (rolling windows via searchsorted).
2. **Survivorship?** None — we look at every trade in the tape, no selection.
3. **Overfit?** IS/OOS split; thresholds fit on IS only; OOS decile analysis shows no
   feature has *any* decile with positive pnl. The negative is uniform, not a
   threshold-tuning artifact.
4. **Fee realism?** Used HL's actual retail schedule (maker +1.5 bps, taker +4.5 bps).
   Sensitivity on exit-slip (0.1 / 1.0 / 5.0 bps) leaves every cell negative.
5. **Cross-asset?** SOL, BTC, ETH all give -7.17 to -7.29 bps/fill — universal for HL
   majors.
6. **Whale-tier sensitivity?** Even at `DEX_WHALE` (maker = -1 bp rebate) the
   taker-exit fee (4.5 bps) dominates; per-fill pnl at H=5 s ≈ -5.5 bps. Still
   negative.

---

## Untestable variant: Uniswap-v3 AMM JIT (qualitatively different)

The literal "capture the pool fee" angle requires Uniswap-v3 swap/mempool data, which
is **not in the cache**. We built the upper bound using HL trades as a proxy for swap
flow and AMM economics (capture = fee_tier × notional; cost = gas + IL). With L2 gas
($0.10/JIT) and 100 % capture, the ceiling APRs are enormous (365 % at 1 bp fee tier,
2 100 % at 5 bp, 13 k % at 30 bp) — but this is a fantasy upper bound assuming zero
competition, zero real IL, and using a different venue's flow. Real extraction is
5–30 % of theoretical, and only on swaps above ~$10 k (gas recovery threshold on L2;
much higher on L1).

**Data needed to confirm/deny the AMM JIT (this is the actual JIT angle):**
- Uniswap-v3 `Swap` events per pool (subgraph or RPC historical).
- Mempool / pending-tx stream (to see the swap before it lands).
- Pool reserve snapshots (tick + liquidity) at swap time, to compute real IL.
- Pool-fee-tier registry (1 / 5 / 30 / 100 bp).
- Optional: existing JIT-bot activity (Purecash, etc.) to estimate competition share.

Without these the AMM JIT cannot be confirmed; the HL CLOB "JIT" we could test is
structurally negative.

---

## Files

- `jit_scratch/load_align.py` — load + inspect trades/L2.
- `jit_scratch/adverse_selection.py` — signed adverse selection across horizons.
- `jit_scratch/economics.py` — per-fill PnL + perfect-foresight ceiling.
- `jit_scratch/jit_signals.py` — causal-signal conditional MM + OOS decile analysis.
- `jit_scratch/jit_large_swap.py` — trade-size adverse selection + predict-large-swap.
- `jit_scratch/final_sim.py` — cross-asset validity + capacity-aware APR/Sharpe.
- `jit_scratch/amm_jit_upper_bound.py` — AMM JIT theoretical upper bound.
- `jit_scratch/trades_features_SOL.parquet` — per-trade features + adverse selection.

---

## Bottom line

- **HL CLOB "JIT" / maker-of-last-resort: NEGATIVE on real data.** Per-fill -7.3 bps,
  no signal extracts a positive edge, oracle ceiling is unattainable. The structural
  reason is that HL retail pays you to provide liquidity (1.5 bps fee) while the
  half-spread you capture is 0.065 bps — a 23× fee/capture mismatch no microstructure
  filter can overcome.
- **AMM JIT (Uniswap v3): UNTESTABLE here.** Different problem (pool fees 5–100 bps
  vs HL spread 0.065 bps), upper bound is positive, but requires swap/mempool data
  not in the cache. Worth fetching if the AMM JIT is to be properly evaluated.
