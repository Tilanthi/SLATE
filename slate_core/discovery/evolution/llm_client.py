"""Provider-agnostic LLM client for the evolution layer.

The user runs GLM via Claude Code, which routes through Z.ai's
Anthropic-protocol-compatible proxy (ANTHROPIC_BASE_URL=https://api.z.ai,
ANTHROPIC_AUTH_TOKEN=<key>). So SLATE needs NO separate key: the Anthropic
backend reuses that exact proxy + token (verified 2026-07-11:
`claude-sonnet-5` via Z.ai returns OK).

Three backends:
  - "anthropic"     : anthropic SDK -> Z.ai proxy (default when token present)
  - "openai_compat" : requests -> any OpenAI-compatible endpoint (optional)
  - "mock"          : deterministic, offline (used by ALL tests; fallback when
                      no token is set)

Evolution never hard-depends on a live model: tests run on the mock, and the
controller treats a failed/empty generation as a skipped candidate.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_STRONG = "claude-sonnet-5"
_DEFAULT_FAST = "claude-3-5-haiku-latest"
# A benign, valid signal body the mock returns so Phase 4 code-gen tests get a
# compilable candidate by default.
_MOCK_SIGNAL_BODY = (
    "def signal_fn(df, i, params):\n"
    "    # evolved (mock): long if short EMA above long EMA, else short\n"
    "    close = df['close'].iloc[i]\n"
    "    prev = df['close'].iloc[i - 1]\n"
    "    return 1 if close > prev else -1\n"
)


@dataclass
class LLMConfig:
    backend: str = "auto"                       # auto|anthropic|openai_compat|mock
    base_url: Optional[str] = None              # default: env ANTHROPIC_BASE_URL
    api_key: Optional[str] = None               # default: env ANTHROPIC_AUTH_TOKEN
    strong_model: str = _DEFAULT_STRONG
    fast_model: str = _DEFAULT_FAST
    max_tokens: int = 1024
    temperature: float = 0.9
    timeout: float = 60.0


class LLMClient:
    """Base interface. generate() returns the model's text ("" on failure)."""
    name = "base"

    def generate(self, prompt: str, system: Optional[str] = None,
                 model: Optional[str] = None, max_tokens: Optional[int] = None) -> str:
        raise NotImplementedError


class MockLLMClient(LLMClient):
    """Deterministic, offline client. Returns a fixed canned string."""
    name = "mock"

    def __init__(self, config: LLMConfig, canned: str = _MOCK_SIGNAL_BODY):
        self.config = config
        self.canned = canned

    def generate(self, prompt: str, system: Optional[str] = None,
                 model: Optional[str] = None, max_tokens: Optional[int] = None) -> str:
        return self.canned


class AnthropicClient(LLMClient):
    """Anthropic Messages-API client pointed at the Z.ai proxy (or real Anthropic).

    The SDK is imported lazily in generate(), so merely constructing the client
    needs neither the package nor network. Failures log + return "" so the
    evolution loop survives transient model errors.
    """
    name = "anthropic"

    def __init__(self, config: LLMConfig):
        self.config = config
        self.base_url = config.base_url or os.environ.get("ANTHROPIC_BASE_URL")
        self.api_key = config.api_key or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        self.strong_model = config.strong_model
        self.fast_model = config.fast_model
        self.model = config.strong_model            # default selection

    def generate(self, prompt: str, system: Optional[str] = None,
                 model: Optional[str] = None, max_tokens: Optional[int] = None) -> str:
        try:
            from anthropic import Anthropic
        except ImportError:
            logger.warning("anthropic SDK not installed; returning empty generation")
            return ""
        try:
            client = Anthropic(base_url=self.base_url, api_key=self.api_key)
            msg = client.messages.create(
                model=model or self.model,
                max_tokens=max_tokens or self.config.max_tokens,
                temperature=self.config.temperature,
                system=system or "",
                messages=[{"role": "user", "content": prompt}],
                timeout=self.config.timeout,
            )
            return "".join(b.text for b in msg.content if hasattr(b, "text"))
        except Exception as exc:  # noqa: BLE001 - keep the loop alive
            logger.warning("anthropic generate failed: %s", str(exc)[:200])
            return ""


class OpenAICompatClient(LLMClient):
    """Optional OpenAI-compatible client via requests (Z.ai/OpenAI/Ollama/vLLM)."""
    name = "openai_compat"

    def __init__(self, config: LLMConfig):
        self.config = config
        self.base_url = (config.base_url or os.environ.get("SLATE_LLM_BASE_URL") or "").rstrip("/")
        self.api_key = config.api_key or os.environ.get("SLATE_LLM_API_KEY")
        self.model = config.strong_model

    def generate(self, prompt: str, system: Optional[str] = None,
                 model: Optional[str] = None, max_tokens: Optional[int] = None) -> str:
        try:
            import requests
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json"},
                json={"model": model or self.model,
                      "messages": messages,
                      "max_tokens": max_tokens or self.config.max_tokens,
                      "temperature": self.config.temperature},
                timeout=self.config.timeout,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001
            logger.warning("openai_compat generate failed: %s", str(exc)[:200])
            return ""


def get_llm_client(config: Optional[LLMConfig] = None) -> LLMClient:
    """Build a client per config.backend. 'auto' picks anthropic if a token is
    present, else mock."""
    cfg = config or LLMConfig()
    if cfg.backend == "mock":
        return MockLLMClient(cfg)
    if cfg.backend == "anthropic":
        return AnthropicClient(cfg)
    if cfg.backend == "openai_compat":
        return OpenAICompatClient(cfg)
    # auto
    if os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return AnthropicClient(cfg)
    logger.info("No ANTHROPIC_AUTH_TOKEN set; using MockLLMClient (offline mode).")
    return MockLLMClient(cfg)
