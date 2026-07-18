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

Detailed dated records — correctness fixes, ASTRA-derived hardening, the funnel,
activity-credit, the **data lever (1,080 daily bars)**, and the **complexity cap**
— live in **[CLAUDE_CHANGELOG.md](CLAUDE_CHANGELOG.md)**.

**Current honest state:** the closed-loop saves nothing (every template loses
money after costs); the evolution funnel shows every candidate overfits IS≫OOS.
The infrastructure is sound and well-instrumented; the remaining work is the science.

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

**Server**: ✅ Running on port 8788 (launchd `com.slate.autoserver`, `KeepAlive`).
**Primary pipeline (2026-07-18 pivot): DEX `market_maker`** — the 24/7 server now runs `SLATE_PIPELINE=dex` + `SLATE_DEX_TARGET=market_maker`, aimed at the maker-rebate edge (honest Hyperliquid economics; MM validated by walk-forward, absolute profit per fold). AMM paused; CEX closed-loop discovery continues in the background as the "lesser extent". Prior focus (AMM yield-clones, CEX directional) is de-prioritized: AMM is a known ~10% yield (income, not alpha); CEX directional is 0/1,783 after costs.
**Discovery stores**: `perpetual_discoveries` = 0, CEX `evolution_population` = 0 — nothing clears the realistic-cost gates (CEX daily-timeframe directional edge remains unfound). DEX MM population: 12 walk-forward-confirmed survivors (pre-walk-forward gate); AMM: 116.
**Closed-loop (CEX)**: active in background (hypothesis-driven, 6 validators). Generates hypotheses; stores nothing.
**Evolution Layer (CEX)**: available but idle — superseded by the DEX-primary focus.
**Market Data**: ~1,080 daily SOLUSDT-perp bars (CEX); DEX uses 5,002 hourly Hyperliquid SOL bars (`sol_data_cache/HYPERLIQUID_SOL_1h.json`).
**Current diagnosis**: the engineering blockers to answering "is there DEX maker-rebate alpha after brutal costs?" are removed (pipeline aimed at MM, compile attrition fixed, walk-forward validation added). Whether a walk-forward-confirmed rebate edge survives the cost gate is the open empirical question. Trajectory in [CLAUDE_CHANGELOG.md](CLAUDE_CHANGELOG.md).

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
*Last Updated: 2026-07-18 (**Verified HL fees + stigmergic guidance** — encoded the real HL perp fee tiers into `economics.py` (`hl_perp_fee_schedule`): maker steps +0.015%→0.000% at >$500M 14d vol, rebates −0.001/−0.002/−0.003% whale-gated (>0.5/1.5/3% of venue). Empirical rebate test on real L2: retail MM loses (−17 @1bps), zero-maker is break-even within adverse-selection uncertainty (+0.4), whale rebate thin (+3.8) — brutal-cost verdict holds. Also wired native **pheromone guidance** (`MMPheromoneStore` + `PheromoneHypothesisMapper`) into the MM optimizer — stigmergic memory biases mutations toward profitable regions. Suite 301 green. Details in `CLAUDE_CHANGELOG.md`).* Earlier 2026-07-18 — **Native (LLM-free) market-maker discovery on tick/L2 data** — the MM variation operator is no longer GLM; it's a native GA + MAP-Elites optimizer over `(half_spread, inv_skew, size)` evaluated by a realistic tick/L2 backtester with price-time-priority fills + adverse-selection capture on real `L2_SOL.jsonl` snapshots. Zero LLM calls in the MM path. Suite 296 green. Earlier 2026-07-18 — Strategic pivot: **DEX `market_maker` is now the primary discovery pipeline** — 24/7 server repointed `SLATE_PIPELINE` amm→dex + `SLATE_DEX_TARGET=market_maker`, aimed at the maker-rebate edge. AMM paused; CEX closed-loop continues as "lesser extent". Added **walk-forward validation for market-makers** and the concise/must-return anti-truncation prompt fix to all 3 DEX prompts. Live: DEX MM compile rate 71%→0%, 12/12 MM candidates, walk-forward gated. Suite 280 green. Earlier 2026-07-17 — AMM LP "never enters" fix: LLM output was **truncated at max_tokens=1024 before the `return`** → 9/10 candidates returned None→HOLD→0 entries; also `min_trades=5` (CEX preset) killed correct enter-and-hold LPs. Fixed: `max_tokens` 1024→2048, LP prompt now mandates concise code + a `return` + prefer being ENTERed, and LP uses `min_trades=1`. Live: 0 compile / 0 never-entered / **50% passed** (was ~0.4%); new top survivor +10.2% OOS APY, zero overfit. Suite 279 green. Details in `CLAUDE_CHANGELOG.md`). Same day — AMM compile-attrition fix: `_BLOCK_RE` now treats the `>>>>>>> REPLACE` terminator as **optional** — GLM omits it, so ~98% of AMM candidates died at compile on leaked markers; live compile rate dropped 99%→31%. Same day — full `slate_core` audit: 214 files, 273 tests green. Fixed 3 real bugs — **closed loop now loads daily bars** (`load_daily_data`, both `server.py` call sites; was hourly `1h_6m.csv` → every `rolling(20)` was 20 hours not 20 days); **feedback learning now receives real hypotheses** (`run_rigorous_validation` passes 1:1-paired `strategy_hypotheses` instead of `[]`, so patterns are actually extracted); **logger defined before guarded imports** (was a latent `NameError`). Also fixed: latent `LP_SEED_ARCHETYPES` import; `*_pct` double-divide (`total_return`/`max_drawdown` were 100× too small); dead imports (server + amm); stale docstring/dead `hasattr` branches/orphan comment; deleted stale `realistic_backtester.cpython-314.pyc`. Doc correction: core evolution overfit cage ends at the **two-window gate** — `EvolutionConfig.validation`'s `walkforward` is dead config, not a 5-fold step. Earlier 2026-07-15: data lever (~1,080 daily SOL bars so IS/OOS ~540/216, not ~87/35); complexity cap (death-stage `too_complex`); activity-credit in fitness; funnel-sharpening; CLAUDE.md pruned → detailed records in `CLAUDE_CHANGELOG.md`. 2026-07-14: ASTRA-derived write chokepoint `append_verified` + funnel `verdict_log.py` + proposer priming; 🔴 core backtester + fetcher were gitignored → now tracked; behavioural MAP-Elites niches; `min_fitness` gate; LICENSE + pinned `requirements.txt`.)*
