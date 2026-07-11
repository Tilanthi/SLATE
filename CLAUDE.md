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

## 🚨 CRITICAL BUGS & FIXES

### **🐛 Zero-Trade Bug (FIXED 2026-07-09)**

**Issue:** Discovery pipeline validated strategies with 0 trades due to type mismatch between hypothesis generation and strategy factory.

**Root Cause:** `HypothesisType.ARBITRAGE` vs `HypothesisType.FUNDING_ARBITRAGE` type mismatch caused signal generation to fail completely.

**Status:** ✅ **FIXED** - Signal generation now working (54 signals vs 0)

**For Details:** See [CLAUDE_CRITICAL_BUG_FIX.md](CLAUDE_CRITICAL_BUG_FIX.md)

### **💰 Funding Arbitrage Bug (FIXED 2026-07-10)**

**Issue:** Funding arbitrage strategy generated 0 trades due to string vs numeric parameter comparison.

**Root Cause:** Hypothesis created `funding_threshold: '0.01%'` (string) causing TypeError in numeric comparison.

**Status:** ✅ **FIXED** - Funding arbitrage now generating 54 trades per cycle

**For Details:** See [CLAUDE_FUNDING_ARBITRAGE_FIX.md](CLAUDE_FUNDING_ARBITRAGE_FIX.md)

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
- **Market Data**: Real SOLUSDT perpetual futures. ⚠️ `SOLUSDT_perpetual_1d_12m.csv` is a JSON array (load with `pd.read_json`, not `read_csv`) of **~4,182 hourly bars ≈ 175 days** despite the "1d" name. The evolution layer resamples it to **daily** (`load_data.load_daily_data`) to match the documented daily-timeframe edge.
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

**Server**: ✅ Running on port 8788
**Database**: Ready for discoveries
**Discovery**: Active with realistic validation thresholds
**Market Data**: 4,182 days of SOLUSDT perpetual futures data

**Recent Fixes Applied (2026-07-09):**
- ✅ Validation thresholds fixed for realistic perpetual futures performance
- ✅ Diagnostic logging added to validation process
- ✅ Server restart requirement documented

**Expected Going Forward:**
- 5-10% validation success rate (vs previous 0%)
- Continuous discovery with 24/7 autonomous operation
- Automatic strategy lifecycle management

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
  A deterministic Mock backend keeps all 78 tests offline.
- **Expected behavior:** most candidates are **rejected** by the gates — that is
  the point. The loop accumulates the rare programs that are genuinely profitable
  OOS on two windows.
- **Endpoints:** `/api/evolution/{status,start,stop,seed}` (autostarts on boot;
  disable with `SLATE_EVOLUTION_AUTOSTART=0`).
- **Plan:** `docs/superpowers/plans/2026-07-11-alphaevolve-evolution.md` (all 6 phases).

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
- **Program database**: `program_database.py` + `niche.py` — MAP-Elites + islands, `sample()`, seeding, sqlite persistence.
- **Prompts**: `prompt_sampler.py` + `meta_prompt_db.py` — rich context + co-evolved meta-instructions.
- **Selection**: `pareto.py` + `novelty.py` — multi-objective Pareto + return-correlation novelty.
- **Code evolution**: `signal_sandbox.py` (AST-gated), `evolvable_strategy.py` (EVOLVE-BLOCK + apply_diff).
- **Loop**: `llm_client.py` (GLM via Z.ai proxy), `llm_pool.py` (fast+strong ensemble), `controller.py` (async), `evolution_service.py` (server-hosted), `load_data.py` (daily resample).
- **Plan**: `docs/superpowers/plans/2026-07-11-alphaevolve-evolution.md` · **Docs**: `slate_core/discovery/evolution/README.md` · **78 tests**.

### **Integration & Server**
- **Integration Layer**: `slate_core/discovery/closed_loop_integration.py` (400+ lines)
- **Server**: `slate_core/server.py` (API endpoints, health checks)
- **Startup Coordinator**: `slate_core/startup_coordinator.py` (auto-restart, watchdog)

### **Database & Market Data**
- **Database**: `slate_core/slate_realistic_discoveries.db` (production, 3 rows) · rich history in `slate_realistic_discoveries_backup_20260705_161518.db` (118k rows)
- **Evolution DB**: `slate_core/slate_evolution.db` (persisted population)
- **Market Data**: `sol_data_cache/SOLUSDT_perpetual_1d_12m.csv` — JSON array of ~4,182 **hourly** bars ≈ 175 days (load with `pd.read_json`; evolution resamples to daily)

---

*For detailed information on any topic, see the modular documentation files listed above*  
*Last Updated: 2026-07-11 (AlphaEvolve-style evolution layer, /api/evolution endpoints, GLM-via-Z.ai LLM, daily-data loader)*
