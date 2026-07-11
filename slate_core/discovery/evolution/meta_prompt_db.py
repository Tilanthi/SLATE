"""Meta-prompt evolution (Phase 2).

A small store that co-evolves the NATURAL-LANGUAGE instructions fed to the
evolution LLM, in a separate database (AlphaEvolve §2.2 "meta prompt
evolution"). Each instruction variant carries a fitness = how well the
strategies it generated performed. The best instruction is reused; an LLM call
periodically proposes a better one.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional

from slate_core.discovery.evolution.llm_client import LLMClient

DEFAULT_INSTRUCTION = (
    "Propose a small change to the signal function that improves out-of-sample "
    "edge vs buy-and-hold on a daily timeframe, without increasing overfit."
)


@dataclass
class MetaPrompt:
    instruction: str
    fitness: float = 0.0
    generation: int = 0


class MetaPromptStore:
    """Keeps the best instruction(s) by fitness; proposes new ones via an LLM."""

    def __init__(self, cap: int = 8):
        self.cap = cap
        self._items: List[MetaPrompt] = []

    def add(self, instruction: str, fitness: float, generation: int = 0) -> None:
        self._items.append(MetaPrompt(instruction, fitness, generation))
        self._items.sort(key=lambda m: m.fitness, reverse=True)
        self._items = self._items[: self.cap]

    def best(self) -> Optional[MetaPrompt]:
        return self._items[0] if self._items else None

    def sample(self, rng: Optional[random.Random] = None) -> Optional[MetaPrompt]:
        if not self._items:
            return None
        r = rng or random.Random()
        # 70% best, 30% random — exploitation/exploration like the program DB
        if r.random() < 0.7 or len(self._items) == 1:
            return self.best()
        return r.choice(self._items)

    def propose_new(self, client: LLMClient, objective_summary: str = "",
                    model: Optional[str] = None) -> str:
        """Ask the LLM to propose an improved instruction; return it (stripped)."""
        current = self.best()
        prompt = (
            "You are improving the INSTRUCTION used to guide an evolutionary "
            "trading-strategy search. Better instructions yield strategies with "
            "higher out-of-sample edge.\n\n"
            f"Current best instruction (fitness={current.fitness:.2f}):\n"
            f"{current.instruction if current else DEFAULT_INSTRUCTION}\n\n"
            f"Objective context: {objective_summary or 'maximize oos_vs_buyhold'}\n"
            "Reply with ONLY a single improved instruction paragraph."
        )
        out = client.generate(prompt, model=model)
        return (out or DEFAULT_INSTRUCTION).strip() or DEFAULT_INSTRUCTION
