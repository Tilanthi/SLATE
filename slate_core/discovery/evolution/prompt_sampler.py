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
    "You are an expert quantitative-trading strategist evolving a perpetual-"
    "futures signal on REAL daily OHLCV data. The daily-timeframe edge on a "
    "liquid major is RARE and almost always non-obvious - efficient markets "
    "have already priced bare technical analysis - so prefer the non-obvious "
    "structures in ALPHA DIRECTIONS below and avoid re-encoding the textbook "
    "indicators in KNOWN-DEAD PATTERNS. Propose a SMALL, targeted change that "
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

# Rec 3 / ASTRA §7.5 + §6: the daily edge on a liquid major survives costs only
# when it is non-obvious. The signal has OHLCV + injected EMAs (no order-book or
# funding fields), so the productive non-obvious directions are CONDITIONAL,
# RESIDUAL, and NON-LINEAR structure - the trading analogue of ASTRA's higher-
# order relation priming (which was its single biggest lever on the novel rate).
ALPHA_DIRECTIONS = """\
ALPHA DIRECTIONS - reach past simple pairwise/linear relations toward
CONDITIONAL, RESIDUAL, and NON-LINEAR structure:
- REGIME-CONDITIONAL: trade differently by volatility regime (e.g. only act
  when ATR/realized-vol is in a specific tercile, or range expansion vs
  contraction). Most real edges are regime-specific, not all-weather.
- RESIDUAL / RELATIVE: trade the deviation from a fitted trend or expected move
  (mean-reversion of residuals after removing drift), not raw price.
- NON-LINEAR / INTERACTION: threshold/curvature effects, and interactions of
  >=3 variables (e.g. return x volume x volatility; high-low range x trend).
- VOLATILITY & VOLUME STRUCTURE: use high-low range (a vol proxy), volume
  spikes, and vol-of-vol, usually as CONDITIONING variables.
Aim for a signal whose profitability is concentrated in a specific state, not
spread thinly across every bar (thin edges do not clear costs)."""

# ASTRA §7.6: mark the textbook-saturated subdomains and stop burning scale on
# them. These are already-arbed on liquid majors; do NOT submit bare versions.
KNOWN_DEAD_PATTERNS = """\
KNOWN-DEAD PATTERNS (textbook / already-arbed on liquid majors) - do NOT submit
bare versions of these. If you use one, it must be a non-obvious INGREDIENT in a
conditional/residual/interaction combo, not the whole signal:
- Bare RSI thresholds (RSI<30 buy / RSI>70 sell)
- Plain moving-average crossovers (fast MA crosses slow MA)
- Generic same-direction momentum (return over N bars -> buy)
- MACD signal-line crosses
- Bollinger-band touch at +/-2 sigma
These barely clear costs on efficient markets and the search has already
explored them heavily."""


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
        parts.append(ALPHA_DIRECTIONS)
        parts.append(KNOWN_DEAD_PATTERNS)

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
