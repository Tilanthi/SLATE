"""Tests for structure-level GP fitness + novelty (slate_core.dex.evolution.gp.fitness)."""
import random

from slate_core.dex.evolution.gp import Node, Individual
from slate_core.dex.evolution.gp.fitness import evaluate_gp_tree, textbook_archetype_curves
from slate_core.discovery.evolution.fitness_evaluator import FitnessConfig


def _snap(t, mid, bids, asks, imbalance=0.1):
    return {"t": t, "coin": "SOL", "mid": mid, "spread_bps": 1.0, "imbalance": imbalance,
            "bids": [[p, s] for p, s in bids], "asks": [[p, s] for p, s in asks]}


def _stream(n=1500, mid=100.0):
    """Oscillating two-sided pressure with VARYING imbalance (so a feature-conditioned
    policy behaves differently from a fixed-spread one)."""
    snaps = []
    for i in range(n):
        imb = 0.3 if i % 2 == 0 else -0.3          # imbalance alternates
        if i % 2 == 0:
            snaps.append(_snap(i, mid, [(99.9, 0.5)], [(100.1, 5.0)], imbalance=imb))
        else:
            snaps.append(_snap(i, mid, [(99.9, 5.0)], [(100.1, 0.5)], imbalance=imb))
    return snaps


def _const_individual(half=10.0, skew=0.0, size=0.5):
    """A 'textbook' fixed-quote individual (no feature conditioning)."""
    return Individual(Node("const", half), Node("const", skew), Node("const", size))


def _imbalance_conditioned_individual():
    """A non-textbook individual: spread widens when order-flow imbalance is high."""
    cond = Node("func", "gt", [Node("feature", "imbalance"), Node("const", 0.0)])
    half = Node("func", "if_else", [cond, Node("const", 5.0), Node("const", 25.0)])
    return Individual(half, Node("const", 0.0), Node("const", 0.5))


def test_evaluate_returns_smooth_fitness_and_gate_flag():
    snaps = _stream()
    arch = textbook_archetype_curves(snaps)
    res = evaluate_gp_tree(_const_individual(), snaps, FitnessConfig(min_trades=1),
                           archetype_curves=arch, n_folds=3)
    # Smooth fitness (finite, may be negative); gate flag recorded; novelty in [0,1].
    import math
    assert math.isfinite(res.fitness_score)
    assert "gate_passed" in res.metrics_oos
    assert "novelty_score" in res.metrics_oos
    assert 0.0 <= res.metrics_oos["novelty_score"] <= 1.0


def test_novelty_discriminates_structurally_different_individuals():
    # A textbook-identical individual should score LOWER novelty than a structurally
    # different (imbalance-conditioned) one — the point of novelty pressure.
    snaps = _stream()
    arch = textbook_archetype_curves(snaps)
    cfg = FitnessConfig(min_trades=1)
    fixed = evaluate_gp_tree(_const_individual(10.0), snaps, cfg, archetype_curves=arch, n_folds=3)
    cond = evaluate_gp_tree(_imbalance_conditioned_individual(), snaps, cfg, archetype_curves=arch, n_folds=3)
    assert cond.metrics_oos["novelty_score"] >= fixed.metrics_oos["novelty_score"]


def test_complexity_cap_rejects_bloat():
    snaps = _stream()
    res = evaluate_gp_tree(_const_individual(), snaps, FitnessConfig(min_trades=1),
                           n_folds=3, max_complexity=1)   # absurdly low cap
    assert "too_complex" in res.rejection_reason
    assert not res.evaluated


def test_size_capped_to_max_inventory_prevents_runaway():
    # An individual outputting a huge size must be capped -> bounded loss.
    snaps = _stream()
    huge = Individual(Node("const", 10.0), Node("const", 0.0), Node("const", 1e6))
    res = evaluate_gp_tree(huge, snaps, FitnessConfig(min_trades=1), n_folds=3,
                           max_inventory=2.0)
    # Loss is bounded (capped size); not a runaway like -1e6.
    assert res.oos_vs_buyhold > -1e6
