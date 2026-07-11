"""LLM ensemble pool (Phase 5).

Wraps a fast + a strong client (AlphaEvolve's Gemini-Flash + Pro mix). Most
calls go to the fast model for volume; a configurable fraction go to the
strong model for occasional breakthroughs. Both point at the Z.ai proxy via
the shared LLMClient, so no extra key is needed.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

from slate_core.discovery.evolution.llm_client import LLMClient


@dataclass
class LLMPoolConfig:
    strong_model: str = "claude-sonnet-5"
    fast_model: str = "claude-3-5-haiku-latest"
    strong_fraction: float = 0.2     # fraction of 'auto' calls routed to strong


class LLMPool:
    """Ensemble of two LLMClients. generate(tier='auto') mixes them."""

    def __init__(self, strong: LLMClient, fast: LLMClient,
                 config: Optional[LLMPoolConfig] = None,
                 rng: Optional[random.Random] = None):
        self.strong = strong
        self.fast = fast
        self.config = config or LLMPoolConfig()
        self.rng = rng or random.Random()

    def generate(self, prompt: str, system: Optional[str] = None,
                 tier: str = "auto", max_tokens: Optional[int] = None) -> str:
        if tier == "strong":
            client, model = self.strong, self.config.strong_model
        elif tier == "fast":
            client, model = self.fast, self.config.fast_model
        else:  # auto: volume + occasional breakthroughs
            use_strong = self.rng.random() < self.config.strong_fraction
            client = self.strong if use_strong else self.fast
            model = self.config.strong_model if use_strong else self.config.fast_model
        return client.generate(prompt, system=system, model=model, max_tokens=max_tokens)
