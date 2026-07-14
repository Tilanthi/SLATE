"""Tests for the Phase 5 async evolution controller (evolution/controller.py)."""
import asyncio
import random

from slate_core.discovery.evolution.controller import evolution_step, EvolutionConfig
from slate_core.discovery.evolution.program_database import Program, ProgramDatabase, ProgramDBConfig
from slate_core.discovery.evolution.prompt_sampler import PromptSampler
from slate_core.discovery.evolution.llm_pool import LLMPool, LLMPoolConfig
from slate_core.discovery.evolution.llm_client import MockLLMClient, LLMConfig
from slate_core.discovery.evolution.evolvable_strategy import BASE_SIGNAL_CODE
from slate_core.discovery.evolution.fitness_evaluator import FitnessResult


def _passing_fitness(*_a, **_kw):
    """A gate-passing FitnessResult for plumbing tests (decouples the wiring from
    the stochastic real gate, which is unit-tested in test_evolution_fitness.py)."""
    return FitnessResult(
        evaluated=True, fitness_score=12.0,
        oos_vs_buyhold=12.0, is_vs_buyhold=20.0,
        overfit_gap=8.0, overfit_penalty=4.0,
        n_trades_is=30, n_trades_oos=15,
        validation_score=1.0, candidate_id="test",
    )


def _rejecting_fitness(*_a, **_kw):
    """A gate-REJECTED FitnessResult (loses money OOS) for funnel-logging tests."""
    return FitnessResult(
        evaluated=False, fitness_score=float("-inf"),
        oos_vs_buyhold=0.0, is_vs_buyhold=0.0, overfit_gap=0.0,
        overfit_penalty=0.0, n_trades_is=0, n_trades_oos=0,
        validation_score=0.0, candidate_id="test",
        rejection_reason="oos_total_profit=-5.00<=0 (not profitable)",
    )


def _seed_db():
    db = ProgramDatabase(ProgramDBConfig())
    db.add(Program(candidate_id="seed1", niche=("momentum", "high"), family="momentum",
                   regime="high", fitness_score=10.0, source="seed", code=BASE_SIGNAL_CODE))
    return db


def _mock_pool(canned=None):
    # When canned is given, BOTH clients return it (so tier selection doesn't matter).
    s = MockLLMClient(LLMConfig(), canned=canned) if canned else MockLLMClient(LLMConfig())
    f = MockLLMClient(LLMConfig(), canned=canned) if canned else MockLLMClient(LLMConfig())
    return LLMPool(s, f, LLMPoolConfig(), rng=random.Random(0))


def test_evolution_step_runs_and_adds_program(sol_slice, monkeypatch):
    db = _seed_db()
    sampler = PromptSampler()
    pool = _mock_pool()
    # Mock the subprocess-isolated fitness so this plumbing test exercises
    # sample -> compile -> store deterministically (no subprocess spawn).
    monkeypatch.setattr(
        "slate_core.discovery.evolution.controller.eval_fitness_subprocess",
        _passing_fitness,
    )
    prog = asyncio.run(evolution_step(db, sampler, pool, sol_slice))
    assert prog is not None
    assert prog.source == "evolved"
    assert prog.code is not None and "def signal_fn" in prog.code
    assert prog.parent_id == "seed1"
    assert any(p.candidate_id == prog.candidate_id for p in db.island_pool())


def test_evolution_step_returns_none_when_code_rejected(sol_slice):
    db = _seed_db()
    sampler = PromptSampler()
    # Mock returns code with an import -> sandbox rejects -> step returns None.
    bad = "def signal_fn(df, i, params):\n    import os\n    return 0\n"
    pool = _mock_pool(canned=bad)
    prog = asyncio.run(evolution_step(db, sampler, pool, sol_slice))
    assert prog is None


def test_evolution_step_works_with_empty_database(sol_slice, monkeypatch):
    db = ProgramDatabase(ProgramDBConfig())   # no seed
    sampler = PromptSampler()
    pool = _mock_pool()
    monkeypatch.setattr(
        "slate_core.discovery.evolution.controller.eval_fitness_subprocess",
        _passing_fitness,
    )
    # (b1) empty DB -> parent is a rotated SEED archetype, not always BASE_SIGNAL_CODE
    prog = asyncio.run(evolution_step(db, sampler, pool, sol_slice,
                                      config=EvolutionConfig(edge_type_default="momentum"),
                                      rng=random.Random(0)))
    assert prog is not None
    assert prog.parent_id.startswith("seed:archetype:")


# ---------------------------------------------------------------------------
# (b1) seed-archetype diversity when the population is empty
# ---------------------------------------------------------------------------

def test_seed_archetypes_compile_and_span_families(sol_slice):
    """The archetypes must (a) compile under the sandbox and (b) span >=2
    behavioural families, so an empty population explores varied signals
    instead of cloning one overfit attractor."""
    from slate_core.discovery.evolution.evolvable_strategy import SEED_ARCHETYPES
    from slate_core.discovery.evolution.signal_sandbox import compile_signal
    from slate_core.discovery.evolution.fitness_evaluator import classify_signal_family
    families = set()
    for _label, code in SEED_ARCHETYPES:
        fn = compile_signal(code)                       # raises if not sandbox-clean
        families.add(classify_signal_family(fn, sol_slice, {}))
    assert len(families) >= 2, f"archetypes not diverse: {families}"


def test_pick_seed_parent_rotates_archetypes():
    from slate_core.discovery.evolution.controller import pick_seed_parent
    cfg = EvolutionConfig()
    rng = random.Random(0)
    seen = {pick_seed_parent(cfg, rng=rng).candidate_id for _ in range(30)}
    assert len(seen) >= 2            # not always the same archetype


def test_gate_rejected_candidate_is_not_stored(sol_slice):
    """Fix 6: a candidate that compiles but FAILS the fitness gate must not be
    added to the database (no -inf elites polluting the population)."""
    from slate_core.discovery.evolution.fitness_evaluator import FitnessConfig

    db = _seed_db()
    before = len(db.island_pool())
    # An impossible min-trade bar -> every candidate fails the two-window gate
    # (fitness.evaluated stays False, fitness_score == -inf).
    prog = asyncio.run(evolution_step(
        db, PromptSampler(), _mock_pool(), sol_slice,
        fitness_config=FitnessConfig(min_trades=10 ** 9),
    ))
    assert prog is None, "gate-rejected candidate was returned"
    assert len(db.island_pool()) == before, "gate-rejected candidate was stored as an elite"


def _labelled_fitness(*_a, **_kw):
    """A gate-passing FitnessResult that ALSO carries behavioural niche labels,
    to prove the controller places the child by its OWN behaviour, not lineage."""
    return FitnessResult(
        evaluated=True, fitness_score=12.0,
        oos_vs_buyhold=12.0, is_vs_buyhold=20.0,
        overfit_gap=8.0, overfit_penalty=4.0,
        n_trades_is=30, n_trades_oos=15,
        validation_score=1.0, candidate_id="test",
        family_label="mean_reversion", regime_label="low_vol",
    )


def test_child_niche_is_behavioral_not_inherited(sol_slice, monkeypatch):
    """Phase 3: the child's niche must come from its OWN evaluated behaviour
    (family_label/regime_label), not the parent's lineage. Without this,
    MAP-Elites collapses every descendant onto the parent's single cell - the
    original 'all momentum / unknown' monoculture."""
    db = _seed_db()                       # parent elite is ('momentum', 'high')
    sampler = PromptSampler()
    pool = _mock_pool()
    monkeypatch.setattr(
        "slate_core.discovery.evolution.controller.eval_fitness_subprocess",
        _labelled_fitness,
    )
    prog = asyncio.run(evolution_step(db, sampler, pool, sol_slice))
    assert prog is not None
    assert prog.family == "mean_reversion", "child inherited parent family instead of its own"
    assert prog.regime == "low_vol", "child inherited parent regime instead of its own"
    assert prog.niche == ("mean_reversion", "low_vol")


def test_evolution_step_stores_verified_candidate(sol_slice, monkeypatch):
    """Rec 2: the controller routes real candidates through the write chokepoint
    (append_verified), so the stored child carries a machine-verification block -
    objective real-data evidence (gate + real_data_result + program_hash), not a
    bare fitness number that could be fiction."""
    db = _seed_db()
    sampler = PromptSampler()
    pool = _mock_pool()
    monkeypatch.setattr(
        "slate_core.discovery.evolution.controller.eval_fitness_subprocess",
        _passing_fitness,
    )
    prog = asyncio.run(evolution_step(db, sampler, pool, sol_slice))
    assert prog is not None
    assert prog.verification.get("gate") == "passed_two_window"
    assert "real_data_result" in prog.verification
    assert "program_hash" in prog.verification
    assert prog.verification["real_data_result"].get("oos_vs_buyhold") == 12.0


# ---------------------------------------------------------------------------
# Funnel diagnostic (Rec 1 / ASTRA §7.2): every candidate's outcome is logged
# ---------------------------------------------------------------------------

def test_evolution_step_logs_passed_verdict(sol_slice, monkeypatch):
    db = _seed_db()
    sampler = PromptSampler()
    pool = _mock_pool()
    monkeypatch.setattr(
        "slate_core.discovery.evolution.controller.eval_fitness_subprocess",
        _passing_fitness,
    )
    recorded = []
    monkeypatch.setattr(
        "slate_core.discovery.evolution.controller.log_candidate_verdict",
        lambda v: recorded.append(v),
    )
    prog = asyncio.run(evolution_step(db, sampler, pool, sol_slice))
    assert prog is not None
    assert len(recorded) == 1
    assert recorded[0].death_stage == "passed"
    assert recorded[0].evaluated is True


def test_evolution_step_logs_verdict_when_gate_rejected(sol_slice, monkeypatch):
    """A gate-rejected candidate is NOT stored, but its death-stage IS logged -
    that is the whole point of the funnel (see where candidates die)."""
    db = _seed_db()
    monkeypatch.setattr(
        "slate_core.discovery.evolution.controller.eval_fitness_subprocess",
        _rejecting_fitness,
    )
    recorded = []
    monkeypatch.setattr(
        "slate_core.discovery.evolution.controller.log_candidate_verdict",
        lambda v: recorded.append(v),
    )
    before = len(db.island_pool())
    prog = asyncio.run(evolution_step(db, PromptSampler(), _mock_pool(), sol_slice))
    assert prog is None
    assert len(db.island_pool()) == before          # not stored ...
    assert len(recorded) == 1                        # ... but IS logged
    assert recorded[0].death_stage == "not_profitable"
    assert recorded[0].evaluated is False


def test_evolution_step_logs_compile_failure_verdict(sol_slice, monkeypatch):
    """A candidate that fails to compile never reaches eval, but its death-stage
    ('compile') is still logged so compile failures are visible in the funnel."""
    db = _seed_db()
    bad = "def signal_fn(df, i, params):\n    import os\n    return 0\n"
    recorded = []
    monkeypatch.setattr(
        "slate_core.discovery.evolution.controller.log_candidate_verdict",
        lambda v: recorded.append(v),
    )
    prog = asyncio.run(evolution_step(db, PromptSampler(), _mock_pool(canned=bad), sol_slice))
    assert prog is None
    assert len(recorded) == 1
    assert recorded[0].death_stage == "compile"
