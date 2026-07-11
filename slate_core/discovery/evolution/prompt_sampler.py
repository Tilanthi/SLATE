"""Rich-context prompt sampler for the evolution loop (Phase 2).

Assembles the AlphaEvolve-style prompt: system instruction, the parent program
(code + fitness + niche + metrics), 2-3 diverse inspirations with their
scores, the OOS-fitness objective, the overfit warning, the daily-timeframe
constraint, and the SEARCH/REPLACE diff rules. Feeding prior winners WITH their
scores back to the LLM (instead of mere bias vectors) is what lets evolution
hill-climb intelligently.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from slate_core.discovery.evolution.program_database import Program

DEFAULT_SYSTEM = (
    "You are an expert quantitative-trading strategy developer evolving a "
    "perpetual-futures signal function. Propose a SMALL, targeted change that "
    "improves OUT-OF-SAMPLE edge without increasing overfit."
)


@dataclass
class PromptObjective:
    metric: str = "oos_vs_buyhold"              # the scalar being maximized
    overfit_warning: str = (
        "Do NOT increase the gap between in-sample and out-of-sample "
        "performance. A larger IS-than-OOS edge is penalized."
    )
    timeframe: str = "daily"                    # SLATE: daily timeframe only
    signal_contract: str = (
        "signal_fn(df, i, params) must return exactly one of {-1, 0, 1} "
        "(-1 short, 0 flat, 1 long)."
    )


SEARCH_REPLACE_RULES = """\
Propose changes as SEARCH/REPLACE blocks:
<<<<<<< SEARCH
# exact original code to find
=======
# new code that replaces it
>>>>>>> REPLACE
"""


class PromptSampler:
    """Builds the evolution prompt from a parent + inspirations."""

    def __init__(self, system_instruction: str = DEFAULT_SYSTEM):
        self.system_instruction = system_instruction

    def build(self, parent: Program, inspirations: List[Program],
              objective: Optional[PromptObjective] = None) -> str:
        obj = objective or PromptObjective()
        parts: List[str] = []

        parts.append(self.system_instruction)
        parts.append(f"\nOBJECTIVE: maximize {obj.metric} (out-of-sample).")
        parts.append(f"TIMEFRAME: {obj.timeframe} only.")
        parts.append(f"CONSTRAINT: {obj.signal_contract}")
        parts.append(f"OVERFIT WARNING: {obj.overfit_warning}")

        parts.append("\n=== PARENT PROGRAM (improve this) ===")
        parts.append(f"id: {parent.candidate_id}")
        parts.append(f"niche: family={parent.family}, regime={parent.regime}")
        parts.append(f"fitness ({obj.metric}): {parent.fitness_score:.2f}")
        if parent.metrics:
            keys = ("oos_vs_buyhold", "total_profit_usdt", "sharpe_ratio",
                    "overfit_penalty", "total_trades")
            shown = {k: parent.metrics[k] for k in keys if k in parent.metrics}
            if shown:
                parts.append(f"metrics: {shown}")
        parts.append("current code:")
        parts.append(parent.code if parent.code else "# (seed program: no code yet)")

        if inspirations:
            parts.append("\n=== INSPIRATIONS (diverse prior winners) ===")
            for i, insp in enumerate(inspirations, 1):
                parts.append(
                    f"[{i}] id={insp.candidate_id} niche=({insp.family},"
                    f"{insp.regime}) fitness={insp.fitness_score:.2f}"
                )

        parts.append("\n=== OUTPUT FORMAT ===")
        parts.append(SEARCH_REPLACE_RULES)
        parts.append(
            "Return ONLY the SEARCH/REPLACE block(s). If a full rewrite is "
            "needed, output the entire new signal_fn instead."
        )
        return "\n".join(parts)
