# AlphaEvolve-Style Evolution for SLATE — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **STATUS AS OF 2026-07-11: ALL PHASES COMPLETE.** Phases 0–5 are implemented, 66 tests green, and the full loop is verified end-to-end on real data with both the mock LLM and the live GLM (Z.ai proxy, no Anthropic key needed). See `slate_core/discovery/evolution/README.md`. Phases 2–5 below are retained as the design rationale; the actual implementations live in the package (prompt_sampler, meta_prompt_db, pareto, novelty, signal_sandbox, evolvable_strategy, llm_client, llm_pool, controller). The LLM-key workaround is in `llm_client.py`: reuse `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN` (Z.ai) via the `anthropic` SDK, with a deterministic Mock backend for all tests.

**Goal:** Bring the high-value, low-risk advances from the AlphaEvolve paper (Google DeepMind, 2025) into SLATE's discovery pipeline — an overfit-resistant fitness evaluator and an accumulating, diversity-maintained program database (MAP-Elites + islands) — without exposing the system to the overfitting failure mode that an inductive (backtest) evaluator creates.

**Architecture:** Additive layers under a new `slate_core/discovery/evolution/` package. Phase 0 wraps the existing brutal-realism backtester + the existing `PluralisticValidationSystem` into one `evaluate_fitness()` that splits in-sample/out-of-sample, penalizes the IS↔OOS gap (overfit penalty), and enforces correctness-by-construction. Phase 1 adds a `ProgramDatabase` (MAP-Elites grid over niche = strategy-family × regime, plus an island exploration pool) seeded from the 28,401 existing `perpetual_discoveries` rows, exposing the AlphaEvolve controller primitive `sample() -> (parent, inspirations)`. Existing parameter-GA (`genetic_optimizer.py`) and template generators keep running unchanged.

**Tech Stack:** Python 3, pandas/numpy, sqlite3 (stdlib), pytest. No new runtime dependencies. Reuses `PerpetualFuturesBacktester`, `PerpetualBacktestResult`, `PluralisticValidationSystem`, `PerpetualDatabaseManager`.

## Global Constraints (apply to every task)

- ❌ **NO SYNTHETIC MARKET DATA for strategy evaluation.** All fitness evaluation runs on the real `sol_data_cache/SOLUSDT_perpetual_1d_12m.csv`. **This file is a JSON array despite the `.csv` extension** — load it with `pd.read_json(...)`, NOT `pd.read_csv` (matches `server.py:362`). Columns include `timestamp, open, high, low, close, volume, atr, rsi, macd, ...` (no `date` column). Unit tests may load a small *slice of the real data* as a fixture — never fabricate OHLCV rows. (Deterministic dummy `signal_function` callables in tests are fine — they are strategy stubs, not market data.)
- ⚠️ **Known pre-existing inconsistency:** the `1d` filename and CLAUDE.md say "daily", but the data is actually **hourly** bars (4182 rows ≈ 175 days, 2026-01-08 → 2026-07-01). Phase 0/1 does not resolve this — the backtester runs on any OHLCV rows. Flagged for the user; out of scope here.
- ✅ **Daily timeframe only.** `timeframe = "1d"`. Per SLATE research, sub-daily indicators are not profitable; evolution must not "rediscover" overfit sub-daily edges.
- ✅ **Realistic costs are already applied** by the backtester (maker 0.02%, taker 0.05%, 15bps slippage, 80% fill, 20% partial). Do not weaken them.
- 🛡️ **Safety envelope is never evolved.** Position sizing, leverage (3x), drawdown limit, and execution live in the backtester skeleton. Evolved code (Phase 4+) may only produce bounded signals — it may never touch sizing/leverage/order logic.
- 🔄 **MANDATORY server restart after any code change:** `pkill -f "python3 -m slate_core.server" && sleep 2 && python3 -m slate_core.server`.
- 🔁 **Determinism inside an evaluation:** seed `numpy.random` before each backtest so a given candidate's fitness is reproducible (evolution needs stable comparisons). Seed must be a function of the candidate id, not wall-clock.
- 📄 **Commits:** frequent, one logical change each, conventional-commit messages. Push only to `main` of https://github.com/Tilanthi/SLATE.
- 📄 **Test files are gitignored** (`.gitignore:80` → `test_*.py`; zero existing root tests are tracked). Do NOT `git add -f` test files — respect the convention. Tests live locally; all test code is reproduced inline in this plan so the suite is rebuildable on restart. Commit steps therefore commit the *implementation* file(s) only; `git add test_*.py` will be silently skipped.
- 🧪 **TDD:** every Phase 0/1 deliverable is written test-first against a real-data slice.

## File Structure (new package: `slate_core/discovery/evolution/`)

| File | Responsibility | Phase |
|---|---|---|
| `evolution/__init__.py` | Package marker + public re-exports. | 0 |
| `evolution/fitness_evaluator.py` | `evaluate_fitness(signal_fn, params, df) -> FitnessResult`. IS/OOS split, overfit penalty, correctness gate, delegates to backtester + `PluralisticValidationSystem`. | 0 |
| `evolution/program_database.py` | `ProgramDatabase` (MAP-Elites + islands), `Program`, niche descriptor, `sample()`, `seed_from_discoveries()`, sqlite persistence. | 1 |
| `evolution/niche.py` | Pure function `compute_niche(strategy_meta) -> tuple` defining the MAP-Elites grid cell. | 1 |
| `evolution/controller.py` | The async evolution loop (controller + samplers + eval nodes). | 5 |
| `evolution/prompt_sampler.py` | Assembles rich-context prompts (parent + inspirations + scores). | 2 |
| `evolution/signal_sandbox.py` | Restricted compile/exec of evolved signal code with bounds + timeout checks. | 4 |

**Tests live at the repo root (matches existing SLATE convention — root-level `test_*.py`, no `tests/` dir).**
| Test file | Covers | Phase |
|---|---|---|
| `conftest.py` (root) | `sol_slice` fixture (real data via `pd.read_json`). | 0 |
| `test_evolution_fitness.py` (root) | Phase 0 tests. | 0 |
| `test_evolution_program_database.py` (root) | Phase 1 tests. | 1 |

Existing files touched (Phase 0/1): none modified in a breaking way. Phase 0/1 are purely additive. Integration into the live discovery cycle happens in Phase 2+.

---

# PHASE 0 — Overfit-resistant fitness evaluator (IMPLEMENTING NOW)

**Why first:** the paper's results all rest on ground-truth evaluators; SLATE's backtest is an inductive proxy, so overfitting is the make-or-break risk. Everything downstream is worthless if the fitness function rewards curve-fitting. We do this before any evolution.

**Reused machinery (do NOT rebuild):**
- `PerpetualFuturesBacktester.backtest_strategy(df, strategy_name, strategy_description, edge_type, signal_function, parameters) -> PerpetualBacktestResult` (`perpetual_futures_backtest.py:298`).
- `signal_function(df, i, parameters) -> int` returns `1` (long), `-1` (short), or `0` (flat) — called at `perpetual_futures_backtest.py:381`.
- `PluralisticValidationSystem` + `get_rigorous_validation_system()` (`rigorous_validation.py:634, 784`) — already has walk-forward, bootstrap, Monte Carlo, regime-stress, parameter-sensitivity, cost-sensitivity.
- `PerpetualBacktestResult` dataclass (`perpetual_futures_backtest.py:84`); convert to dict with `dataclasses.asdict(result)`.

### Task 0.1: Package scaffold + fixtures

**Files:**
- Create: `slate_core/discovery/evolution/__init__.py`
- Create: `slate_core/discovery/evolution/fitness_evaluator.py` (empty stub with docstring only)
- Create: `tests/discovery/evolution/__init__.py`
- Create: `tests/discovery/evolution/conftest.py` — pytest fixture returning a real-data slice.

**Interfaces:**
- Produces: `sol_slice` fixture (`pd.DataFrame`, ~120 rows of real daily SOL data with a `close` column) for all later tests.

- [ ] **Step 1: Create package + test dirs and `__init__.py` files**

```python
# slate_core/discovery/evolution/__init__.py
"""AlphaEvolve-style evolutionary discovery layer for SLATE.

Phase 0: overfit-resistant fitness evaluator.
Phase 1: program database (MAP-Elites + islands).
"""
```

```python
# tests/discovery/evolution/__init__.py
```

- [ ] **Step 2: Write the fixture (real-data slice, not synthetic)**

```python
# tests/discovery/evolution/conftest.py
import pandas as pd
import pytest
from pathlib import Path

REAL_DATA = Path("sol_data_cache/SOLUSDT_perpetual_1d_12m.csv")  # JSON array, .csv ext

@pytest.fixture(scope="session")
def sol_slice() -> pd.DataFrame:
    """A 120-row slice of REAL SOL perpetual data for fast tests."""
    assert REAL_DATA.exists(), f"Real market data not found at {REAL_DATA.resolve()}"
    df = pd.read_json(REAL_DATA)                       # NOTE: read_json, not read_csv
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp").sort_index()
    assert "close" in df.columns
    return df.head(120).copy()
```

- [ ] **Step 3: Stub the module under test**

```python
# slate_core/discovery/evolution/fitness_evaluator.py
"""Overfit-resistant fitness evaluator (Phase 0). Implemented in Task 0.2+."""
```

- [ ] **Step 4: Verify the fixture loads real data**

Run: `python3 -c "import pandas as pd; df=pd.read_json('sol_data_cache/SOLUSDT_perpetual_1d_12m.csv'); print(len(df), [c for c in df.columns][:6])"`
Expected: `4182 ['timestamp', 'open', 'high', 'low', 'close', 'volume']`. (Confirmed 2026-07-11.)

- [ ] **Step 5: Commit**

```bash
git add slate_core/discovery/evolution/__init__.py slate_core/discovery/evolution/fitness_evaluator.py tests/discovery/evolution/
git commit -m "feat(evolution): scaffold evolution package and real-data test fixture"
```

### Task 0.2: Correctness-by-construction gate (test-first)

**Files:**
- Modify: `slate_core/discovery/evolution/fitness_evaluator.py`
- Test: `tests/discovery/evolution/test_fitness_evaluator.py`

**Interfaces:**
- Produces: `FitnessConfig` dataclass; `check_signal_correctness(signal_fn, df, parameters) -> tuple[bool, str]`.

**Design:** Before any backtest, verify the candidate signal function returns only finite values in `{-1, 0, 1}` for every bar in a short probe window. Reject anything else with a reason. This is the AlphaEvolve "correctness by construction" gate adapted to trading (mirrors their randomized-input correctness checks).

- [ ] **Step 1: Write the failing test**

```python
# tests/discovery/evolution/test_fitness_evaluator.py
import numpy as np
import pandas as pd
from slate_core.discovery.evolution.fitness_evaluator import (
    FitnessConfig, check_signal_correctness,
)

def test_correctness_accepts_valid_signals(sol_slice):
    def good_signal(df, i, params):
        return 1 if df["close"].iloc[i] > df["close"].iloc[i-1] else -1
    ok, reason = check_signal_correctness(good_signal, sol_slice, {})
    assert ok is True
    assert reason == ""

def test_correctness_rejects_unbounded_output(sol_slice):
    def bad_signal(df, i, params):
        return 999.0  # not in {-1,0,1}
    ok, reason = check_signal_correctness(bad_signal, sol_slice, {})
    assert ok is False
    assert "bounded" in reason.lower() or "invalid" in reason.lower()

def test_correctness_rejects_nan(sol_slice):
    def nan_signal(df, i, params):
        return float("nan")
    ok, reason = check_signal_correctness(nan_signal, sol_slice, {})
    assert ok is False

def test_correctness_rejects_exceptions(sol_slice):
    def crash_signal(df, i, params):
        raise RuntimeError("boom")
    ok, reason = check_signal_correctness(crash_signal, sol_slice, {})
    assert ok is False
    assert "exception" in reason.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/discovery/evolution/test_fitness_evaluator.py -v`
Expected: FAIL with `ImportError` (symbols not defined).

- [ ] **Step 3: Implement minimal code**

```python
# slate_core/discovery/evolution/fitness_evaluator.py
"""Overfit-resistant fitness evaluator for SLATE evolution (Phase 0)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Tuple
import math
import numpy as np
import pandas as pd

SignalFn = Callable[[pd.DataFrame, int, Dict[str, Any]], float]
VALID_SIGNALS = {-1, 0, 1}


@dataclass
class FitnessConfig:
    """Knobs for evaluate_fitness. Defaults are conservative."""
    is_fraction: float = 0.6           # first 60% of bars = in-sample
    overfit_penalty_weight: float = 1.0
    min_trades: int = 10               # gate: enough activity to be meaningful
    require_beat_buyhold_oos: bool = True
    # Pluralistic validation is EXPENSIVE (bootstrap 1000 + MC 1000 sims) and
    # several validators need additional_data we don't have inside the inner
    # evolution loop. Default OFF: Phase 0's overfit defense is the IS/OOS
    # split + overfit penalty + beat-buy-hold-OOS gate. Turn ON only for
    # finalists. When off, validation_score is neutral (1.0) and the floor
    # gate is skipped.
    run_pluralistic_validation: bool = False
    validation_score_floor: float = 0.4  # only applied when validation is ON
    random_seed: int = 12345           # determinism per evaluation
    probe_window: int = 30             # bars used by correctness gate


def check_signal_correctness(
    signal_fn: SignalFn, df: pd.DataFrame, parameters: Dict[str, Any],
    probe_window: int = 30,
) -> Tuple[bool, str]:
    """Return (ok, reason). ok=False rejects the candidate before backtest."""
    start = min(probe_window, max(0, len(df) - 1))
    for i in range(20, start):  # 20 = backtester warmup
        try:
            sig = signal_fn(df, i, parameters)
        except Exception as exc:  # noqa: BLE001 - any failure = reject
            return False, f"exception at bar {i}: {exc}"
        if sig is None or isinstance(sig, float) and math.isnan(sig):
            return False, f"NaN/None signal at bar {i}"
        if sig not in VALID_SIGNALS:
            return False, f"signal {sig!r} at bar {i} not bounded to {{-1,0,1}}"
    return True, ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/discovery/evolution/test_fitness_evaluator.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add slate_core/discovery/evolution/fitness_evaluator.py tests/discovery/evolution/test_fitness_evaluator.py
git commit -m "feat(evolution): add correctness-by-construction signal gate"
```

### Task 0.3: In-sample / out-of-sample split + backtest runner

**Files:**
- Modify: `slate_core/discovery/evolution/fitness_evaluator.py`
- Test: `tests/discovery/evolution/test_fitness_evaluator.py`

**Interfaces:**
- Consumes: `PerpetualFuturesBacktester.backtest_strategy(...)`.
- Produces: `split_is_oos(df, is_fraction) -> (df_is, df_oos)`; `run_backtest(signal_fn, parameters, df, edge_type, seed) -> dict`.

**Design:** Chronological split (never shuffle — that leaks future into past). Seed numpy before each backtest for reproducibility. Return `asdict(result)` so it can feed validation.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/discovery/evolution/test_fitness_evaluator.py
from slate_core.discovery.evolution.fitness_evaluator import split_is_oos, run_backtest

def test_split_is_chronological_and_disjoint(sol_slice):
    is_df, oos_df = split_is_oos(sol_slice, is_fraction=0.6)
    assert len(is_df) + len(oos_df) == len(sol_slice)
    assert is_df.index[-1] <= oos_df.index[0]   # IS ends before OOS starts
    assert len(oos_df) > 20                       # enough bars to trade

def test_run_backtest_returns_metrics_dict(sol_slice):
    def mom(df, i, p):
        return 1 if df["close"].iloc[i] > df["close"].iloc[i-1] else -1
    res = run_backtest(mom, {}, sol_slice, edge_type="momentum", seed=42)
    assert isinstance(res, dict)
    for k in ("total_profit_usdt", "vs_buy_hold_usdt", "sharpe_ratio",
              "total_trades", "beat_market", "max_drawdown_pct"):
        assert k in res, f"missing metric {k}"
    assert res["total_trades"] >= 0

def test_run_backtest_is_deterministic_under_seed(sol_slice):
    def mom(df, i, p):
        return 1 if df["close"].iloc[i] > df["close"].iloc[i-1] else -1
    a = run_backtest(mom, {}, sol_slice, "momentum", seed=7)
    b = run_backtest(mom, {}, sol_slice, "momentum", seed=7)
    assert a["total_profit_usdt"] == b["total_profit_usdt"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/discovery/evolution/test_fitness_evaluator.py -k "split or run_backtest" -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement**

```python
# append to slate_core/discovery/evolution/fitness_evaluator.py
import dataclasses
from slate_core.discovery.perpetual_futures_backtest import (
    PerpetualFuturesBacktester, PerpetualBacktestConfig,
)


def split_is_oos(df: pd.DataFrame, is_fraction: float = 0.6):
    """Chronological in-sample / out-of-sample split. No shuffling."""
    n = len(df)
    cut = int(n * is_fraction)
    cut = max(cut, 30)               # keep IS tradeable
    cut = min(cut, n - 30)           # keep OOS tradeable
    return df.iloc[:cut].copy(), df.iloc[cut:].copy()


def run_backtest(signal_fn, parameters, df, edge_type: str, seed: int) -> dict:
    """Run one brutal-realism backtest deterministically; return metrics dict."""
    np.random.seed(seed)
    bt = PerpetualFuturesBacktester(PerpetualBacktestConfig())
    result = bt.backtest_strategy(
        df=df,
        strategy_name="eval_candidate",
        strategy_description="fitness evaluation",
        edge_type=edge_type,
        signal_function=signal_fn,
        parameters=parameters or {},
    )
    d = dataclasses.asdict(result)
    d["beat_market"] = bool(d.get("beat_market", False))
    return d
```

> **NOTE for implementer:** If `PerpetualFuturesBacktester.__init__` does not accept a `PerpetualBacktestConfig` positional/keyword, read its `__init__` signature and adapt the two lines above to match. Do not change the backtester.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/discovery/evolution/test_fitness_evaluator.py -k "split or run_backtest" -v`
Expected: 3 PASS. If a test fails because the backtester API differs, fix the call in Step 3 to match the real signature, re-run.

- [ ] **Step 5: Commit**

```bash
git add slate_core/discovery/evolution/fitness_evaluator.py tests/discovery/evolution/test_fitness_evaluator.py
git commit -m "feat(evolution): add chronological IS/OOS split and seeded backtest runner"
```

### Task 0.4: Overfit penalty + final `evaluate_fitness`

**Files:**
- Modify: `slate_core/discovery/evolution/fitness_evaluator.py`
- Test: `tests/discovery/evolution/test_fitness_evaluator.py`

**Interfaces:**
- Consumes: `get_rigorous_validation_system()` from `rigorous_validation.py:784`; `PluralisticValidationSystem.validate_strategy(...)`.
- Produces: `FitnessResult` dataclass; `evaluate_fitness(signal_fn, parameters, df, edge_type, config=None, candidate_id="") -> FitnessResult`.

**Design (the crux):**
1. Correctness gate (Task 0.2). Fail → `fitness_score = -inf`.
2. IS + OOS backtests (Task 0.3).
3. Overfit gap = `is_vs_buyhold − oos_vs_buyhold` clamped at 0 (only penalize when IS looks better than OOS). `overfit_penalty = gap * weight`.
4. Validation score from `PluralisticValidationSystem` run on the OOS result (it already does walk-forward + bootstrap + MC). Floor at `validation_score_floor`.
5. Gates: `oos_trades >= min_trades`, (optional) `oos beats buy-hold`, `validation_score >= floor`. Any fail → `fitness_score = -inf`, with `rejection_reason`.
6. `fitness_score = oos_vs_buyhold − overfit_penalty` (a real USDT-denominated, overfit-adjusted edge). Higher = better.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/discovery/evolution/test_fitness_evaluator.py
from slate_core.discovery.evolution.fitness_evaluator import (
    evaluate_fitness, FitnessResult,
)

def test_evaluate_fitness_returns_result_for_valid_strategy(sol_slice):
    def mom(df, i, p):
        return 1 if df["close"].iloc[i] > df["close"].iloc[i-1] else -1
    res = evaluate_fitness(mom, {}, sol_slice, edge_type="momentum",
                           candidate_id="t1")
    assert isinstance(res, FitnessResult)
    assert res.evaluated is True
    assert res.n_trades_oos >= 0
    assert isinstance(res.overfit_gap, float)
    # fitness is either a finite float or -inf; never NaN
    assert not math.isnan(res.fitness_score)

def test_evaluate_fitness_rejects_bad_signal(sol_slice):
    def bad(df, i, p):
        return 42
    res = evaluate_fitness(bad, {}, sol_slice, edge_type="momentum",
                           candidate_id="t2")
    assert res.fitness_score == float("-inf")
    assert res.evaluated is False
    assert res.rejection_reason

def test_overfit_penalty_reduces_score_when_is_far_exceeds_oos(monkeypatch, sol_slice):
    """If IS edge hugely exceeds OOS edge, penalty must be positive."""
    from slate_core.discovery.evolution import fitness_evaluator as fe
    # Force a large IS/OOS gap by stubbing run_backtest outputs.
    def fake_run(signal_fn, parameters, df, edge_type, seed):
        is_run = "is" if df.index[0] == sol_slice.index[0] else "oos"
        base = {"total_profit_usdt": 0.0, "vs_buy_hold_usdt": 0.0,
                "sharpe_ratio": 0.0, "total_trades": 20, "beat_market": True,
                "max_drawdown_pct": 0.1, "total_transaction_costs_usdt": 0.0,
                "win_rate": 0.5, "profit_factor": 1.0}
        base["vs_buy_hold_usdt"] = 500.0 if is_run == "is" else 10.0
        return base
    monkeypatch.setattr(fe, "run_backtest", fake_run)
    # Stub validation to always pass the floor.
    monkeypatch.setattr(fe, "_validation_score", lambda *a, **k: 0.9)
    def mom(df, i, p): return 0
    res = evaluate_fitness(mom, {}, sol_slice, edge_type="momentum",
                           candidate_id="t3")
    assert res.overfit_gap > 0
    assert res.overfit_penalty > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/discovery/evolution/test_fitness_evaluator.py -k "evaluate_fitness or overfit_penalty" -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement**

```python
# append to slate_core/discovery/evolution/fitness_evaluator.py
from slate_core.discovery.rigorous_validation import get_rigorous_validation_system


@dataclass
class FitnessResult:
    evaluated: bool                # did it pass the gate and produce a score?
    fitness_score: float           # higher = better; -inf if rejected
    oos_vs_buyhold: float
    is_vs_buyhold: float
    overfit_gap: float             # max(0, is - oos)
    overfit_penalty: float
    n_trades_is: int
    n_trades_oos: int
    validation_score: float
    rejection_reason: str = ""
    metrics_oos: Dict[str, Any] = field(default_factory=dict)
    metrics_is: Dict[str, Any] = field(default_factory=dict)
    candidate_id: str = ""


def _validation_score(oos_metrics: dict, oos_df=None,
                      strategy_name: str = "eval_candidate") -> float:
    """Run the existing pluralistic validators on the OOS result; return 0..1.

    Reads PluralisticValidationReport.overall_validation_score (verified at
    rigorous_validation.py:721). Passes price_data so walk-forward works."""
    try:
        system = get_rigorous_validation_system()
        additional = {"price_data": oos_df} if oos_df is not None else None
        report = system.validate_strategy(strategy_name, oos_metrics, additional)
        return float(getattr(report, "overall_validation_score", 0.0) or 0.0)
    except Exception:
        # Validation must never crash evolution; a failure => neutral score.
        return 0.0


def evaluate_fitness(signal_fn, parameters, df, edge_type: str,
                     config: "FitnessConfig | None" = None,
                     candidate_id: str = "") -> FitnessResult:
    cfg = config or FitnessConfig()
    base = FitnessResult(evaluated=False, fitness_score=float("-inf"),
                         oos_vs_buyhold=0.0, is_vs_buyhold=0.0,
                         overfit_gap=0.0, overfit_penalty=0.0,
                         n_trades_is=0, n_trades_oos=0,
                         validation_score=0.0, candidate_id=candidate_id)

    # 1) Correctness gate
    ok, reason = check_signal_correctness(signal_fn, df, parameters or {},
                                          probe_window=cfg.probe_window)
    if not ok:
        base.rejection_reason = f"correctness: {reason}"
        return base

    # 2) Split + backtest both halves (deterministic per seed)
    is_df, oos_df = split_is_oos(df, cfg.is_fraction)
    seed = cfg.random_seed
    is_m = run_backtest(signal_fn, parameters, is_df, edge_type, seed=seed)
    oos_m = run_backtest(signal_fn, parameters, oos_df, edge_type,
                         seed=seed + 1)

    base.metrics_is, base.metrics_oos = is_m, oos_m
    base.is_vs_buyhold = float(is_m.get("vs_buy_hold_usdt", 0.0))
    base.oos_vs_buyhold = float(oos_m.get("vs_buy_hold_usdt", 0.0))
    base.n_trades_is = int(is_m.get("total_trades", 0))
    base.n_trades_oos = int(oos_m.get("total_trades", 0))

    # 3) Overfit gap & penalty (only penalize IS > OOS)
    base.overfit_gap = max(0.0, base.is_vs_buyhold - base.oos_vs_buyhold)
    base.overfit_penalty = base.overfit_gap * cfg.overfit_penalty_weight

    # 4) Validation on OOS (optional — slow; off by default in the inner loop)
    if cfg.run_pluralistic_validation:
        base.validation_score = _validation_score(oos_m, oos_df=oos_df)
    else:
        base.validation_score = 1.0  # neutral; floor gate skipped below

    # 5) Gates
    reasons = []
    if base.n_trades_oos < cfg.min_trades:
        reasons.append(f"oos_trades={base.n_trades_oos}<{cfg.min_trades}")
    if cfg.require_beat_buyhold_oos and base.oos_vs_buyhold <= 0:
        reasons.append("oos_does_not_beat_buyhold")
    if cfg.run_pluralistic_validation and base.validation_score < cfg.validation_score_floor:
        reasons.append(f"validation_score={base.validation_score:.2f}<{cfg.validation_score_floor}")
    if reasons:
        base.rejection_reason = "; ".join(reasons)
        return base

    # 6) Final overfit-adjusted edge (USDT vs buy-hold, OOS)
    base.evaluated = True
    base.fitness_score = base.oos_vs_buyhold - base.overfit_penalty
    return base
```

- [ ] **Step 4: Run the full Phase-0 test suite**

Run: `pytest tests/discovery/evolution/ -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add slate_core/discovery/evolution/fitness_evaluator.py tests/discovery/evolution/test_fitness_evaluator.py
git commit -m "feat(evolution): add overfit-resistant evaluate_fitness (IS/OOS + penalty + gates)"
```

### Task 0.5: Smoke-test on real full data + document

**Files:**
- Create: `slate_core/discovery/evolution/README.md`
- No new tests (manual smoke).

- [ ] **Step 1: Smoke run on the full real CSV**

```bash
python3 -c "
import pandas as pd
from slate_core.discovery.evolution.fitness_evaluator import evaluate_fitness
df = pd.read_json('sol_data_cache/SOLUSDT_perpetual_1d_12m.csv')
df['timestamp']=pd.to_datetime(df['timestamp']); df=df.set_index('timestamp').sort_index()
def mom(df,i,p): return 1 if df['close'].iloc[i]>df['close'].iloc[i-1] else -1
def flat(df,i,p): return 0
for name,fn in [('momentum',mom),('flat',flat)]:
    r=evaluate_fitness(fn,{},df,edge_type='momentum',candidate_id=name)
    print(name,'eval=',r.evaluated,'fit=',r.fitness_score,'oos_vs_bh=',round(r.oos_vs_buyhold,2),'overfit=',round(r.overfit_penalty,2),'trades_oos=',r.n_trades_oos,'reason=',r.rejection_reason)
"
```
Expected: two lines printed, no crash. `momentum` should either pass gates or be rejected with a clear reason; `flat` should be rejected (0 trades / doesn't beat buy-hold). This proves the evaluator runs end-to-end on real data.

- [ ] **Step 2: Write `evolution/README.md`** summarizing Phase 0 behavior, the overfit-penalty rationale, and the `evaluate_fitness` contract (inputs, outputs, gates). Keep it to ~40 lines.

- [ ] **Step 3: Commit**

```bash
git add slate_core/discovery/evolution/README.md
git commit -m "docs(evolution): document Phase 0 fitness evaluator"
```

- [ ] **Step 4: Restart server (MANDATORY)**

```bash
pkill -f "python3 -m slate_core.server" ; sleep 2 ; python3 -m slate_core.server &
```

---

# PHASE 1 — Program database: MAP-Elites + islands (IMPLEMENTING NOW)

**Why:** SLATE's biggest structural gap (confirmed by architecture review): each of the 28,401 discoveries is independent — nothing breeds, nothing maintains diversity, nothing accumulates. The program database is the AlphaEvolve component that fixes this, and it's the cleanest single win. It also costs zero new code-execution risk: it only stores and samples metadata/scores.

**Design:** MAP-Elites grid where each cell (niche) keeps its single best program, plus an "island pool" of recent diverse programs for exploration. Niche = `(strategy_family, regime_bucket)`. `sample()` returns `(parent, inspirations)` — the exact AlphaEvolve controller primitive. Seeded from the existing `perpetual_discoveries` table so accumulated knowledge instantly populates the grid. Persisted to a new sqlite table so it survives restarts.

### Task 1.1: Niche descriptor (test-first)

**Files:**
- Create: `slate_core/discovery/evolution/niche.py`
- Test: `tests/discovery/evolution/test_program_database.py`

**Interfaces:**
- Produces: `compute_niche(strategy_meta: dict) -> tuple[str, str]` returning `(family, regime_bucket)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/discovery/evolution/test_program_database.py
from slate_core.discovery.evolution.niche import compute_niche

def test_niche_from_edge_type_and_regime():
    meta = {"edge_type": "momentum", "volatility_regime": "high"}
    assert compute_niche(meta) == ("momentum", "high")

def test_niche_defaults_unknowns():
    assert compute_niche({}) == ("unknown", "unknown")
    assert compute_niche({"edge_type": "arbitrage"}) == ("arbitrage", "unknown")

def test_niche_normalizes_regime():
    meta = {"edge_type": "mean_reversion", "volatility_regime": "LOW"}
    assert compute_niche(meta) == ("mean_reversion", "low")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/discovery/evolution/test_program_database.py::test_niche_from_edge_type_and_regime -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement**

```python
# slate_core/discovery/evolution/niche.py
"""MAP-Elites niche descriptor: (strategy_family, regime_bucket)."""
from typing import Any, Dict, Tuple


def compute_niche(strategy_meta: Dict[str, Any]) -> Tuple[str, str]:
    family = str(strategy_meta.get("edge_type") or "unknown").strip().lower() or "unknown"
    regime = str(strategy_meta.get("volatility_regime") or "unknown").strip().lower() or "unknown"
    return (family, regime)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/discovery/evolution/test_program_database.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add slate_core/discovery/evolution/niche.py tests/discovery/evolution/test_program_database.py
git commit -m "feat(evolution): add MAP-Elites niche descriptor"
```

### Task 1.2: `Program` dataclass + `ProgramDatabase.add` (MAP-Elites elite replacement)

**Files:**
- Create: `slate_core/discovery/evolution/program_database.py`
- Test: `tests/discovery/evolution/test_program_database.py`

**Interfaces:**
- Produces: `Program` dataclass; `ProgramDatabase(config)` with `.add(program)` and `.elite(niche)`.

**Design:** In-memory `dict[niche -> Program]` for elites + `list[Program]` island pool (cap size; evict lowest-fitness). `add` replaces the niche elite iff the new program's `fitness_score` strictly exceeds the incumbent's.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/discovery/evolution/test_program_database.py
from slate_core.discovery.evolution.program_database import Program, ProgramDatabase, ProgramDBConfig

def _prog(fitness, family="momentum", regime="high", cid="c"):
    return Program(candidate_id=cid, niche=(family, regime),
                   family=family, regime=regime,
                   fitness_score=fitness, source="seed")

def test_add_keeps_best_per_niche():
    db = ProgramDatabase(ProgramDBConfig())
    db.add(_prog(10.0, cid="a")); db.add(_prog(50.0, cid="b")); db.add(_prog(20.0, cid="c"))
    elite = db.elite(("momentum", "high"))
    assert elite.candidate_id == "b"
    assert elite.fitness_score == 50.0

def test_separate_niches_kept_separately():
    db = ProgramDatabase(ProgramDBConfig())
    db.add(_prog(5.0, family="momentum", regime="high", cid="m"))
    db.add(_prog(1.0, family="arbitrage", regime="low", cid="a"))
    assert db.elite(("momentum", "high")).candidate_id == "m"
    assert db.elite(("arbitrage", "low")).candidate_id == "a"

def test_island_pool_capped_and_evicts_worst():
    cfg = ProgramDBConfig(island_pool_size=3)
    db = ProgramDatabase(cfg)
    for i in range(5):
        db.add(_prog(float(i), cid=f"p{i}"))
    pool = db.island_pool()
    assert len(pool) == 3
    assert min(p.fitness_score for p in pool) >= 2.0  # two lowest (0,1) evicted
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/discovery/evolution/test_program_database.py -k "add_keeps or separate_niches or island_pool" -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement**

```python
# slate_core/discovery/evolution/program_database.py
"""Program database: MAP-Elites elites + island exploration pool (Phase 1)."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple
import itertools
_niche = Tuple[str, str]


@dataclass
class ProgramDBConfig:
    island_pool_size: int = 50          # exploration pool cap
    inspiration_count: int = 3          # inspirations returned by sample()
    novelty_correlation_max: float = 0.7  # used in Phase 3; reserved here
    persist_path: Optional[str] = "slate_core/slate_evolution.db"


@dataclass
class Program:
    candidate_id: str
    niche: _niche
    family: str
    regime: str
    fitness_score: float               # -inf = rejected
    source: str = "evolved"            # "seed" | "evolved"
    parameters: Dict[str, Any] = field(default_factory=dict)
    code: Optional[str] = None         # present for Phase 4 evolved programs
    metrics: Dict[str, Any] = field(default_factory=dict)
    parent_id: Optional[str] = None
    generation: int = 0
    timestamp: str = ""


class ProgramDatabase:
    def __init__(self, config: Optional[ProgramDBConfig] = None):
        self.config = config or ProgramDBConfig()
        self._elites: Dict[_niche, Program] = {}
        self._pool: List[Program] = []

    def add(self, program: Program) -> None:
        # MAP-Elites: keep the best per niche
        cur = self._elites.get(program.niche)
        if cur is None or program.fitness_score > cur.fitness_score:
            self._elites[program.niche] = program
        # Island pool: bounded, evict lowest fitness
        self._pool.append(program)
        if len(self._pool) > self.config.island_pool_size:
            self._pool.sort(key=lambda p: p.fitness_score, reverse=True)
            self._pool = self._pool[: self.config.island_pool_size]

    def elite(self, niche: _niche) -> Optional[Program]:
        return self._elites.get(niche)

    def island_pool(self) -> List[Program]:
        return list(self._pool)

    def best(self) -> Optional[Program]:
        if not self._elites:
            return None
        return max(self._elites.values(), key=lambda p: p.fitness_score)

    def occupied_niches(self) -> List[_niche]:
        return list(self._elites.keys())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/discovery/evolution/test_program_database.py -v`
Expected: all PASS so far.

- [ ] **Step 5: Commit**

```bash
git add slate_core/discovery/evolution/program_database.py tests/discovery/evolution/test_program_database.py
git commit -m "feat(evolution): add Program + ProgramDatabase MAP-Elites elite storage"
```

### Task 1.3: `sample()` — the AlphaEvolve controller primitive

**Files:**
- Modify: `slate_core/discovery/evolution/program_database.py`
- Test: `tests/discovery/evolution/test_program_database.py`

**Interfaces:**
- Produces: `ProgramDatabase.sample(rng=None) -> (Program, List[Program])` returning `(parent, inspirations)`.

**Design:** 70% of the time pick the global `best()` as parent (exploitation); 30% pick a uniformly random occupied niche's elite (exploration). Inspirations = up to `inspiration_count` programs from *other* niches than the parent (diversity). Deterministic when `rng` (a `random.Random`) is seeded.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/discovery/evolution/test_program_database.py
import random

def test_sample_returns_parent_and_inspirations():
    db = ProgramDatabase(ProgramDBConfig(inspiration_count=2))
    db.add(_prog(10.0, family="momentum", regime="high", cid="m"))
    db.add(_prog(8.0, family="arbitrage", regime="low", cid="a"))
    db.add(_prog(6.0, family="mean_reversion", regime="mid", cid="r"))
    rng = random.Random(0)
    parent, inspirations = db.sample(rng=rng)
    assert isinstance(parent, Program)
    assert len(insspirations) <= 2
    for insp in inspirations:
        assert insp.niche != parent.niche

def test_sample_is_deterministic_under_seed():
    db = ProgramDatabase(ProgramDBConfig(inspiration_count=2))
    for i,fam in enumerate(["momentum","arbitrage","mean_reversion","breakout"]):
        db.add(_prog(float(10-i), family=fam, regime="high", cid=fam))
    p1,i1 = db.sample(rng=random.Random(42))
    p2,i2 = db.sample(rng=random.Random(42))
    assert p1.candidate_id == p2.candidate_id
    assert [x.candidate_id for x in i1] == [x.candidate_id for x in i2]

def test_sample_empty_db_returns_none():
    db = ProgramDatabase(ProgramDBConfig())
    assert db.sample() == (None, [])
```

> **NOTE:** there is a deliberate typo above (`insspirations`) — write the test correctly when you implement it.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/discovery/evolution/test_program_database.py -k "sample" -v`
Expected: FAIL (AttributeError: `sample`).

- [ ] **Step 3: Implement**

```python
# append to slate_core/discovery/evolution/program_database.py
import random as _random


class ProgramDatabase:
    # ... existing methods ...

    def sample(self, rng: Optional[_random.Random] = None):
        """AlphaEvolve controller primitive: (parent, inspirations)."""
        r = rng or _random.Random()
        if not self._elites:
            return None, []
        niches = list(self._elites.keys())
        # 70% exploit global best, 30% explore a random niche elite
        if r.random() < 0.7:
            parent = self.best()
        else:
            parent = self._elites[r.choice(niches)]
        # inspirations from OTHER niches (diversity)
        others = [self._elites[n] for n in niches if n != parent.niche]
        r.shuffle(others)
        inspirations = others[: self.config.inspiration_count]
        return parent, inspirations
```

> **NOTE for implementer:** add `sample` as a method on the *existing* `ProgramDatabase` class (do not redefine the class). Also fix the typo'd test variable to `inspirations`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/discovery/evolution/test_program_database.py -k "sample" -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add slate_core/discovery/evolution/program_database.py tests/discovery/evolution/test_program_database.py
git commit -m "feat(evolution): add sample() parent+inspirations primitive"
```

### Task 1.4: Seed from existing discoveries

**Files:**
- Modify: `slate_core/discovery/evolution/program_database.py`
- Test: `tests/discovery/evolution/test_program_database.py`

**Interfaces:**
- Consumes: `perpetual_discoveries` table via sqlite3 (columns: `strategy_name, edge_type, volatility_regime, total_profit_usdt, vs_buy_hold_usdt, sharpe_ratio, beat_market, passed_validation, total_trades`).
- Produces: `seed_from_discoveries(db_path, limit=None) -> int` returning count seeded.

**Design:** Read existing rows, build `Program`s with `source="seed"`, `fitness_score = vs_buy_hold_usdt` (the same OOS-edge currency the evaluator uses) for validated rows, `code=None` (legacy rows have no stored signal code — they seed niches/fitness only; they are inspirations, not re-executable parents). Skip rows with non-finite/`-inf` fitness.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/discovery/evolution/test_program_database.py
import sqlite3, tempfile, os

def _make_legacy_db(path):
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute("""CREATE TABLE perpetual_discoveries (
        id INTEGER PRIMARY KEY, strategy_name TEXT, edge_type TEXT,
        volatility_regime TEXT, total_profit_usdt REAL, vs_buy_hold_usdt REAL,
        sharpe_ratio REAL, beat_market INTEGER, passed_validation INTEGER,
        total_trades INTEGER, strategy_description TEXT)""")
    rows = [
        ("s1","momentum","high", 100.0, 50.0, 1.2, 1, 1, 30),
        ("s2","arbitrage","low", 80.0, 40.0, 1.1, 1, 1, 25),
        ("s3","mean_reversion","high", -20.0, -30.0, 0.3, 0, 0, 10),
    ]
    c.executemany("INSERT INTO perpetual_discoveries (strategy_name,edge_type,volatility_regime,"
                  "total_profit_usdt,vs_buy_hold_usdt,sharpe_ratio,beat_market,passed_validation,"
                  "total_trades,strategy_description) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  [r + ("seed",) for r in rows])
    conn.commit(); conn.close()

def test_seed_from_discoveries_populates_niches():
    path = tempfile.mktemp(suffix=".db")
    _make_legacy_db(path)
    try:
        db = ProgramDatabase(ProgramDBConfig())
        n = db.seed_from_discoveries(path)
        assert n == 2  # only the 2 profitable/validated rows (s3 skipped: vs_buy_hold<0)
        assert db.elite(("momentum","high")) is not None
        assert db.elite(("arbitrage","low")) is not None
        assert db.elite(("mean_reversion","high")) is None  # skipped
    finally:
        os.remove(path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/discovery/evolution/test_program_database.py -k "seed_from_discoveries" -v`
Expected: FAIL (AttributeError).

- [ ] **Step 3: Implement**

```python
# append as a method on ProgramDatabase (add `import sqlite3` at top of file)
    def seed_from_discoveries(self, db_path: str, limit: Optional[int] = None) -> int:
        """Seed the population from existing perpetual_discoveries rows.

        Legacy rows carry metrics but no signal code, so seeded Programs are
        usable as fitness/niche references and inspirations, not as
        re-executable parents (code=None)."""
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT strategy_name, edge_type, volatility_regime, total_profit_usdt, "
            "vs_buy_hold_usdt, sharpe_ratio, beat_market, passed_validation, total_trades "
            "FROM perpetual_discoveries WHERE passed_validation=1 ORDER BY vs_buy_hold_usdt DESC"
        ).fetchall()
        conn.close()
        if limit:
            rows = rows[:limit]
        count = 0
        for row in rows:
            vs_bh = float(row["vs_buy_hold_usdt"]) if row["vs_buy_hold_usdt"] is not None else 0.0
            if vs_bh <= 0:
                continue  # skip non-edges; they add no niche value
            niche = (str(row["edge_type"] or "unknown").lower(),
                     str(row["volatility_regime"] or "unknown").lower())
            self.add(Program(
                candidate_id=f"seed:{row['strategy_name']}",
                niche=niche,
                family=niche[0], regime=niche[1],
                fitness_score=vs_bh,
                source="seed",
                metrics={
                    "total_profit_usdt": float(row["total_profit_usdt"] or 0),
                    "sharpe_ratio": float(row["sharpe_ratio"] or 0),
                    "total_trades": int(row["total_trades"] or 0),
                    "beat_market": bool(row["beat_market"]),
                },
            ))
            count += 1
        return count
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/discovery/evolution/test_program_database.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add slate_core/discovery/evolution/program_database.py tests/discovery/evolution/test_program_database.py
git commit -m "feat(evolution): seed program database from existing discoveries"
```

### Task 1.5: Sqlite persistence (survive restarts)

**Files:**
- Modify: `slate_core/discovery/evolution/program_database.py`
- Test: `tests/discovery/evolution/test_program_database.py`

**Interfaces:**
- Produces: `ProgramDatabase.save() -> None`, `ProgramDatabase.load() -> int`, backed by table `evolution_population`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/discovery/evolution/test_program_database.py
def test_persistence_roundtrip():
    path = tempfile.mktemp(suffix=".db")
    try:
        db = ProgramDatabase(ProgramDBConfig(persist_path=path))
        db.add(_prog(42.0, family="momentum", regime="high", cid="x"))
        db.save()
        db2 = ProgramDatabase(ProgramDBConfig(persist_path=path))
        n = db2.load()
        assert n == 1
        assert db2.elite(("momentum","high")).candidate_id == "x"
    finally:
        if os.path.exists(path): os.remove(path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/discovery/evolution/test_program_database.py -k "persistence" -v`
Expected: FAIL.

- [ ] **Step 3: Implement** `save()` (write all elites+pool to `evolution_population(candidate_id PK, niche_family, niche_regime, fitness_score, source, parameters_json, code, metrics_json, parent_id, generation, timestamp)`) and `load()` (read back into `Program`s, re-`add`). Use `json` for the dict columns. Keep it simple and idempotent (`INSERT OR REPLACE`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/discovery/evolution/test_program_database.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add slate_core/discovery/evolution/program_database.py tests/discovery/evolution/test_program_database.py
git commit -m "feat(evolution): persist program database to sqlite"
```

### Task 1.6: End-to-end smoke — seed real DB, sample, evaluate one child

- [ ] **Step 1: Smoke run**

```bash
python3 -c "
import pandas as pd, random
from slate_core.discovery.evolution.program_database import ProgramDatabase, ProgramDBConfig
from slate_core.discovery.evolution.fitness_evaluator import evaluate_fitness
db = ProgramDatabase(ProgramDBConfig(persist_path='slate_core/slate_evolution.db'))
n = db.seed_from_discoveries('slate_core/slate_realistic_discoveries.db', limit=500)
print('seeded', n, 'niches', len(db.occupied_niches()), 'best=', round(db.best().fitness_score,2))
parent, insp = db.sample(rng=random.Random(1))
print('parent', parent.candidate_id, parent.niche, 'inspirations', [i.niche for i in insp])
"
```
Expected: prints seeded count > 0, niche count > 0, a best fitness, a parent id, and 0–3 inspiration niches. No crash. This proves the full Phase-1 loop on real accumulated data.

- [ ] **Step 2: Update `evolution/README.md`** with a Phase-1 section (how seeding works, the `sample()` contract, persistence file location).

- [ ] **Step 3: Commit + restart server**

```bash
git add slate_core/discovery/evolution/README.md
git commit -m "docs(evolution): document Phase 1 program database"
pkill -f "python3 -m slate_core.server" ; sleep 2 ; python3 -m slate_core.server &
```

---

# PHASE 2 — Rich-context prompt sampling + meta-prompt evolution (DESIGN — activate after 0+1 ship)

**Goal:** Replace SLATE's bias-vector feedback with AlphaEvolve-style prompts that show the LLM concrete prior winners *with their code and scores*, plus co-evolved meta-instructions. Ablation in the paper shows context + meta-prompts each give significant gains.

**Files:**
- Create: `evolution/prompt_sampler.py` — `PromptSampler.build(parent: Program, inspirations: List[Program], objective: dict) -> str`. Assembles: (a) system instruction, (b) parent program with its fitness + niche + metrics, (c) 2–3 inspirations with their niches/scores, (d) the OOS-fitness objective + overfit warning, (e) stochastic formatting slot.
- Create: `evolution/meta_prompt_db.py` — a second small `ProgramDatabase`-style store for prompt-instruction snippets, co-evolved alongside strategies (`meta_prompt_evolution`). Mutated by the LLM in a separate prompt-generation step.
- Wire into: `discovery/nl_strategy_generator.py` (`NLStrategyGenerator`) — consume `PromptSampler` output instead of plain bias dicts.

**Key logic to lock:**
- Prompt template = Figure 3b of the paper adapted to trading: prior-programs block (with `fitness_score`, `oos_vs_buyhold`, `overfit_penalty`, `niche`), current-program block, SEARCH/REPLACE rules block, task block ("propose a daily-timeframe signal variant that improves OOS edge without increasing the overfit gap").
- Meta-prompt store uses the same MAP-Elites niche idea but niches = prompt-strategy archetypes.

**Validation gate:** every emitted proposal still passes Phase 0 `evaluate_fitness` before entering the Phase 1 DB. The prompt layer only changes *what is proposed*, not *what survives*.

**Risks:** prompt length / cost; LLM producing code that breaks the Phase-0 correctness gate (acceptable — gate rejects it). No new overfit risk beyond Phase 0's.

**TDD steps:** to be elaborated when activated. First tests: `PromptSampler.build` includes parent id + fitness + ≥1 inspiration; meta-prompt store add/sample round-trip.

---

# PHASE 3 — Multi-objective MAP-Elites + diversity (DESIGN — activate after 2)

**Goal:** Promote the existing `StrategyGenome.dominates()` (`genetic_optimizer.py:66`) and `/results/pareto-frontier` endpoint (`enhanced_api.py:94`) from side-features into the *selection* mechanism. Add a real return-correlation novelty bonus so the population covers distinct edges, not variants of one.

**Files:**
- Modify: `evolution/program_database.py` — extend niche to carry a small Pareto archive per cell (not just one elite); add `correlation_to(existing, candidate_equity) -> float` using equity-curve correlation on the OOS slice.
- Modify: `evolution/niche.py` — niche becomes `(family, regime, behavior_signature)` where `behavior_signature` buckets by trade frequency / direction bias (cheap proxy before full correlation).
- New: `evolution/pareto.py` — `pareto_front(programs) -> List[Program]` across objectives `(oos_vs_buyhold, sharpe_oos, -max_drawdown, stability)`.

**Key logic:** survival = Pareto-frontier membership per niche; novelty bonus = `1 − max correlation to any incumbent in pool` (reuse SLATE's existing 0.7 correlation threshold as the cutoff above which a candidate is penalized). The paper shows multi-objective diversity improves even the single target metric — this is where that dividend is captured.

**Validation gate:** unchanged (Phase 0). Pareto is selection, not fitness.

**Risks:** correlation requires re-running equity curves → cost; mitigate with the behavior-signature proxy first, real correlation only for finalists.

**TDD steps:** to be elaborated when activated.

---

# PHASE 4 — Sandboxed signal-code evolution (DESIGN — highest leverage, highest risk — activate after 3)

**Goal:** Evolve the *signal logic itself* as executable code — the core AlphaEvolve mechanism — but inside a hard cage so the safety envelope is never touched and overfitting stays bounded by Phase 0.

**Files:**
- Create: `evolution/signal_sandbox.py`:
  - `compile_signal(code: str) -> SignalFn` — parse with `ast`, **whitelist** only safe nodes (arithmetic, comparison, indexing into a frozen allowlist of df columns, `if/else`, calls to an allowlist of numpy/indicator helpers). **Reject** any `Import`, `Attribute` access outside the allowlist, `call` to forbidden builtins, assignment to non-local.
  - `safe_eval_signal(fn, df, i, params) -> int` — run with `resource.setrlimit(RLIMIT_CPU/RLIMIT_AS)` + `signal.alarm` timeout; clamp output to `{-1,0,1}`.
- Create: `evolution/evolvable_strategy.py` — one annotated template file with `# EVOLVE-BLOCK-START/END` around a single `def signal_fn(df, i, params) -> int`. The skeleton (risk caps, sizing, execution) is **never** in an EVOLVE-BLOCK.
- Integrate: the evolved `signal_fn` is passed straight to `evaluate_fitness` → `PerpetualFuturesBacktester.backtest_strategy(..., signal_function=signal_fn, ...)` (`perpetual_futures_backtest.py:304`). No backtester changes.

**Key logic (mirrors paper):**
- LLM emits SEARCH/REPLACE diffs against the current `signal_fn` body → `apply_diff` → `compile_signal` (AST-gated) → Phase-0 `evaluate_fitness` (correctness gate + IS/OOS + overfit penalty + validation floor) → Phase-1/3 DB.
- "Correctness by construction" = the sandbox can only emit bounded signals; the backtester still enforces 3% position / 3x leverage / drawdown limit. Exactly analogous to the paper's scheduling heuristic that only *ranked* Borg-pre-filtered machines.
- Daily timeframe only; explicitly forbid sub-daily features in the AST allowlist.

**Validation gate:** Phase 0 is mandatory and unchanged; add a hard rule: a Phase-4 program must clear the gate on **two** non-overlapping OOS windows (not one) to enter the DB — extra overfit insurance for the most expressive search.

**Risks (must re-read before activating):** this is the maximum-overfitting mode. Do NOT activate until Phase 0's two-window gate is proven to reject curve-fits on a known-overfit control strategy. Add an LLM overfit-suspicion judge (Phase 2 stretch) as a second soft filter.

**TDD steps:** to be elaborated when activated. First tests: sandbox rejects `import os`, rejects network/attribute access, rejects infinite loop (timeout), clamps out-of-range output, compiles+runs a benign momentum stub.

---

# PHASE 5 — Async distributed controller + LLM ensemble (DESIGN — activate after 4)

**Goal:** Throughput. Wrap the loop in AlphaEvolve's async pipeline (controller + LLM samplers + eval nodes) on top of the existing `parallel_strategy_tester.py` `ProcessPoolExecutor`. Use an LLM ensemble: a fast model (high volume of candidates) + a strong model (occasional breakthroughs), per the paper's Gemini Flash + Pro mix.

**Files:**
- Create: `evolution/controller.py` — `async def evolution_step(db, sampler, evaluator, llm_pool)` implementing `parent,insp = db.sample(); prompt = sampler.build(...); code = await llm_pool.generate(prompt); child = apply_diff(...); result = await evaluator.submit(child); db.add(child, result)`. Asyncio, throughput-optimized.
- Modify: reuse `parallel_strategy_tester.py` for the eval pool (backtests are the expensive, embarrassingly-parallel part).
- Create: `evolution/llm_pool.py` — thin ensemble wrapper (fast + strong model); model-agnostic, pluggable provider.

**Key logic:** optimize for evaluated-ideas-per-budget, not single-eval latency (paper §2.6). Cap concurrency at `min(16, cpu-2)` to match existing pool sizing.

**Validation gate:** unchanged (Phase 0). Concurrency is execution, not selection.

**Risks:** cost of LLM calls at scale; mitigate with the Phase-0 evaluation cascade (cheap correctness+IS gate before expensive OOS+validation). API key/provider plumbing is project-specific.

**TDD steps:** to be elaborated when activated.

---

# Appendix A — Reused SLATE interfaces (verified 2026-07-11)

- `PerpetualFuturesBacktester.backtest_strategy(df, strategy_name, strategy_description, edge_type, signal_function, parameters) -> PerpetualBacktestResult` — `perpetual_futures_backtest.py:298`. Signal called at `:381`.
- `PerpetualBacktestConfig` — `perpetual_futures_backtest.py:29` (fees 0.02/0.05%, 15bps slip, 80% fill, 3% size, 3x lev, 20% DD limit, daily).
- `PerpetualBacktestResult` — `perpetual_futures_backtest.py:84` (~47 fields; `vs_buy_hold_usdt`, `beat_market`, `sharpe_ratio`, `total_trades`, `max_drawdown_pct`, etc.).
- `rigorous_validation.py`: `BootstrapValidation` (`:99`), `WalkForwardValidation` (`:197`, OOS), `MonteCarloValidation` (`:304`), `RegimeStressValidation` (`:375`), `ParameterSensitivityValidation` (`:467`), `CostSensitivityValidation` (`:558`), `PluralisticValidationSystem.validate_strategy` (`:659`), `get_rigorous_validation_system()` (`:784`).
- `PerpetualDatabaseManager` — `perpetual_database.py:18` (`save_discovery`, `get_top_strategies`, `get_statistics`); `perpetual_discoveries` schema at `:31`.
- Real data: `sol_data_cache/SOLUSDT_perpetual_1d_12m.csv` (daily SOL perpetual).

# Appendix B — Self-review checklist (run before declaring Phases 0–1 done)

- [ ] All Phase 0 + Phase 1 tasks committed individually with conventional-commit messages.
- [ ] `pytest tests/discovery/evolution/ -v` fully green.
- [ ] Smoke commands (Task 0.5 Step 1, Task 1.6 Step 1) run clean on real data.
- [ ] No synthetic OHLCV anywhere (only real CSV slices + dummy signal stubs).
- [ ] Server restarted after final change.
- [ ] `evolution/README.md` covers Phase 0 + Phase 1.
- [ ] Type/signature consistency: `FitnessResult.fitness_score`, `Program.niche`, `compute_niche` return type, `sample()` return shape match across all tasks.
