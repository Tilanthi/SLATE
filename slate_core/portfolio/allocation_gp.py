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
    # Dirichlet sample for properly normalized random weights
    raw = r.dirichlet(np.ones(len(stream_names)))
    weights = {name: float(raw[i]) for i, name in enumerate(stream_names)}
    return AllocationGenome(
        stream_weights=weights,
        dd_throttle_start=float(r.uniform(0.05, 0.12)),
        dd_throttle_half=float(r.uniform(0.10, 0.18)),
        dd_throttle_flat=float(r.uniform(0.15, 0.25)),
        regime_stress_factor=float(r.uniform(0.3, 0.7)),
        target_portfolio_vol=float(r.uniform(0.10, 0.25)),
    )


def _mutate_genome(genome: AllocationGenome, rng: np.random.RandomState,
                   sigma: float = 0.15) -> AllocationGenome:
    """Gaussian mutation of an allocation genome."""
    names = list(genome.stream_weights.keys())
    raw = np.array([genome.stream_weights[n] for n in names])
    raw = raw + rng.normal(0, sigma, len(raw))
    raw = np.clip(raw, 0.0, None)
    total = raw.sum()
    if total > 0:
        raw = raw / total
    else:
        raw = np.ones(len(names)) / len(names)
    return AllocationGenome(
        stream_weights={n: float(raw[i]) for i, n in enumerate(names)},
        dd_throttle_start=max(0.02, genome.dd_throttle_start + rng.normal(0, 0.01)),
        dd_throttle_half=max(0.05, genome.dd_throttle_half + rng.normal(0, 0.02)),
        dd_throttle_flat=max(0.10, genome.dd_throttle_flat + rng.normal(0, 0.02)),
        regime_stress_factor=np.clip(genome.regime_stress_factor + rng.normal(0, 0.05), 0.1, 0.9),
        target_portfolio_vol=np.clip(genome.target_portfolio_vol + rng.normal(0, 0.02), 0.05, 0.40),
    )


def evolve_allocation(stream_returns: Dict[str, np.ndarray],
                      n_gen: int = 20, pop_size: int = 40,
                      elite_frac: float = 0.25, seed: int = 42) -> Dict:
    """Evolve the best allocation/risk policy via a native GA (no LLM).

    Genome = stream weights + risk thresholds. Fitness = portfolio risk-adjusted
    return (Sharpe/Calmar minus drawdown penalty) via the portfolio backtester.
    This is native intelligence applied to the META-problem: HOW to weight and
    risk-manage the premium book, NOT what to predict.

    Returns {best_genome, best_metrics, history}.
    """
    rng = np.random.RandomState(seed)
    names = list(stream_returns.keys())
    if len(names) < 2:
        return {"best_genome": None, "best_metrics": {}, "history": []}

    # Initialize population
    pop = [random_allocation_genome(names, rng) for _ in range(pop_size)]
    best_genome = None
    best_fitness = float("-inf")
    best_metrics = {}
    history = []

    for gen in range(n_gen):
        # Evaluate
        scored = []
        for genome in pop:
            metrics = evaluate_allocation(genome, stream_returns)
            scored.append((genome, metrics, metrics["fitness"]))
        scored.sort(key=lambda x: x[2], reverse=True)

        # Track best
        if scored[0][2] > best_fitness:
            best_fitness = scored[0][2]
            best_genome = scored[0][0]
            best_metrics = scored[0][1]

        history.append({"gen": gen, "best_fitness": round(best_fitness, 4),
                        "best_sharpe": round(best_metrics.get("sharpe", 0), 4)})

        # Select elites + generate offspring
        n_elite = max(2, int(pop_size * elite_frac))
        elites = [s[0] for s in scored[:n_elite]]
        offspring = []
        for _ in range(pop_size - n_elite):
            parent = rng.choice(elites)
            child = _mutate_genome(parent, rng)
            offspring.append(child)
        pop = elites + offspring

    return {
        "best_genome": best_genome,
        "best_metrics": best_metrics,
        "history": history,
    }


__all__ = ["AllocationGenome", "evaluate_allocation", "random_allocation_genome",
           "evolve_allocation"]
