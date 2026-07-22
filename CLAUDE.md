# SLATE PROJECT CONTEXT - Quick Reference

**Current Identity:** Autonomous Perpetual Futures Trading System 🔄⚡

---

## 🚨 CRITICAL OPERATIONAL RULES

### **🔄 SERVER RESTART RULE (MANDATORY)**
**ALWAYS restart the server after making ANY code changes to apply fixes.**

```bash
# After ANY code changes, restart server to apply fixes:
pkill -f "python3 -m slate_core.server"
sleep 2
python3 -m slate_core.server

# Or if running in terminal: Ctrl+C, then restart
```

**Why:** Python modules stay in memory. Changes won't take effect until server restarts.

**Verification:**
```bash
# Check server is running
curl http://127.0.0.1:8788/health | jq '.closed_loop_discovery.discovery_running'

# Check changes are applied
curl -X POST "http://127.0.0.1:8788/api/closed-loop/discovery/start" | jq '.summary'
```

---

## 🚨 Critical Bugs (all FIXED) & launchd Ops

All historical bugs below are **fixed and in code**; full write-ups live in their
linked docs and in [CLAUDE_CHANGELOG.md](CLAUDE_CHANGELOG.md).

- **Zero-Trade / type-mismatch (2026-07-09)** — signal generation fixed. Details: `CLAUDE_CRITICAL_BUG_FIX.md`.
- **Funding-arbitrage string-vs-numeric (2026-07-10)** — fixed. Details: `CLAUDE_FUNDING_ARBITRAGE_FIX.md`.
- **Discovery-pipeline data-structure drift (2026-07-11)** — integration handles direct+wrapped and object+dict; DB saves read-back verified.

### launchd ops — how to actually stop/restart the server
The server is kept alive by **`com.slate.autoserver`** (`KeepAlive=true`; runs the
server as its main process). A bare `pkill -f "python3 -m slate_core.server"` does
**not** stop it — launchd respawns within seconds (which is also why `pkill`
"restarts" it with new code).

```bash
# Fully stop (e.g. to work on the DB):
launchctl unload ~/Library/LaunchAgents/com.slate.autoserver.plist
pkill -9 -f "slate_core.server"; lsof -ti:8788 | xargs kill -9 2>/dev/null
# Restart (server runs as the job's main process; health ~15-20 s):
launchctl load ~/Library/LaunchAgents/com.slate.autoserver.plist
```

- Load `com.slate.autoserver` (uv Python 3.14 at `/Users/gjw255/.local/bin/python3`;
  its env embeds the Z.ai proxy so evolution uses the real GLM LLM). **Leave
  `com.slate.auto` UNLOADED** — it death-loops. If `/tmp/slate_server_error.log`
  shows `ModuleNotFoundError: numpy`, the plist points at the wrong Python.

---

## 📒 Change Log (detailed records moved out)

Detailed dated records live in **[CLAUDE_CHANGELOG.md](CLAUDE_CHANGELOG.md)** —
including the 2026-07-20→22 honest-evaluator build, the three-tier realism layer,
the exhaustive alpha search, and the survivorship-corrected yield work.

**Current honest state (2026-07-22):** After an exhaustive, brutally-honest search
(~6,000 variants across 24 markets × 1h–1d, cross-sectional long-short, regime
detection, intelligent sizing, CEX+DEX+LP+emissions, with DSR/PBO/cross-asset
gates), **no robust directional/cross-sectional alpha survives honest costs in
liquid crypto perps.** The pipeline is sound (no-lookahead evaluator, real costs,
tested). The only real positive return streams are passive **yield**: stablecoin
LP **~3–4%/yr** (low risk) and emissions farming **~6–11%/yr** (hack/depeg-tail-laden).
The tested honest evaluator is the source of truth:
`from slate_core.backtest import backtest, EventBacktester, cscv_pbo, deflated_sharpe, calibrate`.
Earlier `strategy_results.db`/`mega_sweep_results` were selected under a biased
evaluator → untrusted. Full writeup: `HONEST_DISCOVERY_REPORT.pdf`.

---


## 🎯 Quick System Overview

### **Perpetual Futures Trading**
- **Market**: SOLUSDT Perpetual Futures (Binance)
- **Position Types**: Long + Short (perpetual contracts enable both)
- **Backtest Period**: 12 months (Nov 2025 to Jul 2026)
- **Transaction Costs**: Brutally realistic
  - Maker Fee: 0.02% | Taker Fee: 0.05%
  - Slippage: 15 bps (volatility-adjusted)
  - Fill Rate: 80% | Partial Fills: 20%
- **Risk Management**: 3x max leverage, 3% max position size

### **Key Architecture**
- **Discovery Method**: Hypothesis-driven scientific discovery (closed-loop AI)
- **Evolution Layer**: AlphaEvolve-style evolutionary code search (`slate_core/discovery/evolution/`) — runs alongside closed-loop discovery
- **Market Data**: Real SOLUSDT perpetual futures. Default evolution source `sol_data_cache/SOLUSDT_perpetual_1d_36m.csv` = **~1,080 daily bars** (2023-08→present, fetched from Binance) so IS/OOS are hundreds of bars. The loader (`load_data.load_daily_data`) resamples to daily if handed the legacy hourly cache `SOLUSDT_perpetual_1h_6m.csv` (4,182 hourly bars ≈ 175 days). Daily-timeframe edge only.
- **Validation**: 6 pluralistic validation methods with realistic thresholds
- **Learning**: Continuous feedback learning system
- **Server**: Port 8788 with 24/7 autonomous operation

---

## 📚 Modular Documentation (Detailed Information)

**CLAUDE.md is now a quick reference. For detailed information, see:**

- **[CLAUDE_CHANGELOG.md](CLAUDE_CHANGELOG.md)** - Dated change records
- **[CLAUDE_DOCUS.md](CLAUDE_DOCUS.md)** - DEX Discovery Layer (Hyperliquid) detailed reference
- **[CLAUDE_AMM.md](CLAUDE_AMM.md)** - AMM LP Layer (Uniswap V3 yield) detailed reference
- **[CLAUDE_TRADING_FULL.md](CLAUDE_TRADING_FULL.md)** - Trading rules, research findings
- **[CLAUDE_ARCHITECTURE.md](CLAUDE_ARCHITECTURE.md)** - Architecture, file locations, API endpoints

---

## 🚀 Quick Commands

### **Server Operations**
```bash
python3 -m slate_core.server              # start
curl http://127.0.0.1:8788/health | jq   # health
```

### **Discovery Operations**
```bash
curl http://127.0.0.1:8788/api/closed-loop/status | jq
curl -X POST "http://127.0.0.1:8788/api/closed-loop/discovery/start" | jq
```

### **Evolution Operations**
```bash
curl http://127.0.0.1:8788/api/evolution/status | jq
curl -X POST http://127.0.0.1:8788/api/evolution/start | jq
curl -X POST http://127.0.0.1:8788/api/evolution/stop  | jq
```

### **DEX Operations** (`SLATE_PIPELINE=dex`)
```bash
curl http://127.0.0.1:8788/api/dex/status | jq
curl -X POST http://127.0.0.1:8788/api/dex/start | jq
```

### **AMM Operations** (`SLATE_PIPELINE=amm`)
```bash
curl http://127.0.0.1:8788/api/amm/status | jq
curl -X POST http://127.0.0.1:8788/api/amm/start | jq
```

### **Database Operations**
```bash
sqlite3 slate_core/slate_realistic_discoveries.db "SELECT COUNT(*) FROM perpetual_discoveries;"
sqlite3 slate_core/dex_evolution.db "SELECT COUNT(*) FROM evolution_population;"
sqlite3 slate_core/amm_evolution.db "SELECT COUNT(*) FROM evolution_population;"
```

---

## 🎯 GitHub Repository Target

- **SLATE Repository**: https://github.com/Tilanthi/SLATE
- **Push Instructions**: When asked to push to GitHub, **ALWAYS** push **ONLY** to the **main branch** of the SLATE repository
- **Do NOT** push to any other repositories or branches

**Command Verification:**
```bash
pwd  # Should show: /Users/gjw255/astrodata/SWARM/SLATE/
git remote -v  # Should show: https://github.com/Tilanthi/SLATE.git
git branch --show-current  # Should show: main
```

---

## 🟢 Current System Status

**Server**: ✅ Running on port 8788 (launchd `com.slate.autoserver`, `KeepAlive`). Earlier pipelines (closed-loop, evolution, DEX, AMM, portfolio) remain available via `SLATE_PIPELINE=` but are **de-prioritized** — see the verdict below.
**Honest verdict (2026-07-22):** exhaustive search found **no robust directional/cross-sectional alpha** in liquid crypto perps after brutally honest costs (DSR/PBO/cross-asset gates all fail). The realistic positive return streams are passive **yield**: stablecoin LP **~3–4%/yr** (low risk) and emissions farming **~6–11%/yr** (hack/depeg-tail-laden, survivorship-corrected). Strategic implication: **stop searching liquid-perp OHLCV directional alpha**; the sound direction is the yield side, or alpha in inefficient venues / alt-data.
**Source-of-truth evaluator:** `slate_core/backtest/` — `honest.py` (no-lookahead, tested), `event_engine.py` (event-driven + impact + partial fills + maker adverse selection), `validation.py` (CPCV/PBO/DSR), `calibration.py` (live-fill loop), `lp.py` (honest LP), `market_maker.py`. `from slate_core.backtest import backtest`. 26 tests green.
**Market data (real):** CEX SOL daily 1,080 bars (3yr) + 24-coin basket 1d/1h/funding (`sol_data_cache/BASKET_*`); HL hourly; DefiLlama pool histories (`sol_data_cache/yield_pools/`). All regenerable via `fetch_*.py`.
Trajectory + detail in [CLAUDE_CHANGELOG.md](CLAUDE_CHANGELOG.md); report in `HONEST_DISCOVERY_REPORT.pdf`.

---

## 🧬 Evolution Layer (AlphaEvolve-style)

Evolves executable signal code via LLM-guided evolution. Adapted from AlphaEvolve (2025).
**Endpoints:** `/api/evolution/{status,start,stop,seed}` (autostarts on boot;
disable `SLATE_EVOLUTION_AUTOSTART=0`). LLM: GLM via Z.ai proxy (no separate key).

- Overfit cage: correctness gate → IS/OOS split → overfit penalty → absolute-profit
  gate → **two-window gate** (terminal). AST sandbox (no imports/dunder/network). NOTE:
  `EvolutionConfig.validation` advertises a `"walkforward"` option but it is **dead config** —
  `subprocess_eval` always calls `evaluate_fitness_two_window`; no walk-forward step runs in this
  funnel. Walk-forward *does* exist elsewhere: DEX directional fitness (`dex_fitness.py`, anchored
  multi-fold) and closed-loop pluralistic validation (`rigorous_validation.py`).
- **Funding archetypes**: `funding_reversal` (long on extreme negative funding — short squeeze)
  + `funding_carry` (short on high funding). Real Binance funding merged into candles + backtester.
- **Plan:** `docs/superpowers/plans/2026-07-11-alphaevolve-evolution.md`.

## 🔁 DEX Discovery Layer (Hyperliquid)

Separate pipeline exploiting **maker rebates** (zero gas, maker 0.015% < taker 0.045%)
and **sub-daily timescales**. `slate_core/dex/`, own DB + verdict log. CEX untouched.
**Endpoints:** `/api/dex/{status,start,stop}`. Autostart: `SLATE_PIPELINE=dex`.
Targets: `SLATE_DEX_TARGET=` `directional` | `market_maker` | `pairs` | `cross_market`. **Current primary target: `market_maker`** (the maker-rebate edge — `directional` = taker fees = the CEX dead-end; set explicitly because the service defaults to `directional`).
**→ See [CLAUDE_DOCUS.md](CLAUDE_DOCUS.md) for full details.**

## 🏦 AMM LP Layer (Uniswap V3 Yield)

Yield provision (not speculation): concentrated liquidity on stablecoin pairs, 10.8% APY
backtested. `slate_core/amm/`. **Endpoints:** `/api/amm/{status,start,stop}`.
Autostart: `SLATE_PIPELINE=amm`.
**→ See [CLAUDE_AMM.md](CLAUDE_AMM.md) for full details.**

---

## 🛡️ Safety & Constraints

### **Critical Trading Rules**
- ❌ **NO SYNTHETIC DATA** - Only use real market data from exchange APIs
- ✅ **ALWAYS apply realistic costs**: fees (0.02-0.05%), slippage (10-20 bps), fill rates (85-95%)
- 🔍 **Focus on**: daily+ timeframes, market microstructure, liquidation prediction
- ⚠️ **Sub-daily technical indicators** are NOT profitable on efficient exchanges

### **Safety-First Design**
- 📊 **Paper trading only** - NO real money
- 🛡️ **Risk controls** - 3x max leverage, 3% max position size
- 🔄 **Continuous validation** - All strategies must pass statistical tests
- 📈 **Performance monitoring** - Real-time metrics and health checks

---

## 🔧 Development Workflow

### **Making Changes to SLATE**
1. Make code changes
2. **Restart server** (MANDATORY): `pkill -f "python3 -m slate_core.server" && python3 -m slate_core.server`
3. Test changes with discovery cycle
4. Verify changes applied correctly
5. Commit to git if working

### **Testing Validation Fixes**
```bash
# Run discovery cycle to test
curl -X POST "http://127.0.0.1:8788/api/closed-loop/discovery/start" | jq '.'

# Check validation results
curl http://127.0.0.1:8788/api/closed-loop/status | jq '.'

# Monitor database
sqlite3 slate_core/slate_realistic_discoveries.db "SELECT COUNT(*) FROM perpetual_discoveries WHERE timestamp > datetime('now', '-1 hour');"
```

---

## 📖 Key Architecture Files

### **Core Discovery System**
- **Closed-Loop Discovery**: `slate_core/discovery/closed_loop_discovery.py` (850+ lines)
- **Rigorous Validation**: `slate_core/discovery/rigorous_validation.py` (700+ lines)
- **Feedback Learning**: `slate_core/discovery/feedback_learning.py` (650+ lines)
- **Hybrid Strategies**: `slate_core/discovery/hybrid_neurosymbolic.py` (750+ lines)

### **Evolution Layer** (AlphaEvolve-style, `slate_core/discovery/evolution/`)
- **Fitness evaluator**: `fitness_evaluator.py` — IS/OOS split, overfit penalty, absolute-profit gate, two-window gate. Presets: `strict()` / `exploration()`.
- **Program database**: `program_database.py` + `niche.py` — MAP-Elites + islands, `sample()`, seeding, sqlite persistence, **unified write chokepoint** (`append_verified`, machine-verification block required).
- **Funnel diagnostic**: `verdict_log.py` — per-candidate death-stage JSONL log (where candidates die).
- **Prompts**: `prompt_sampler.py` + `meta_prompt_db.py` — rich context + co-evolved meta-instructions + **ALPHA DIRECTIONS / KNOWN-DEAD PATTERNS** steering.
- **Selection**: `pareto.py` + `novelty.py` — multi-objective Pareto + return-correlation novelty.
- **Code evolution**: `signal_sandbox.py` (AST-gated), `evolvable_strategy.py` (EVOLVE-BLOCK + apply_diff).
- **Loop**: `llm_client.py` (GLM via Z.ai proxy), `llm_pool.py` (fast+strong ensemble), `controller.py` (async), `evolution_service.py` (server-hosted), `load_data.py` (daily resample).
- **Plan**: `docs/superpowers/plans/2026-07-11-alphaevolve-evolution.md` · **Docs**: `slate_core/discovery/evolution/README.md` · evolution tests are part of the 150-test green suite.

### **Integration & Server**
- **Integration Layer**: `slate_core/discovery/closed_loop_integration.py` (400+ lines)
- **Server**: `slate_core/server.py` (API endpoints, health checks)
- **Startup Coordinator**: `slate_core/startup_coordinator.py` (auto-restart, watchdog)

### **Database & Market Data**
- **Database**: `slate_core/slate_realistic_discoveries.db` (production, **fresh — cleared 2026-07-11**) · rich history in `slate_realistic_discoveries_backup_20260705_161518.db` (118k rows)
- **Evolution DB**: `slate_core/slate_evolution.db` (persisted population)
- **Market Data**: `sol_data_cache/SOLUSDT_perpetual_1d_36m.csv` — ~1,080 **daily** SOLUSDT-perp bars (2023-08→present); legacy `SOLUSDT_perpetual_1h_6m.csv` = 4,182 hourly bars (loader resamples to daily)

---

*For detailed information on any topic, see the modular documentation files listed above*
*Last Updated: 2026-07-22 — exhaustive honest alpha search concluded (no directional alpha; yield is the positive); honest evaluator + three-tier realism layer + survivorship-corrected yield work in place. Full history + the DEX/AMM/evolution engineering detail in [CLAUDE_CHANGELOG.md](CLAUDE_CHANGELOG.md).*
