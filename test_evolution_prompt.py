"""Tests for the Phase 2 prompt sampler (evolution/prompt_sampler.py)."""
from slate_core.discovery.evolution.program_database import Program
from slate_core.discovery.evolution.prompt_sampler import (
    PromptSampler, PromptObjective,
)


def _prog(cid, fitness, code=None, family="momentum", regime="high"):
    return Program(candidate_id=cid, niche=(family, regime), family=family,
                   regime=regime, fitness_score=fitness, source="evolved",
                   code=code, metrics={"oos_vs_buyhold": fitness})


def test_prompt_includes_parent_id_fitness_and_code():
    p = _prog("parent1", 123.45, code="def signal_fn(df, i, params):\n    return 1")
    prompt = PromptSampler().build(p, [])
    assert "parent1" in prompt
    assert "123.45" in prompt
    assert "def signal_fn" in prompt


def test_prompt_includes_inspiration_niches_and_scores():
    p = _prog("p", 10.0, code="x")
    insp = [_prog("i1", 8.0, family="arbitrage", regime="low"),
            _prog("i2", 6.0, family="mean_reversion", regime="mid")]
    prompt = PromptSampler().build(p, insp)
    assert "arbitrage" in prompt and "low" in prompt
    assert "mean_reversion" in prompt
    assert "8.00" in prompt and "6.00" in prompt


def test_prompt_includes_rules_objective_and_timeframe():
    p = _prog("p", 10.0, code="x")
    prompt = PromptSampler().build(p, [], PromptObjective(metric="oos_vs_buyhold"))
    assert "SEARCH" in prompt and "REPLACE" in prompt
    assert "oos_vs_buyhold" in prompt
    assert "daily" in prompt.lower()        # SLATE daily-timeframe constraint
    assert "overfit" in prompt.lower()      # overfit warning present


def test_prompt_handles_seed_parent_with_no_code():
    p = Program(candidate_id="seed:foo", niche=("enhanced_ema", "unknown"),
                family="enhanced_ema", regime="unknown", fitness_score=50.0,
                source="seed", code=None)
    prompt = PromptSampler().build(p, [])
    assert "seed:foo" in prompt
    assert "50" in prompt
    assert "no code" in prompt.lower() or "seed" in prompt.lower()
