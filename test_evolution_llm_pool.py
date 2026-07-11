"""Tests for the Phase 5 LLM ensemble pool (evolution/llm_pool.py)."""
import random

from slate_core.discovery.evolution.llm_client import MockLLMClient, LLMConfig
from slate_core.discovery.evolution.llm_pool import LLMPool, LLMPoolConfig


def _pool(strong_frac=0.2, seed=0):
    strong = MockLLMClient(LLMConfig(), canned="STRONG")
    fast = MockLLMClient(LLMConfig(), canned="FAST")
    return LLMPool(strong, fast, LLMPoolConfig(strong_fraction=strong_frac),
                   rng=random.Random(seed))


def test_pool_fast_tier_uses_fast_client():
    pool = _pool()
    assert pool.generate("p", tier="fast") == "FAST"


def test_pool_strong_tier_uses_strong_client():
    pool = _pool()
    assert pool.generate("p", tier="strong") == "STRONG"


def test_pool_auto_mix_eventually_uses_both_clients():
    pool = _pool(strong_frac=0.5, seed=1)
    seen = {pool.generate("p") for _ in range(40)}
    assert seen == {"STRONG", "FAST"}


def test_pool_returns_nonempty_string():
    pool = _pool()
    out = pool.generate("p", tier="fast")
    assert isinstance(out, str) and len(out) > 0
