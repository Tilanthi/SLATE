"""Tests for the DEX evolution controller (slate_core.dex.evolution.dex_controller)."""
import asyncio
import random

import numpy as np
import pandas as pd

from slate_core.discovery.evolution.controller import EvolutionConfig
from slate_core.discovery.evolution.program_database import (
    Program, ProgramDatabase, ProgramDBConfig,
)
from slate_core.discovery.evolution.llm_client import MockLLMClient, LLMConfig
from slate_core.discovery.evolution.llm_pool import LLMPool, LLMPoolConfig
from slate_core.discovery.evolution.evolvable_strategy import BASE_SIGNAL_CODE
from slate_core.discovery.evolution.fitness_evaluator import FitnessResult
from slate_core.dex.evolution.dex_controller import dex_evolution_step, DexPromptSampler


def _passing(*a, **kw):
    return FitnessResult(evaluated=True, fitness_score=50.0, oos_vs_buyhold=50.0,
                         is_vs_buyhold=80.0, overfit_gap=30.0, overfit_penalty=10.0,
                         n_trades_is=40, n_trades_oos=20, validation_score=1.0,
                         candidate_id="t", family_label="momentum", regime_label="high_vol")


def _rejecting(*a, **kw):
    return FitnessResult(evaluated=False, fitness_score=float("-inf"),
                         oos_vs_buyhold=0.0, is_vs_buyhold=0.0, overfit_gap=0.0,
                         overfit_penalty=0.0, n_trades_is=0, n_trades_oos=0,
                         validation_score=0.0, candidate_id="t",
                         rejection_reason="oos1_pnl=0.00<=0; oos1_trades=0<10")


def _seed_db():
    db = ProgramDatabase(ProgramDBConfig(persist_path=None))
    db.add(Program(candidate_id="seed1", niche=("momentum", "high"), family="momentum",
                   regime="high", fitness_score=10.0, source="seed", code=BASE_SIGNAL_CODE))
    return db


def _mock_pool(canned=None):
    s = MockLLMClient(LLMConfig(), canned=canned) if canned else MockLLMClient(LLMConfig())
    f = MockLLMClient(LLMConfig(), canned=canned) if canned else MockLLMClient(LLMConfig())
    return LLMPool(s, f, LLMPoolConfig(), rng=random.Random(0))


def _df():
    n = 100
    idx = pd.date_range("2026-01-01", periods=n, freq="1h")
    close = 100 + np.arange(n) * 0.1
    return pd.DataFrame({"open": close, "high": close + 0.5, "low": close - 0.5,
                         "close": close}, index=idx)


def test_dex_step_stores_verified_candidate(monkeypatch):
    db = _seed_db()
    monkeypatch.setattr("slate_core.dex.evolution.dex_controller.dex_eval_fitness_subprocess", _passing)
    recorded = []
    monkeypatch.setattr("slate_core.dex.evolution.dex_controller.log_dex_verdict",
                        lambda v: recorded.append(v))
    prog = asyncio.run(dex_evolution_step(db, DexPromptSampler(), _mock_pool(), _df()))
    assert prog is not None
    assert prog.verification.get("gate") == "dex_passed_two_window"
    assert prog.verification["real_data_result"]["oos_pnl"] == 50.0
    assert len(recorded) == 1 and recorded[0].death_stage == "passed"
    assert any(p.candidate_id == prog.candidate_id for p in db.island_pool())


def test_dex_step_rejected_not_stored_but_logged(monkeypatch):
    db = _seed_db()
    before = len(db.island_pool())
    monkeypatch.setattr("slate_core.dex.evolution.dex_controller.dex_eval_fitness_subprocess", _rejecting)
    recorded = []
    monkeypatch.setattr("slate_core.dex.evolution.dex_controller.log_dex_verdict",
                        lambda v: recorded.append(v))
    prog = asyncio.run(dex_evolution_step(db, DexPromptSampler(), _mock_pool(), _df()))
    assert prog is None
    assert len(db.island_pool()) == before
    assert len(recorded) == 1 and recorded[0].death_stage != "passed"


def test_dex_step_compile_failure_logged(monkeypatch):
    db = _seed_db()
    bad = "def signal_fn(df, i, params):\n    import os\n    return 0\n"
    monkeypatch.setattr("slate_core.dex.evolution.dex_controller.dex_eval_fitness_subprocess", _passing)
    recorded = []
    monkeypatch.setattr("slate_core.dex.evolution.dex_controller.log_dex_verdict",
                        lambda v: recorded.append(v))
    prog = asyncio.run(dex_evolution_step(db, DexPromptSampler(), _mock_pool(canned=bad), _df()))
    assert prog is None
    assert len(recorded) == 1 and recorded[0].death_stage == "compile"


def test_dex_mm_step_stores_verified_candidate(monkeypatch):
    """Step 3: the MM evolution step evolves quote_fn, routes through the
    chokepoint, and logs a verdict."""
    from slate_core.dex.evolution.dex_controller import dex_mm_evolution_step, DexMMPromptSampler
    db = ProgramDatabase(ProgramDBConfig(persist_path=None))   # empty -> MM base parent
    monkeypatch.setattr("slate_core.dex.evolution.dex_controller.dex_mm_eval_fitness_subprocess", _passing)
    recorded = []
    monkeypatch.setattr("slate_core.dex.evolution.dex_controller.log_dex_verdict",
                        lambda v: recorded.append(v))
    canned = "def quote_fn(state):\n    return (12.0, 3.0, 0.5)\n"
    prog = asyncio.run(dex_mm_evolution_step(db, DexMMPromptSampler(), _mock_pool(canned=canned), _df()))
    assert prog is not None
    assert prog.verification.get("gate") == "dex_mm_passed_two_window"
    assert len(recorded) == 1 and recorded[0].death_stage == "passed"


def test_dex_pairs_step_stores_verified_candidate(monkeypatch):
    """target=pairs: the pairs evolution step evolves spread_fn, routes through the
    chokepoint, and logs a verdict."""
    from slate_core.dex.evolution.dex_controller import dex_pairs_evolution_step, DexPairsPromptSampler
    db = ProgramDatabase(ProgramDBConfig(persist_path=None))   # empty -> pairs base parent
    monkeypatch.setattr("slate_core.dex.evolution.dex_controller.dex_pairs_eval_fitness_subprocess",
                        _passing)
    recorded = []
    monkeypatch.setattr("slate_core.dex.evolution.dex_controller.log_dex_verdict",
                        lambda v: recorded.append(v))
    canned = "def spread_fn(dfA, dfB, i):\n    return 1 if i > 60 else 0\n"
    prog = asyncio.run(dex_pairs_evolution_step(
        db, DexPairsPromptSampler(), _mock_pool(canned=canned), _df(), _df()))
    assert prog is not None
    assert prog.verification.get("gate") == "dex_pairs_passed_two_window"
    assert prog.family == "pairs"
    assert len(recorded) == 1 and recorded[0].death_stage == "passed"


def test_dex_service_uses_loosened_complexity_cap():
    """The DEX cap is loosened from the CEX 200 (measured DEX signals cluster at
    201-350) so candidates reach evaluation; CEX stays at 200."""
    import os as _os
    import tempfile
    from slate_core.dex.evolution.dex_service import DexEvolutionService
    from slate_core.discovery.evolution.llm_client import MockLLMClient, LLMConfig
    path = tempfile.mktemp(suffix=".db")
    try:
        svc = DexEvolutionService(persist_path=path, llm_client=MockLLMClient(LLMConfig()))
        assert svc.evolution_config.max_signal_complexity == 350
        assert svc.evolution_config.max_signal_complexity > 200
    finally:
        if _os.path.exists(path):
            _os.remove(path)


def test_run_steps_parallel_gathers_all():
    """P1: the concurrent runner gathers n_steps (concurrency at a time)."""
    from slate_core.dex.evolution.dex_controller import _run_steps_parallel
    counter = {"n": 0}

    async def step():
        counter["n"] += 1
        return f"p{counter['n']}"

    out = asyncio.run(_run_steps_parallel(step, 4, 4))
    assert len(out) == 4


def test_hash_dedup_skips_identical_code(monkeypatch):
    """P1: byte-identical code is evaluated once, then deduped."""
    from slate_core.dex.evolution.dex_controller import dex_evolution_step, _EVALUATED_HASHES
    db = _seed_db()
    calls = []

    def counting(*a, **kw):
        calls.append(1)
        return _passing(*a, **kw)

    monkeypatch.setattr("slate_core.dex.evolution.dex_controller.dex_eval_fitness_subprocess",
                        counting)
    _EVALUATED_HASHES.clear()
    canned = "def signal_fn(df, i, params):\n    return 1\n"
    asyncio.run(dex_evolution_step(db, DexPromptSampler(), _mock_pool(canned=canned), _df()))
    asyncio.run(dex_evolution_step(db, DexPromptSampler(), _mock_pool(canned=canned), _df()))
    assert len(calls) == 1            # second identical code deduped


def test_dex_failure_summary_and_prompt_injection(tmp_path):
    """P5: the failure distribution is summarized and injected into the prompt."""
    import json
    from slate_core.dex.evolution.dex_controller import dex_failure_summary, DexPromptSampler
    p = tmp_path / "dex.jsonl"
    p.write_text("\n".join(json.dumps({"death_stage": s}) for s in
                           ["not_profitable", "not_profitable", "overfit_fitness"]))
    summ = dex_failure_summary(str(p))
    assert "not_profitable" in summ and "overfit" in summ
    s = DexPromptSampler()
    s.failure_summary = summ
    parent = Program(candidate_id="p", niche=("m", "h"), family="m", regime="h",
                     fitness_score=1.0, source="seed", code="x")
    assert "RECENT FAILURE FEEDBACK" in s.build(parent, [])
