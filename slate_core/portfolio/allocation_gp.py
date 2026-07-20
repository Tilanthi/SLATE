"""Allocation-policy GP scaffold (Phase 5 — interface defined, evolution deferred).

Evolves the ALLOCATION / RISK policy across a diversified premium book — NOT a
price predictor. The genome is a set of allocation weights + risk thresholds
(dd_throttle levels, regime-gate thresholds); the fitness is the portfolio's
risk-adjusted return (Sharpe / Calmar) from the PortfolioBacktester, validated
walk-forward + Monte Carlo.

This is where SLATE's native intelligence (GP + swarm) drives the META-problem:
how to weight and risk-manage the premium book across regimes, NOT how to
predict price direction. Full evolution deferred until Phases 1–4 are
battle-tested; the interface is defined so it can drop in.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np


@dataclass
class AllocationGenome:
    """A candidate allocation/risk policy for the premium book.

    Each stream gets a base weight; risk thresholds control drawdown response.
    The GP varies these; the portfolio backtester scores the result.
    """
    stream_weights: Dict[str, float] = field(default_factory=dict)
    dd_throttle_start: float = 0.08
    dd_throttle_half: float = 0.12
    dd_throttle_flat: float = 0.18
    regime_stress_factor: float = 0.5
    target_portfolio_vol: float = 0.15


def evaluate_allocation(genome: AllocationGenome,
                        stream_returns: Dict[str, np.ndarray]) -> Dict:
    """Score an allocation genome via the portfolio backtester.

    Returns the portfolio's risk-adjusted metrics (the fitness signal for GP).
    This is the FITNESS FUNCTION the GP optimizes — portfolio Sharpe/Calmar,
    not single-strategy profit.
    """
    from slate_core.portfolio.portfolio_backtester import PortfolioBacktester

    bt = PortfolioBacktester(periods_per_year=365)
    combined = bt.combine(stream_returns, genome.stream_weights)
    wf = bt.walk_forward_validate(stream_returns, genome.stream_weights, n_folds=5)
    mc = bt.monte_carlo(combined["returns"], n_sims=500)

    sharpe = combined["metrics"].get("sharpe", 0)
    calmar = combined["metrics"].get("calmar", 0)
    mdd = combined["metrics"].get("max_drawdown", 1)
    p95_dd = mc.get("p95_dd", mdd)
    wf_worst = min((f.get("sharpe", -999) for f in wf.get("folds", [])), default=-999)

    # Fitness = robustness-weighted Sharpe (penalise high DD + fold variance)
    dd_penalty = max(0, p95_dd - 0.10) * 5.0   # penalise p95 DD > 10%
    fitness = sharpe + 0.5 * calmar - dd_penalty + 0.3 * wf_worst

    return {
        "fitness": fitness,
        "sharpe": sharpe,
        "calmar": calmar,
        "max_drawdown": mdd,
        "p95_drawdown": p95_dd,
        "worst_fold_sharpe": wf_worst,
        "diversification_ratio": combined.get("diversification_ratio", 1.0),
    }


def random_allocation_genome(stream_names: List[str],
                             rng: np.random.RandomState = None) -> AllocationGenome:
    """Seed a random allocation genome (for GP initialization)."""
    r = rng or np.random.RandomState()
    raw = {name: float(r.dirichlet(np.ones(1))[0]) for name in stream_names}
    total = sum(raw.values()) or 1.0
    weights = {k: v / total for k, v in raw.items()}
    return AllocationGenome(
        stream_weights=weights,
        dd_throttle_start=float(r.uniform(0.05, 0.12)),
        dd_throttle_half=float(r.uniform(0.10, 0.18)),
        dd_throttle_flat=float(r.uniform(0.15, 0.25)),
        regime_stress_factor=float(r.uniform(0.3, 0.7)),
        target_portfolio_vol=float(r.uniform(0.10, 0.25)),
    )


__all__ = ["AllocationGenome", "evaluate_allocation", "random_allocation_genome"]
