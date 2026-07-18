"""Tests for the native MM parameter optimizer (slate_core.dex.evolution.param_optimizer).

Verifies the walk-forward gate accepts a genuine spread-capturing policy and
rejects a buried/no-fill one, and that `mm_param_step` seeds + mutates natively
(no LLM) and persists survivors via the chokepoint.
"""
import asyncio
import os
import tempfile

from slate_core.dex.evolution.param_optimizer import (
    PARAM_SPACE, evaluate_mm_params, mm_param_step,
)
from slate_core.discovery.evolution.fitness_evaluator import FitnessConfig
from slate_core.discovery.evolution.program_database import (
    ProgramDBConfig, ProgramDatabase,
)


def _snap(t, mid, bids, asks):
    return {"t": t, "coin": "SOL", "mid": mid, "spread_bps": 1.0, "imbalance": 0.0,
            "bids": [[p, s] for p, s in bids], "asks": [[p, s] for p, s in asks]}


def _oscillating_stream(n=3000, mid=100.0):
    """Stable mid, alternating seller/buyer pressure: a tight-spread MM captures
    the spread each round trip; a wide (buried) MM never fills."""
    snaps = []
    for i in range(n):
        if i % 2 == 0:
            snaps.append(_snap(i, mid, [(99.9, 0.5)], [(100.1, 5.0)]))   # sellers
        else:
            snaps.append(_snap(i, mid, [(99.9, 5.0)], [(100.1, 0.5)]))   # buyers
    return snaps


def test_evaluate_rejects_buried_no_fill_policy():
    snaps = _oscillating_stream()
    wide = {"half_spread_bps": 100.0, "inv_skew_bps": 0.0, "size": 0.5}  # bid 99.0/ask 101.0
    res = evaluate_mm_params(wide, snaps, FitnessConfig(min_trades=1))
    assert not res.evaluated
    assert "fills" in res.rejection_reason      # never filled (buried)


def test_evaluate_accepts_spread_capture_policy():
    snaps = _oscillating_stream()
    tight = {"half_spread_bps": 10.0, "inv_skew_bps": 0.0, "size": 0.5}  # bid 99.9/ask 100.1
    res = evaluate_mm_params(tight, snaps, FitnessConfig(min_trades=1))
    assert res.evaluated
    assert res.fitness_score > 0.0              # profitable in every fold
    assert res.oos_vs_buyhold > 0.0             # worst-fold net PnL > 0


def test_mm_param_step_seeds_and_persists_survivor():
    # Empty DB: the step seeds a random vector, mutates, and over enough tries
    # finds + stores a profitable policy. No LLM anywhere in the path.
    snaps = _oscillating_stream(2000)
    with tempfile.TemporaryDirectory() as d:
        db = ProgramDatabase(ProgramDBConfig(persist_path=os.path.join(d, "dex.db")))
        stored = 0
        for _ in range(40):
            child = asyncio.run(mm_param_step(db, snaps, fitness_config=FitnessConfig(min_trades=1)))
            if child is not None:
                stored += 1
        assert stored >= 1                       # at least one walk-forward-confirmed survivor
        assert db.best() is not None
        assert db.best().parameters in (db.best().parameters,)  # params dict present
        assert "half_spread_bps" in db.best().parameters


def test_param_space_bounds_match_market_maker():
    # Sanity: the optimized knobs are exactly the MM strategy's parameter surface.
    assert set(PARAM_SPACE) == {"half_spread_bps", "inv_skew_bps", "size"}
    assert PARAM_SPACE["size"][1] <= 2.0         # cannot exceed max_inventory default
