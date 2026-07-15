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
