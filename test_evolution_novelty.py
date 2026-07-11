"""Tests for Phase 3 novelty (evolution/novelty.py) + Pareto archive method."""
import numpy as np

from slate_core.discovery.evolution.novelty import (
    equity_correlation, novelty_score,
)
from slate_core.discovery.evolution.program_database import Program, ProgramDatabase, ProgramDBConfig


def test_equity_correlation_identical_is_one():
    a = [1, 2, 3, 4, 5]
    assert round(equity_correlation(a, a), 6) == 1.0


def test_equity_correlation_inverse_is_minus_one():
    a = [1, 2, 3, 4, 5]
    b = [5, 4, 3, 2, 1]
    assert round(equity_correlation(a, b), 6) == -1.0


def test_equity_correlation_constant_returns_zero():
    assert equity_correlation([1, 1, 1, 1], [1, 2, 3, 4]) == 0.0


def test_novelty_score_zero_for_identical_to_population():
    cand = [1, 2, 3, 4, 5]
    pop = [[1, 2, 3, 4, 5]]
    assert novelty_score(cand, pop) < 1e-9      # ~0 (corrcoef float epsilon)


def test_novelty_score_high_for_uncorrelated():
    rng = np.random.RandomState(0)
    cand = rng.randn(50).tolist()
    pop = [rng.randn(50).tolist()]
    # random independent walks -> low abs correlation -> high novelty
    assert novelty_score(cand, pop) > 0.7


def test_pareto_archive_method_delegates():
    db = ProgramDatabase(ProgramDBConfig())
    db.add(Program(candidate_id="a", niche=("m", "h"), family="m", regime="h",
                   fitness_score=100, source="evolved",
                   metrics={"oos_vs_buyhold": 100, "sharpe_ratio": 1.0}))
    db.add(Program(candidate_id="b", niche=("m2", "h"), family="m2", regime="h",
                   fitness_score=50, source="evolved",
                   metrics={"oos_vs_buyhold": 50, "sharpe_ratio": 2.0}))
    front = db.pareto_archive([("oos_vs_buyhold", "max"), ("sharpe_ratio", "max")])
    ids = {p.candidate_id for p in front}
    assert ids == {"a", "b"}     # neither dominates the other
