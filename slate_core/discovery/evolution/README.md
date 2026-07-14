# Evolution Layer (AlphaEvolve-style)

Implements the high-value, low-risk advances from the AlphaEvolve paper
(Google DeepMind, 2025) as additive layers over SLATE's existing discovery
pipeline. Full multi-phase plan:
`docs/superpowers/plans/2026-07-11-alphaevolve-evolution.md`.

## Why this exists

SLATE's discoveries were *independent* — 28k+ rows that never bred, with no
diversity maintenance and no accumulating memory. AlphaEvolve's two biggest
ideas fix that: (1) an **overfit-resistant fitness evaluator** and (2) an
**accumulating program database** (MAP-Elites + islands). The catch — and the
reason the design is careful — is that AlphaEvolve's results rest on
*ground-truth* evaluators, while SLATE's backtest is an *inductive* proxy.
Overfitting is therefore the make-or-break risk, and Phase 0 exists to make
the fitness function resistant to it before any evolution runs.

## Phase 0 — fitness evaluator (`fitness_evaluator.py`)

### Contract

```python
evaluate_fitness(signal_fn, parameters, df, edge_type,
                 config=None, candidate_id="") -> FitnessResult
```

`signal_fn(df, i, parameters) -> int` must return `1` (long), `-1` (short), or
`0` (flat) — the same interface the backtester already calls
(`perpetual_futures_backtest.py:381`).

### Pipeline

1. **Correctness gate** — probe the signal over a short window; reject
   candidates that raise, return non-finite values, or emit anything outside
   `{-1, 0, 1}`. The safety envelope (sizing/leverage/execution) can never be
   touched by evolved signal code.
2. **Chronological IS/OOS split** (60/40, never shuffled) + deterministic
   backtests on both halves (seeded for reproducibility).
3. **Overfit penalty** = `max(0, is_vs_buyhold - oos_vs_buyhold) * weight`.
   Only penalized when in-sample looks better than out-of-sample.
4. **Optional pluralistic validation** (off by default — it runs
   bootstrap 1000 + Monte Carlo 1000 sims and is too slow for the inner loop;
   turn `run_pluralistic_validation=True` for finalists). Reads
   `PluralisticValidationReport.overall_validation_score`.
5. **Gates** — `oos_trades >= min_trades`; (default) OOS must beat buy-hold;
   (optional) validation score ≥ floor. Any failure → `fitness_score = -inf`.
6. **Score** = `oos_vs_buyhold - overfit_penalty` (USDT-vs-buy-hold units,
   overfit-adjusted). Higher is better.

### Smoke results (full real data, 2026-07-11)

| signal | eval | fitness | oos_vs_bh | overfit_pen | trades is/oos |
|---|---|---|---|---|---|
| momentum | True | 1342.82 | 5458.34 | 4115.51 | 813 / 535 |
| flat | False | -inf | — | — | 0 / 0 (rejected) |

The penalty cutting momentum's raw +5458 OOS edge down to +1343 is the
overfit defense doing its job (IS was far higher than OOS).

### Known limitation — `vs_buy_hold` in downtrends

`vs_buy_hold = strategy_profit - buyhold_profit`. In a down-trending OOS
window, buy-hold loses money, so even "do nothing" (flat) records a positive
`vs_buy_hold`. The `min_trades` gate rejects the pure-flat case, but a
money-losing strategy that merely loses *less* than buy-hold can still pass.

**Recommended first refinement** (not yet implemented): add a
`require_absolute_oos_profit` gate (default True) so a candidate must actually
*make* money OOS (`total_profit_usdt > 0`), not just beat a losing benchmark.
This is small, well-tested, and squarely within Phase 0's intent; deferred only
to respect the "Phase 0 + 1 as planned" scope.

## Phase 1 — program database (`program_database.py`, `niche.py`)

MAP-Elites grid (niche = strategy-family × regime) keeping the best program per
cell, plus a bounded island pool for exploration. Seeded from the existing
`perpetual_discoveries` table so accumulated knowledge instantly populates the
grid. Exposes the AlphaEvolve controller primitive
`sample() -> (parent, inspirations)`. Persisted to sqlite (`slate_core/slate_evolution.db`).

### API

```python
db = ProgramDatabase(ProgramDBConfig(persist_path="slate_core/slate_evolution.db"))
db.seed_from_discoveries("slate_core/slate_realistic_discoveries.db",
                         limit=2000, require_validated=False)
parent, inspirations = db.sample(rng=random.Random(0))   # AlphaEvolve primitive
db.add(evolved_program); db.save()
```

`seed_from_discoveries`: a row is kept if it shows an edge — `vs_buy_hold_usdt
> 0`, else `total_profit_usdt > 0`. `require_validated` defaults **False**
because historically SLATE's `passed_validation` column is unreliable (the
118k-row backup is entirely `passed_validation=0`).

### Smoke results (real data, 2026-07-11)

- Production DB (`slate_realistic_discoveries.db`): 3 rows, 1 seeded.
- Backup (`..._backup_20260705_161518.db`, 118k rows): 2000 seeded, but all land
  in a single niche `('enhanced_ema', 'unknown')`.

### Known characteristics (not bugs)

- **Legacy data is a monoculture.** The historical discoveries are almost all
  `edge_type='enhanced_ema'` with `volatility_regime='unknown'`, so they occupy
  one MAP-Elites cell and `sample()` returns no inspirations. Grid diversity
  emerges once new evolved programs (Phase 2+) with distinct families/regimes
  enter, and when niche dimensions expand (Phase 3).
- **Seed fitness is approximate.** The backup's `vs_buy_hold_usdt` is inflated
  (a $16-profit row claims +$5156 vs buy-hold). Seeds are therefore starting
  material / inspirations, clearly marked `source="seed"`, **not trusted
  elites**. Phase 0's `evaluate_fitness` governs what actually survives going
  forward.

## Status

All phases complete. 66 tests green; verified end-to-end on real data with both
the mock LLM and the live GLM (Z.ai proxy).

- Phase 0: ✅ fitness evaluator (IS/OOS + overfit penalty + absolute-profit gate).
- Phase 1: ✅ program database (MAP-Elites + islands, seeding, persistence).
- Phase 2: ✅ rich-context prompt sampler + meta-prompt evolution.
- Phase 3: ✅ Pareto front + return-correlation novelty.
- Phase 4: ✅ AST-gated signal sandbox + evolvable template + two-window gate.
- Phase 5: ✅ LLM ensemble pool + async controller.

## LLM integration (no Anthropic key needed)

The user runs GLM via Claude Code, which routes through Z.ai's
Anthropic-protocol-compatible proxy (`ANTHROPIC_BASE_URL=https://api.z.ai`,
`ANTHROPIC_AUTH_TOKEN=<key>`). `llm_client.py` reuses that exact proxy + token
(verified: `claude-sonnet-5` via Z.ai returns OK), so SLATE needs **no separate
key**. A deterministic Mock backend keeps all 66 tests offline. Optional
OpenAI-compatible backend for other providers.

## Running the loop

```python
import asyncio, pandas as pd
from slate_core.discovery.evolution.controller import run_evolution, EvolutionConfig
from slate_core.discovery.evolution.program_database import ProgramDatabase, ProgramDBConfig
from slate_core.discovery.evolution.prompt_sampler import PromptSampler
from slate_core.discovery.evolution.llm_pool import LLMPool
from slate_core.discovery.evolution.llm_client import get_llm_client, LLMConfig

df = pd.read_json("sol_data_cache/SOLUSDT_perpetual_1h_6m.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"]); df = df.set_index("timestamp").sort_index()

db = ProgramDatabase(ProgramDBConfig(persist_path="slate_core/slate_evolution.db"))
db.seed_from_discoveries("slate_core/slate_realistic_discoveries.db", limit=200)

pool = LLMPool(get_llm_client(LLMConfig()), get_llm_client(LLMConfig()))  # GLM via Z.ai
produced = asyncio.run(run_evolution(db, PromptSampler(), pool, df, n_steps=20))
```

### End-to-end verification (2026-07-11)

- **Mock loop**: 5/5 steps produced Programs; the two-window gate rejected the
  mock's non-edge signal (overfit defense working).
- **Live GLM (Z.ai)**: 3/3 steps produced valid, sandbox-compiled signal
  functions that ran through the backtester; all rejected by the profitability
  gate on this data window — safety system functioning as designed.

Most candidates will be rejected by the gates early on — that is the point. The
loop accumulates the rare programs that are genuinely profitable OOS on two
independent windows.
