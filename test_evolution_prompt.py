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


# ---------------------------------------------------------------------------
# Rec 3 / ASTRA §7.5 + §6: prime the proposer toward NON-OBVIOUS edges
# (the few things that survive EMH + costs on a liquid major), and steer AWAY
# from textbook/already-arbed TA the search would otherwise rediscover forever.
# ---------------------------------------------------------------------------

def test_prompt_steers_toward_non_obvious_edges():
    p = _prog("p", 10.0, code="x")
    prompt = PromptSampler().build(p, [])
    low = prompt.lower()
    assert any(kw in low for kw in
               ["regime", "residual", "non-linear", "interaction", "conditional"]), (
        "prompt does not steer toward non-obvious (regime/residual/non-linear) edges"
    )


def test_prompt_names_known_dead_patterns_to_avoid():
    """The blacklist of textbook TA must be present so the model is steered AWAY
    from re-encoding bare RSI/MA-crossover/momentum (EMH-arbed on liquid majors)."""
    p = _prog("p", 10.0, code="x")
    low = PromptSampler().build(p, []).lower()
    assert "rsi" in low
    assert "moving-average" in low or "ma crossover" in low or "crossover" in low


def test_prompt_has_labeled_alpha_directions_section():
    p = _prog("p", 10.0, code="x")
    assert "alpha directions" in PromptSampler().build(p, []).lower()
