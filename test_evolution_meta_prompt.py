"""Tests for the Phase 2 meta-prompt store (evolution/meta_prompt_db.py)."""
from slate_core.discovery.evolution.meta_prompt_db import MetaPromptStore
from slate_core.discovery.evolution.llm_client import MockLLMClient, LLMConfig


def test_metaprompt_store_keeps_best():
    s = MetaPromptStore()
    s.add("v1", 1.0)
    s.add("v2", 5.0)
    s.add("v3", 2.0)
    best = s.best()
    assert best is not None
    assert best.instruction == "v2"
    assert best.fitness == 5.0


def test_metaprompt_sample_returns_a_variant():
    s = MetaPromptStore()
    s.add("only", 3.0)
    sampled = s.sample()
    assert sampled is not None
    assert sampled.instruction == "only"


def test_metaprompt_propose_new_uses_llm():
    s = MetaPromptStore()
    s.add("be concise", 2.0)
    client = MockLLMClient(LLMConfig(), canned="Prefer mean-reversion; avoid overfitting.")
    new = s.propose_new(client)
    assert isinstance(new, str) and len(new) > 0
    assert "mean-reversion" in new          # came from the mock LLM output
