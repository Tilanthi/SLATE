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

- **[CLAUDE_TRADING_FULL.md](CLAUDE_TRADING_FULL.md)** - Complete trading rules, research findings, critical constraints
- **[CLAUDE_PHASE2_INTELLIGENCE.md](CLAUDE_PHASE2_INTELLIGENCE.md)** - Trading Intelligence Layer details (5 core components)
- **[CLAUDE_ANALYTICS.md](CLAUDE_ANALYTICS.md)** - Performance metrics, analytics capabilities, data analysis findings
- **[CLAUDE_ARCHITECTURE.md](CLAUDE_ARCHITECTURE.md)** - System architecture, file locations, API endpoints
- **[CLAUDE_OPERATIONAL_STATUS.md](CLAUDE_OPERATIONAL_STATUS.md)** - Current live operational status and system state
- **[CLAUDE_COMMANDS.md](CLAUDE_COMMANDS.md)** - Complete command reference for all operations
- **[CLAUDE_CHANGELOG.md](CLAUDE_CHANGELOG.md)** - Dated change records (correctness fixes, ASTRA hardening, funnel, data lever, complexity cap)

---

## 🚀 Quick Commands

### **Server Operations**
```bash
# Start SLATE server
python3 -m slate_core.server

# Check health
curl http://127.0.0.1:8788/health | jq '.'

# Restart server (MANDATORY after code changes)
pkill -f "python3 -m slate_core.server" && sleep 2 && python3 -m slate_core.server
```

### **Discovery Operations**
```bash
# Discovery status
curl http://127.0.0.1:8788/api/closed-loop/status | jq '.'

# Start discovery cycle
curl -X POST "http://127.0.0.1:8788/api/closed-loop/discovery/start" | jq '.'

# System performance
curl http://127.0.0.1:8788/api/closed-loop/performance | jq '.'
```

### **Evolution Operations** (AlphaEvolve-style loop)
```bash
# Evolution status (running, niches, best fitness, cycle counts)
curl http://127.0.0.1:8788/api/evolution/status | jq '.'

# Start / stop the background evolution loop
curl -X POST http://127.0.0.1:8788/api/evolution/start | jq '.'
curl -X POST http://127.0.0.1:8788/api/evolution/stop  | jq '.'

# Seed the population from existing discoveries
curl -X POST "http://127.0.0.1:8788/api/evolution/seed?limit=200" | jq '.'
```
The loop **autostarts** with the server (disable with `SLATE_EVOLUTION_AUTOSTART=0`).
It uses the `exploration` gate preset and GLM via the Z.ai proxy by default.

### **Database Operations**
```bash
# Access database
sqlite3 slate_core/slate_realistic_discoveries.db

# Count discoveries
sqlite3 slate_core/slate_realistic_discoveries.db "SELECT COUNT(*) FROM perpetual_discoveries;"

# Check validated strategies
sqlite3 slate_core/slate_realistic_discoveries.db "SELECT COUNT(*) FROM perpetual_discoveries WHERE passed_validation > 0;"
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
**Discovery stores**: `perpetual_discoveries` = 0, `evolution_population` = 0 — both empty. Honest state: nothing is stored because nothing clears the realistic-cost gates.
**Closed-loop**: active (hypothesis-driven, 6 validators). Generates hypotheses; stores nothing.
**Evolution Layer**: active (autostart, real GLM via Z.ai proxy). AlphaEvolve-style code search: write chokepoint (`append_verified`), overfit-resistant two-window gate, behavioural MAP-Elites niches, seed-archetype diversity, activity-credit in fitness, AST-node complexity cap (default 200), per-candidate funnel log (`slate_core/evolution_verdicts.jsonl`).
**Market Data**: ~1,080 daily SOLUSDT-perp bars (2023-08→present, `SOLUSDT_perpetual_1d_36m.csv`); legacy 6-month hourly cache still present. Loader resamples to daily.
**Current diagnosis (funnel)**: every candidate overfits IS≫OOS (IS≈4,420 vs OOS≈92) — the open problem is the overfit gap, now addressed structurally via more data (1,080 bars) + the complexity cap. Trajectory in [CLAUDE_CHANGELOG.md](CLAUDE_CHANGELOG.md).

---

## 🧬 Evolution Layer (AlphaEvolve-style)

A second discovery engine that **evolves executable signal code** via LLM-guided
evolution, running alongside the hypothesis-driven closed-loop. Adapted from
Google DeepMind's AlphaEvolve (2025).

- **Why two engines:** the closed-loop searches *parameters* of fixed templates;
  the evolution layer searches the *signal logic itself* (much larger space), but
  inside a hard overfit-resistant cage.
- **Overfitting is the crux.** Unlike AlphaEvolve's ground-truth evaluators,
  SLATE's backtest is an inductive proxy, so the fitness function is built to
  resist curve-fitting: correctness gate → IS/OOS split → overfit penalty →
  absolute-profit gate → **two-window gate** (must profit on two independent OOS
  windows). Evolved code runs in an AST sandbox (no imports/dunder/network),
  clamped to `{-1,0,1}`, never touching the safety envelope.
- **LLM with no Anthropic key:** the user runs GLM via Claude Code, which routes
  through Z.ai's Anthropic-protocol-compatible proxy (`ANTHROPIC_BASE_URL` /
  `ANTHROPIC_AUTH_TOKEN`). `evolution/llm_client.py` reuses that proxy via the
  `anthropic` SDK (model `claude-sonnet-5`), so **no separate key is needed**.
  A deterministic Mock backend keeps the evolution tests offline (part of the 150-test green suite).
- **Expected behavior:** most candidates are **rejected** by the gates — that is
  the point. The loop accumulates the rare programs that are genuinely profitable
  OOS on two windows.
- **Endpoints:** `/api/evolution/{status,start,stop,seed}` (autostarts on boot;
  disable with `SLATE_EVOLUTION_AUTOSTART=0`).
- **Plan:** `docs/superpowers/plans/2026-07-11-alphaevolve-evolution.md` (all 6 phases).

## 🔁 DEX Discovery Layer (Hyperliquid)

A separate discovery pipeline for Hyperliquid (DEX), built to exploit what CEX
can't: **maker rebates** (zero gas; maker 0.015% < taker 0.045%, negative-maker
rebates at high maker-fraction) and **sub-daily timescales**. CEX code is
untouched; the DEX layer lives in `slate_core/dex/` with its own DB
(`slate_core/dex_evolution.db`) and verdict log (`slate_core/dex_verdicts.jsonl`).

- **Reuse:** the venue-agnostic crown jewel is shared — write chokepoint
  (`append_verified`), funnel (`verdict_log`), AST sandbox + complexity cap,
  `FitnessResult`/two-window/overfit/activity gates, `ProgramDatabase`, `LLMPool`.
  The DEX evolved unit is a CEX-form `signal_fn(df,i,params)->{-1,0,1}`, so the
  sandbox/SEARCH-REPLACE machinery is reused verbatim.
- **DEX-specific:** `dex/data/` (first-party HL candles + funding, 5,000-candle
  accumulating store), `dex/backtester/` (bar-level: maker/taker fee split +
  rebates, oracle rejection, min-notional, leverage cap, funding), and a richer
  `act(state)->list[Order]` action model with **Directional** (Market-executed —
  Alo/post-only left ~40% of candidates 0-trade on 1h data, a fill confound;
  maker-rebate capture is the **MarketMaker** archetype's job) and **MarketMaker**
  (two-sided quoting + inventory skew + rebate) archetypes.
- **L2/trade feed (definitive MM fills):** `bar_fill_l2` adds a queue gate (a maker
  fills only if the bar's traded volume consumes the queue ahead of it); the
  backtester takes an optional `l2_provider` (pluggable seam; `HLClient.l2_book`
  supplies real-time snapshots). Without a provider it falls back to the bar proxy
  (indicative). Dense historical L2/trade data needs a third-party feed.
- **Evolvable MM quoting:** the market-maker's `quote_fn(state)->(half_spread_bps,
  inv_skew_bps, size)` is sandbox-compiled (`compile_function`, no {-1,0,1} clamp)
  and evolved via `dex_mm_evolution_step` + `evaluate_dex_mm_fitness` (same crown
  jewel). The service `target` selects directional (default) vs market_maker.
- **Honest v1 limits:** funding uses a constant rate; bar-level fills without an
  L2 provider are indicative. Backtester is **lookahead-safe** (decide at bar i,
  fill at i+1). Paper/discovery only — never places live HL orders.
- **Complexity cap:** DEX uses **350** AST nodes (vs CEX 200) — measured DEX
  signals cluster at 201-350 (p50=277, p90=341), so cap 200 rejected 68% pre-eval
  and starved the funnel. The overfit gate is the primary defense; the cap is a
  secondary guardrail that now blocks only the baroque tail (>350). Tunable via
  `DexEvolutionService(max_signal_complexity=...)`.
- **Validation (overfit defense):** DEX directional fitness uses **anchored
  walk-forward** — 5 folds, each training on all data up to a block and testing on
  the next; a candidate must profit on **all** independent OOS folds (not one
  split), a far stronger overfit defense. Selectable via
  `EvolutionConfig.validation` ("walkforward", DEX default | "two_window").
- **Run it:** `/api/dex/{status,start,stop}` (always available). Autostart via
  `SLATE_PIPELINE=dex` (default `cex`); DEX target via `SLATE_DEX_TARGET=market_maker`
  (default `directional`). Suite: **237 passed / 0 failed**.
  Plan: `docs/superpowers/plans/2026-07-15-dex-hyperliquid-discovery.md`.

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
*Last Updated: 2026-07-15 (data lever: default to ~1,080 real daily SOL bars `SOLUSDT_perpetual_1d_36m.csv` so IS/OOS are ~540/216 bars, not ~87/35; complexity cap: reject over-complex evolved signals pre-eval (death-stage `too_complex`). CLAUDE.md pruned — detailed change records moved to `CLAUDE_CHANGELOG.md`. Earlier 2026-07-15: activity-credit in fitness; funnel-sharpening (`death_stage`=first gate + `failed_gates`, reject labels, archetype diversity, trade-frequency directive). 2026-07-14: ASTRA-derived write chokepoint `append_verified` + funnel `verdict_log.py` + proposer priming (ALPHA DIRECTIONS / KNOWN-DEAD PATTERNS); deliberately did NOT adopt ASTRA's literature-novelty Gate 2 (incoherent for trading). 🔴 core backtester + fetcher were gitignored → now tracked; behavioural MAP-Elites niches; `min_fitness` gate; LICENSE + pinned `requirements.txt`; dead legacy tests removed → full suite green **195 passed/0 failed**.)*
