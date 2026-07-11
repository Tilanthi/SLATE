"""Return-correlation novelty for diversity (Phase 3).

Novelty search via equity-curve correlation: a candidate is novel if its OOS
equity curve is uncorrelated with the curves already in the population. This is
the diversity dividend AlphaEvolve captures via multi-objective optimization —
it keeps the population covering distinct edges rather than collapsing onto one.
"""
from __future__ import annotations

from typing import List, Sequence

import numpy as np


def equity_correlation(curve_a: Sequence[float], curve_b: Sequence[float]) -> float:
    """Pearson correlation of two equity curves (aligned by leading bars)."""
    a = np.asarray(curve_a, dtype=float)
    b = np.asarray(curve_b, dtype=float)
    n = min(len(a), len(b))
    if n < 3:
        return 0.0
    a = a[:n]
    b = b[:n]
    if a.std() == 0.0 or b.std() == 0.0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def novelty_score(candidate_curve: Sequence[float],
                  population_curves: Sequence[Sequence[float]]) -> float:
    """1.0 = fully novel, 0.0 = identical (in shape) to an existing curve.

    Uses the maximum ABSOLUTE correlation, so both mirrored and copied curves
    count as 'already seen'.
    """
    if not population_curves:
        return 1.0
    max_abs = max(abs(equity_correlation(candidate_curve, c)) for c in population_curves)
    return max(0.0, 1.0 - max_abs)
