"""Tests for the Phase 3 Pareto front (evolution/pareto.py)."""
from slate_core.discovery.evolution.pareto import pareto_front
from slate_core.discovery.evolution.program_database import Program


def _mp(cid, **metrics):
    return Program(candidate_id=cid, niche=("m", "h"), family="m", regime="h",
                   fitness_score=metrics.get("oos_vs_buyhold", 0.0),
                   source="evolved", metrics=metrics)


def test_pareto_front_returns_non_dominated():
    a = _mp("a", oos_vs_buyhold=100, sharpe_ratio=1.0)
    b = _mp("b", oos_vs_buyhold=50, sharpe_ratio=2.0)
    c = _mp("c", oos_vs_buyhold=80, sharpe_ratio=0.5)   # dominated by a
    front = pareto_front([a, b, c],
                         [("oos_vs_buyhold", "max"), ("sharpe_ratio", "max")])
    assert {p.candidate_id for p in front} == {"a", "b"}
    assert "c" not in {p.candidate_id for p in front}


def test_pareto_single_objective_keeps_max():
    a = _mp("a", oos_vs_buyhold=10)
    b = _mp("b", oos_vs_buyhold=30)
    c = _mp("c", oos_vs_buyhold=20)
    front = pareto_front([a, b, c], [("oos_vs_buyhold", "max")])
    assert {p.candidate_id for p in front} == {"b"}


def test_pareto_min_objective_keeps_lowest():
    a = _mp("a", max_drawdown_pct=0.2)
    b = _mp("b", max_drawdown_pct=0.1)
    front = pareto_front([a, b], [("max_drawdown_pct", "min")])
    assert {p.candidate_id for p in front} == {"b"}


def test_pareto_empty_input():
    assert pareto_front([], [("oos_vs_buyhold", "max")]) == []
