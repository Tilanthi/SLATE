"""Native (non-LLM) variation operators for parameter-vector evolution.

These are the SLATE-native search primitives — pure functions, no LLM, no
external optimizer dependency — ported from the isolated GA in
`intelligence/genetic_optimizer.py` into a live, representation-generic module.
They operate on plain param dicts so they can drive the market-maker parameter
optimizer (and any future non-LLM parameter search) over the existing
ProgramDatabase MAP-Elites infrastructure.

A "param vector" is a `Dict[str, float]`. `bounds` is a `Dict[str, (lo, hi)]`.
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional, Sequence, Tuple

ParamVec = Dict[str, float]
Bounds = Dict[str, Tuple[float, float]]


def clamp(params: ParamVec, bounds: Bounds) -> ParamVec:
    """Clamp each parameter into its [lo, hi] range."""
    out = dict(params)
    for key, (lo, hi) in bounds.items():
        if key in out:
            out[key] = max(lo, min(hi, float(out[key])))
    return out


def gaussian_mutate(params: ParamVec, bounds: Bounds,
                    sigma: float = 0.1, prob: Optional[float] = None,
                    rng: Optional[random.Random] = None) -> ParamVec:
    """Gaussian perturbation of each parameter.

    `sigma` is relative to each parameter's range (0.1 = 10% of the range std),
    so all dimensions perturb on a comparable scale. `prob` (if given) is the
    per-gene probability of being mutated at all (else every gene is mutated).
    """
    r = rng or random.Random()
    out = dict(params)
    for key, (lo, hi) in bounds.items():
        if key not in out:
            continue
        if prob is not None and r.random() >= prob:
            continue
        span = hi - lo
        out[key] = float(out[key]) + r.gauss(0.0, sigma * span)
    return clamp(out, bounds)


def uniform_crossover(p1: ParamVec, p2: ParamVec,
                      rng: Optional[random.Random] = None) -> ParamVec:
    """Uniform (per-gene) crossover of two param vectors."""
    r = rng or random.Random()
    keys = set(p1) | set(p2)
    out: ParamVec = {}
    for k in keys:
        out[k] = float(p1[k]) if (k in p2 and r.random() < 0.5) or k not in p2 else float(p2[k])
    return out


def tournament_select(pop: Sequence, k: int = 3,
                      rng: Optional[random.Random] = None):
    """Tournament selection over objects with a `.fitness_score` attribute.

    Returns the fittest of `k` uniformly-sampled candidates. `pop` items expose
    `fitness_score` (Program does). Returns None on empty input.
    """
    if not pop:
        return None
    r = rng or random.Random()
    contenders = [r.choice(pop) for _ in range(min(k, len(pop)))]
    return max(contenders, key=lambda p: getattr(p, "fitness_score", float("-inf")))


def random_params(bounds: Bounds, rng: Optional[random.Random] = None) -> ParamVec:
    """Seed a random param vector uniformly within `bounds`."""
    r = rng or random.Random()
    return {key: lo + r.random() * (hi - lo) for key, (lo, hi) in bounds.items()}


def params_equal(a: ParamVec, b: ParamVec, tol: float = 1e-9) -> bool:
    """Approximate equality of two param vectors (for de-duplication)."""
    if set(a) != set(b):
        return False
    return all(abs(float(a[k]) - float(b[k])) <= tol for k in a)


__all__ = ["ParamVec", "Bounds", "clamp", "gaussian_mutate", "uniform_crossover",
           "tournament_select", "random_params", "params_equal"]
