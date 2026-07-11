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
    # Mock the (stochastic, gate-dependent) fitness so this plumbing test
    # exercises sample -> compile -> store deterministically.
    monkeypatch.setattr(
        "slate_core.discovery.evolution.controller.evaluate_fitness_two_window",
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
        "slate_core.discovery.evolution.controller.evaluate_fitness_two_window",
        _passing_fitness,
    )
    prog = asyncio.run(evolution_step(db, sampler, pool, sol_slice,
                                      config=EvolutionConfig(edge_type_default="momentum")))
    assert prog is not None
    assert prog.family == "momentum"


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
