"""Multi-objective Pareto selection (Phase 3).

Returns the non-dominated front across user objectives (AlphaEvolve §2.4
"multiple scores"). Objectives are read from Program.metrics; "min" objectives
(e.g. drawdown) are negated internally so "higher is always better" in the
comparison. Default objectives for SLATE: oos_vs_buyhold (max), sharpe (max),
-max_drawdown (min drawdown), and stability via 1/(1+overfit_gap) (max).
"""
from __future__ import annotations

from typing import List, Sequence, Tuple

from slate_core.discovery.evolution.program_database import Program

Objective = Tuple[str, str]                # (metrics_key, "max" | "min")

DEFAULT_OBJECTIVES: Sequence[Objective] = (
    ("oos_vs_buyhold", "max"),
    ("sharpe_ratio", "max"),
    ("max_drawdown_pct", "min"),
    ("stability", "max"),
)


def _value_vector(program: Program, objectives: Sequence[Objective]) -> List[float]:
    """Higher is always better (min objectives negated)."""
    vec = []
    for key, direction in objectives:
        raw = float(program.metrics.get(key, 0.0))
        vec.append(raw if direction == "max" else -raw)
    return vec


def pareto_front(programs: Sequence[Program],
                 objectives: Sequence[Objective] = DEFAULT_OBJECTIVES) -> List[Program]:
    """Return the non-dominated programs. O(n^2) — fine for population sizes."""
    items = list(programs)
    if not items:
        return []
    vecs = [_value_vector(p, objectives) for p in items]
    n_obj = len(objectives)
    front: List[Program] = []
    for i, vi in enumerate(vecs):
        dominated = False
        for j, vj in enumerate(vecs):
            if i == j:
                continue
            ge_all = all(vj[k] >= vi[k] for k in range(n_obj))
            gt_any = any(vj[k] > vi[k] for k in range(n_obj))
            if ge_all and gt_any:
                dominated = True
                break
        if not dominated:
            front.append(items[i])
    return front
