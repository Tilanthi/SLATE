"""Tests for the provider-agnostic LLM client (evolution/llm_client.py).

All tests use the Mock backend or inspect config — NO network calls."""
import os

from slate_core.discovery.evolution.llm_client import (
    LLMConfig, MockLLMClient, AnthropicClient, get_llm_client,
)


def test_mock_client_returns_canned():
    c = MockLLMClient(LLMConfig(), canned="hello world")
    assert c.generate("any prompt") == "hello world"


def test_mock_client_default_is_deterministic():
    a = MockLLMClient(LLMConfig()).generate("prompt one")
    b = MockLLMClient(LLMConfig()).generate("prompt two")
    assert a == b and isinstance(a, str) and len(a) > 0


def test_get_llm_client_auto_returns_mock_without_token(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    c = get_llm_client(LLMConfig(backend="auto"))
    assert isinstance(c, MockLLMClient)


def test_get_llm_client_auto_returns_anthropic_with_token(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "test-token")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.z.ai")
    c = get_llm_client(LLMConfig(backend="auto"))
    assert isinstance(c, AnthropicClient)
    assert c.api_key == "test-token"
    assert "z.ai" in c.base_url


def test_anthropic_client_carries_config_and_does_not_touch_network():
    c = AnthropicClient(LLMConfig(strong_model="claude-sonnet-5",
                                  fast_model="claude-3-5-haiku-latest"))
    assert c.strong_model == "claude-sonnet-5"
    assert c.fast_model == "claude-3-5-haiku-latest"
    assert c.model == "claude-sonnet-5"  # default selection
