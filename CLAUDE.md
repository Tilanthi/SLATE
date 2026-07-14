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

### **🔧 Discovery-Pipeline Data-Structure Fix (FIXED 2026-07-11)**

**Issue:** `closed_loop_integration.py` only handled the legacy `raw_results` wrapper and object-format
backtest results, so when the validation system returned a *direct* `validated_strategies` list of
*dict-format* results, strategies could not be matched/saved correctly (wrong field names like
`total_profit_usdt` vs `total_profit`, `max_drawdown_usdt` vs `max_drawdown`, etc.).

**Root Cause:** Field-name drift between the validation dict output and the DB-mapping code, plus a
rigid single-format code path.

**Status:** ✅ **FIXED** — integration now handles both direct+wrapped structures and both
object+dict formats with corrected field names; startup coordinator hardened against duplicate
discovery-loop/watchdog tasks; DB saves now verified by read-back.

### **🐕 launchd Auto-Restart (OPERATIONAL NOTE — corrected 2026-07-11)**

The server is kept alive by the **`com.slate.autoserver`** launchd job (`KeepAlive=true`), which
runs the server **as its main process** (so launchd restarts it directly on crash — no watchdog
script in between).

- **`com.slate.autoserver`** → `ProgramArguments: /Users/gjw255/.local/bin/python3 -m slate_core.server`
  (the uv-managed Python 3.14 that has numpy/pandas/anthropic/fastapi). Its `EnvironmentVariables`
  embed `PYTHONPATH`, `ANTHROPIC_AUTH_TOKEN`, and `ANTHROPIC_BASE_URL` (Z.ai proxy) so the evolution
  layer uses the **real GLM LLM**, not Mock. **This is the job to load.**
- **`com.slate.auto`** → `start_slate.sh`. **Leave UNLOADED.** It backgrounds the server then
  health-checks after only 5 s; because evolution **autostarts during boot** and takes >5 s, the
  check always fails and launchd kills the still-booting server — a death loop. (The plists live in
  `~/Library/LaunchAgents/`, outside the repo.)

**Consequence:** A bare `pkill -f "python3 -m slate_core.server"` does **NOT** stop the server —
launchd respawns it within seconds. To fully stop it (e.g. to work on the DB safely):

```bash
launchctl unload ~/Library/LaunchAgents/com.slate.autoserver.plist
pkill -9 -f "slate_core.server"; lsof -ti:8788 | xargs kill -9 2>/dev/null

# Bring it back (auto-restart resumes); server runs as the job's main process:
launchctl load ~/Library/LaunchAgents/com.slate.autoserver.plist
# Health takes ~15-20 s to come up (evolution autostart is heavy) — don't give up early.
```

If the server is repeatedly failing to start, check `/tmp/slate_server_error.log` — a
`ModuleNotFoundError: No module named 'numpy'` means the plist is pointing at the wrong Python
(should be `/Users/gjw255/.local/bin/python3`, NOT `/usr/bin/python3`).

---

## 🔧 Correctness Fixes (2026-07-11) — the 7 force-multipliers

A deep audit found the pipeline manufactured false confidence. These fixes make
the numbers trustworthy (120 tests, TDD). All verified live.

1. **Lookahead closed** (`perpetual_futures_backtest.py:381`) — the signal now
   receives only `df.iloc[:i+1]`, so evolved code can no longer read future bars.
   Defeatable overfit cage → sound.
2. **Timeframe-aware backtester + daily data** (`perpetual_futures_backtest`,
   `startup_coordinator`) — funding accrual and Sharpe annualization now scale to
   the detected bar frequency (was hardcoded daily on hourly data → 24× funding
   error). The closed-loop now loads **daily** bars via `load_daily_data`
   (matches the documented daily-timeframe edge). Result carries `bars_per_year`.
3. **Deterministic RNG** — backtests seed numpy (config `random_seed`, overridable
   per-candidate via the `seed` param). Same strategy/seed → identical result.
4. **Full backtest result carried to DB** (`convert_backtest_to_dict` now
   comprehensive; integration reads canonical `*_usdt` names) — buy-hold, funding,
   per-trade stats, real prices/period no longer default to 0. Fixes the
   `max_drawdown_usdt`-stored-as-ratio bug.
5. **Validation gate rejects losers** (`rigorous_validation.py` + `closed_loop_discovery.py`)
   — hard profitability floor (`total_profit <= 0` → REJECT) on **both** gates
   (the pluralistic gate AND the hypothesis `is_successful` check, which could
   otherwise score 0.8 from the other four components) + consensus raised to a
   true majority (50%, was 33%). Money-losing strategies can no longer be saved.
6. **No more `-inf` elites** (`controller.py`) — gate-rejected candidates are not
   stored (was: first reject became the niche elite).
7. **Sandbox hardened** (`signal_sandbox.py`) — AST-gates DataFrame write/export
   methods (`to_csv`/`to_pickle`/… ; closes the filesystem leak) and rejects
   unconditional `while True` loops at compile. **Fitness eval now runs in an
   isolated subprocess** (`subprocess_eval.py`) with `RLIMIT_CPU` + wall-clock
   kill, so a non-obvious infinite loop in evolved code can't hang an executor
   thread (the worker-thread DoS hole).

**Follow-ups completed:** test suite un-ignored and committed (24 modules, 124
tests, was wrongly gitignored); regime filter floors small datasets
(`MIN_BARS_FOR_DISCOVERY=120`) so the closed-loop gets enough daily bars to trade
(was 47 → strategies fired 0 trades).

**Current honest state:** with the gates now truthful, the closed-loop saves
**nothing** because every current strategy template loses money on daily SOL
perps after brutal costs — i.e. the system correctly refuses to record fake
edges. The infrastructure is sound; finding a genuinely profitable daily-timeframe
strategy is the remaining research task. The evolution layer (searching signal
*code* rather than parameters) is the more promising path to that edge.

---

## 🔧 Correctness, Search & Hygiene Updates (2026-07-14)

**🔴 P0 repo-integrity fix — the core backtester was never committed.** An
over-broad `.gitignore` rule (`*_backtest.py`, line 72) matched
`slate_core/discovery/perpetual_futures_backtest.py`, and `fetch_*.py` (line 81)
matched `fetch_binance_futures.py`, so **neither core file was tracked**. On a
fresh clone the backtester is absent → every `from ...perpetual_futures_backtest
import …` fails and the suite cannot be collected (this is the real cause of the
"test suite can't collect" symptom an external review flagged — true on a fresh
checkout, false only on a machine with the file locally). Fixed by un-ignoring
both (`!path` negation in `.gitignore`) and tracking them. The backtester lands
with its full current content, so all the 2026-07-11 correctness fixes above are
finally in git (they'd been made to an ignored file). **Lesson: claims below are
now reproducible from a clean clone; before this commit they were machine-local.**

**Behavioural MAP-Elites niches (closes the deferred Phase-3 gap).** The old
controller *inherited* the niche from the parent, so with the closed-loop DB
empty every program collapsed onto one cell (`momentum/unknown`, top-10 tied at
fitness −1776). Added `classify_signal_family` (momentum/mean_reversion/other via
signal↔recent-return correlation) and `classify_active_regime`
(low/med/high_vol = modal rolling-vol tercile of in-market bars) in
`fitness_evaluator.py`; `FitnessResult` carries `family_label`/`regime_label`;
the controller now places each child by its **own** behaviour. **Gotcha that bit
us once:** the classifiers must probe the signal on the **backtester-enriched**
frame (`add_signal_indicators(df)` — the shared EMA injector in
`perpetual_futures_backtest.py`), not the raw df, or every real signal (which
reads `ema_20` etc.) KeyErrors into the `other/unknown` fallback. Verified on the
real mislabelled elite → `momentum/high_vol`.

**Tightened fitness gate (`min_fitness`, default 0.0).** The two-window gate only
required absolute OOS profit > 0, so overfit survivors (IS ~4400 vs OOS ~100,
overfit_gap ~3850) could PASS with fitness −1826 and become niche elites. Now a
candidate is rejected unless its overfit-adjusted fitness (oos_edge −
overfit_penalty) ≥ the floor. With daily-SOL's honest no-edge state this will
likely keep the population near-empty until a real edge appears — that is the
point (stop storing overfit junk as elites).

**Repo hygiene:** added `LICENSE` (MIT, matches the README badge) and
`requirements.txt` / `requirements-dev.txt` pinning the runtime + test deps
(Python 3.14; numpy/pandas/anthropic/fastapi/uvicorn/pyarrow/…). Removed the dead
legacy tests (`slate_core/tests/test_{connectors,languages,strategies}.py` and
`slate_core/test_integration.py`) that imported a defunct layer
(`slate_core.engine`/`connectors.binance`/`languages.haas_script`/`risk.manager`)
and failed every run — **the full suite is now green: 150 passed, 0 failed**
(was 152 passed + 13 dead failures, masked). Renamed the mislabelled cache file
`SOLUSDT_perpetual_1d_12m.csv` → `SOLUSDT_perpetual_1h_6m.csv` (it is 4,182
**hourly** bars ≈ 6 months, not daily/12-month as the old name claimed); all
~30 references across code/tests/scripts/docs + the live server path updated.
`load_data.py` still detects intraday and resamples to daily regardless of name.

---

## 🔧 ASTRA-Derived Discovery-Pipeline Hardening (2026-07-14)

Distilled from ASTRA's 2026-07-11→14 re-architecture (the AlphaEvolve-based
re-architecture + measure→fix→re-measure cycle in
`~/Desktop/Discovery-Pipeline-Lessons-for-Sibling-Projects.md`). Three additive
mechanisms layered on the evolution layer — they *add* to the verification crown
jewel; nothing *replaces* it. **One ASTRA idea was deliberately NOT adopted:** a
literature-novelty "Gate 2" is incoherent for trading (an edge being "in the
literature" says nothing about whether it's tradeable on crypto, and a real
microstructure edge would be wrongly rejected). SLATE's Gate-2 analogue is the
realistic-cost OOS gate it already has.

1. **Unified write chokepoint** (`program_database.py`, ASTRA §7.1) —
   `append_verified(program, verification)` is the single write path for a
   gate-verified candidate and **requires a machine-verification block** (`gate`
   + `real_data_result` + `program_hash`). Both `add()` and `append_verified()`
   **structurally refuse** gate-rejected (`fitness_score == -inf`) candidates, so
   a reject can never become a niche elite (the −inf-elite hole) or reach disk.
   The controller routes every real candidate through `append_verified`; seeds
   carry a `seed:discovery_db_profitable` block. Pinned by regression tests in
   `test_evolution_program_database.py`; a guarded `ALTER` adds `verification_json`
   to existing DBs.

2. **Funnel diagnostic** (`verdict_log.py`, ASTRA §4/§7.2) — every evaluated
   candidate emits one JSONL line to `slate_core/evolution_verdicts.jsonl`
   (gitignored; `SLATE_VERDICT_LOG` overrides) carrying its **death-stage**
   (`correctness → too_few_trades → not_profitable → no_oos_edge →
   overfit_fitness → validation_failed → eval_crash → passed`) plus IS/OOS edges,
   family/regime, and a code hash. Written *inside* the search process,
   independent of stdout, so the failure distribution can be read directly —
   turning "saves nothing" from a conclusion into a measurable hypothesis
   (**where** do candidates die?). Logged at compile-fail / gate-reject / pass in
   `controller.py`.

3. **Proposer primed toward non-obvious edges** (`prompt_sampler.py` +
   `meta_prompt_db.py`, ASTRA §7.5/§6/§7.6) — the evolution prompt now carries an
   **ALPHA DIRECTIONS** block (regime-conditional / residual / non-linear /
   multi-variable-interaction / vol-&-volume-structure — the few structures that
   survive EMH + costs on a liquid major, given the signal only has OHLCV+EMAs)
   and a **KNOWN-DEAD PATTERNS** blacklist (bare RSI, MA crossovers, generic
   momentum, MACD, Bollinger touch — already-arbed; must be ingredients, not the
   whole signal). `meta_prompt_db.DEFAULT_INSTRUCTION` anchored the same way.

**Test suite: 181 passed / 0 failed** (was 150; +31 tests across the chokepoint,
the funnel logger, the controller wiring, and the prompt steering). An autouse
`conftest.py` fixture redirects the verdict logger to tmp during tests.

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
- **Market Data**: Real SOLUSDT perpetual futures. `sol_data_cache/SOLUSDT_perpetual_1h_6m.csv` is a JSON array (load with `pd.read_json`, not `read_csv`) of **~4,182 hourly bars ≈ 175 days** (renamed from the misleading `1d_12m` on 2026-07-14). The evolution layer resamples it to **daily** (`load_data.load_daily_data`) to match the documented daily-timeframe edge.
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

**Server**: ✅ Running on port 8788 (launchd-managed, `com.slate.autoserver` — server runs as the job's main process under direct `KeepAlive`)
**Database**: ✅ **Fresh — discovery tables cleared 2026-07-11** (`perpetual_discoveries` = 0, `edge_discoveries` = 0). Backup at `slate_core/slate_realistic_discoveries_backup_20260711_121642.db`.
**Discovery**: Active with realistic validation thresholds, restarted fresh after the 2026-07-11 data-structure fix
**Evolution Layer**: Active (autostart, real GLM/Z.ai LLM). **Behavioural MAP-Elites niches** (family × regime, derived per-candidate) + **`min_fitness` gate** (rejects overfit-adjusted-fitness < 0) landed 2026-07-14; population **cleared to a clean slate 2026-07-14** for those fixes — niches diversify correctly now and overfit `−1800s` survivors are no longer stored (`slate_evolution.db`; pre-clear backups at `slate_evolution_backup_*.db`).
**Market Data**: 4,182 hourly bars ≈ 175 days of SOLUSDT perpetual futures data (resampled to daily by the evolution loader)

**Recent Architectural Changes Applied (2026-07-11):**
- ✅ `closed_loop_integration.py` — handles direct + wrapped structures, object + dict formats, corrected field names (strategies now save with real backtest values)
- ✅ `startup_coordinator.py` — guards against duplicate discovery-loop / watchdog tasks; correct restart-after-hang
- ✅ `perpetual_database.py` — save verified by read-back
- ✅ Discovery DB cleared for a clean run under the corrected code path

**Expected Going Forward:**
- 5-10% validation success rate with realistic thresholds
- Continuous discovery (closed-loop) + code evolution (AlphaEvolve-style) running 24/7
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
  A deterministic Mock backend keeps the evolution tests offline (part of the 150-test green suite).
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
- **Market Data**: `sol_data_cache/SOLUSDT_perpetual_1h_6m.csv` — JSON array of ~4,182 **hourly** bars ≈ 175 days (load with `pd.read_json`; evolution resamples to daily)

---

*For detailed information on any topic, see the modular documentation files listed above*
*Last Updated: 2026-07-14 (ASTRA-derived hardening: unified write chokepoint `append_verified` requiring a machine-verification block + structural −inf rejection; funnel diagnostic `verdict_log.py` logging per-candidate death-stage to JSONL; proposer primed toward non-obvious edges via ALPHA DIRECTIONS + KNOWN-DEAD PATTERNS; deliberately did NOT adopt ASTRA's literature-novelty Gate 2 as it is incoherent for trading — see ASTRA-Derived Hardening 2026-07-14 above. 🔴 core backtester + data fetcher were gitignored & missing from repo → now tracked, suite collects on fresh clone; behavioural MAP-Elites niches + `add_signal_indicators` injected-columns fix so real signals label correctly; `min_fitness` gate rejects overfit `−1800s` survivors; LICENSE + pinned `requirements.txt`; dead legacy tests removed → full suite green **181 passed/0 failed**; cache file renamed `1d_12m`→`1h_6m` (was mislabelled daily) — see Correctness Updates 2026-07-14 above)*
