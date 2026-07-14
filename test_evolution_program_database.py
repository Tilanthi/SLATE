"""Tests for Phase 1 program database (niche.py + program_database.py)."""
from slate_core.discovery.evolution.niche import compute_niche


# ---------------------------------------------------------------------------
# Task 1.1: niche descriptor
# ---------------------------------------------------------------------------

def test_niche_from_edge_type_and_regime():
    meta = {"edge_type": "momentum", "volatility_regime": "high"}
    assert compute_niche(meta) == ("momentum", "high")


def test_niche_defaults_unknowns():
    assert compute_niche({}) == ("unknown", "unknown")
    assert compute_niche({"edge_type": "arbitrage"}) == ("arbitrage", "unknown")


def test_niche_normalizes_regime():
    meta = {"edge_type": "mean_reversion", "volatility_regime": "LOW"}
    assert compute_niche(meta) == ("mean_reversion", "low")


# ---------------------------------------------------------------------------
# Task 1.2: Program + ProgramDatabase.add (MAP-Elites elite + island pool)
# ---------------------------------------------------------------------------

from slate_core.discovery.evolution.program_database import (
    Program, ProgramDatabase, ProgramDBConfig,
)


def _prog(fitness, family="momentum", regime="high", cid="c"):
    return Program(candidate_id=cid, niche=(family, regime),
                   family=family, regime=regime,
                   fitness_score=fitness, source="seed")


def test_add_keeps_best_per_niche():
    db = ProgramDatabase(ProgramDBConfig())
    db.add(_prog(10.0, cid="a"))
    db.add(_prog(50.0, cid="b"))
    db.add(_prog(20.0, cid="c"))
    elite = db.elite(("momentum", "high"))
    assert elite.candidate_id == "b"
    assert elite.fitness_score == 50.0


def test_separate_niches_kept_separately():
    db = ProgramDatabase(ProgramDBConfig())
    db.add(_prog(5.0, family="momentum", regime="high", cid="m"))
    db.add(_prog(1.0, family="arbitrage", regime="low", cid="a"))
    assert db.elite(("momentum", "high")).candidate_id == "m"
    assert db.elite(("arbitrage", "low")).candidate_id == "a"


def test_island_pool_capped_and_evicts_worst():
    cfg = ProgramDBConfig(island_pool_size=3)
    db = ProgramDatabase(cfg)
    for i in range(5):
        db.add(_prog(float(i), cid=f"p{i}"))
    pool = db.island_pool()
    assert len(pool) == 3
    assert min(p.fitness_score for p in pool) >= 2.0  # two lowest (0, 1) evicted


# ---------------------------------------------------------------------------
# Task 1.3: sample() -> (parent, inspirations)
# ---------------------------------------------------------------------------

import random as _random


def test_sample_returns_parent_and_inspirations():
    db = ProgramDatabase(ProgramDBConfig(inspiration_count=2))
    db.add(_prog(10.0, family="momentum", regime="high", cid="m"))
    db.add(_prog(8.0, family="arbitrage", regime="low", cid="a"))
    db.add(_prog(6.0, family="mean_reversion", regime="mid", cid="r"))
    parent, inspirations = db.sample(rng=_random.Random(0))
    assert isinstance(parent, Program)
    assert len(inspirations) <= 2
    for insp in inspirations:
        assert insp.niche != parent.niche


def test_sample_is_deterministic_under_seed():
    db = ProgramDatabase(ProgramDBConfig(inspiration_count=2))
    for i, fam in enumerate(["momentum", "arbitrage", "mean_reversion", "breakout"]):
        db.add(_prog(float(10 - i), family=fam, regime="high", cid=fam))
    p1, i1 = db.sample(rng=_random.Random(42))
    p2, i2 = db.sample(rng=_random.Random(42))
    assert p1.candidate_id == p2.candidate_id
    assert [x.candidate_id for x in i1] == [x.candidate_id for x in i2]


def test_sample_empty_db_returns_none():
    db = ProgramDatabase(ProgramDBConfig())
    assert db.sample() == (None, [])


# ---------------------------------------------------------------------------
# Task 1.4: seed_from_discoveries
# ---------------------------------------------------------------------------

import sqlite3
import tempfile
import os


def _make_legacy_db(path):
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute("""CREATE TABLE perpetual_discoveries (
        id INTEGER PRIMARY KEY, strategy_name TEXT, edge_type TEXT,
        volatility_regime TEXT, total_profit_usdt REAL, vs_buy_hold_usdt REAL,
        sharpe_ratio REAL, beat_market INTEGER, passed_validation INTEGER,
        total_trades INTEGER, strategy_description TEXT)""")
    rows = [
        ("s1", "momentum", "high", 100.0, 50.0, 1.2, 1, 1, 30),
        ("s2", "arbitrage", "low", 80.0, 40.0, 1.1, 1, 1, 25),
        ("s3", "mean_reversion", "high", -20.0, -30.0, 0.3, 0, 0, 10),
    ]
    c.executemany(
        "INSERT INTO perpetual_discoveries (strategy_name, edge_type, volatility_regime, "
        "total_profit_usdt, vs_buy_hold_usdt, sharpe_ratio, beat_market, passed_validation, "
        "total_trades, strategy_description) VALUES (?,?,?,?,?,?,?,?,?,?)",
        [r + ("seed",) for r in rows],
    )
    conn.commit()
    conn.close()


def test_seed_from_discoveries_populates_niches():
    path = tempfile.mktemp(suffix=".db")
    _make_legacy_db(path)
    try:
        db = ProgramDatabase(ProgramDBConfig())
        n = db.seed_from_discoveries(path)
        assert n == 2  # only the 2 profitable/validated rows (s3 skipped: vs_buy_hold<0)
        assert db.elite(("momentum", "high")) is not None
        assert db.elite(("arbitrage", "low")) is not None
        assert db.elite(("mean_reversion", "high")) is None  # skipped
        assert db.elite(("momentum", "high")).fitness_score == 50.0
    finally:
        if os.path.exists(path):
            os.remove(path)


# ---------------------------------------------------------------------------
# Task 1.5: sqlite persistence
# ---------------------------------------------------------------------------

def test_persistence_roundtrip():
    path = tempfile.mktemp(suffix=".db")
    try:
        db = ProgramDatabase(ProgramDBConfig(persist_path=path))
        db.add(_prog(42.0, family="momentum", regime="high", cid="x"))
        db.add(_prog(7.0, family="arbitrage", regime="low", cid="y"))
        db.save()

        db2 = ProgramDatabase(ProgramDBConfig(persist_path=path))
        n = db2.load()
        assert n == 2
        assert db2.elite(("momentum", "high")).candidate_id == "x"
        assert db2.elite(("momentum", "high")).fitness_score == 42.0
        assert db2.elite(("arbitrage", "low")).candidate_id == "y"
    finally:
        if os.path.exists(path):
            os.remove(path)


# ---------------------------------------------------------------------------
# Unified write chokepoint (ASTRA §7.1): exactly one verified write path for
# real candidates, and gate-rejected (fitness_score == -inf) programs can NEVER
# become niche elites or reach disk. Pinned by regression so fiction (a stored
# candidate lacking objective real-data evidence) is structurally impossible.
# ---------------------------------------------------------------------------

def test_add_rejects_gate_rejected_candidate():
    """A -inf (gate-rejected) Program must not be placed as a niche elite, even
    on an empty niche. Without this the first reject wins the empty niche - the
    -inf-elite hole."""
    db = ProgramDatabase(ProgramDBConfig())
    placed = db.add(_prog(float("-inf"), cid="reject"))
    assert placed is False
    assert db.elite(("momentum", "high")) is None
    assert db.island_pool() == []


def test_add_returns_true_for_finite_fitness_seed():
    """add() stays permissive for finite-fitness programs (seeds/fixtures that
    pre-date the verification contract); only -inf is refused."""
    db = ProgramDatabase(ProgramDBConfig())
    assert db.add(_prog(10.0, cid="seed1")) is True
    assert db.elite(("momentum", "high")) is not None


def test_append_verified_requires_verification_block():
    db = ProgramDatabase(ProgramDBConfig())
    assert db.append_verified(_prog(10.0, cid="v1"), verification=None) is False
    assert db.append_verified(_prog(10.0, cid="v1"), verification={}) is False
    assert db.island_pool() == []


def test_append_verified_requires_gate_and_real_data_result():
    """A verification block missing the objective-evidence keys is rejected."""
    db = ProgramDatabase(ProgramDBConfig())
    assert db.append_verified(_prog(10.0, cid="v1"),
                              verification={"gate": "passed"}) is False
    assert db.append_verified(_prog(10.0, cid="v1"),
                              verification={"real_data_result": {"x": 1}}) is False


def test_append_verified_rejects_gate_rejected_even_with_verification():
    db = ProgramDatabase(ProgramDBConfig())
    ok = db.append_verified(
        _prog(float("-inf"), cid="r"),
        verification={"gate": "passed", "real_data_result": {"oos": 5}},
    )
    assert ok is False
    assert db.elite(("momentum", "high")) is None


def test_append_verified_places_and_stamps_verification():
    db = ProgramDatabase(ProgramDBConfig())
    block = {"gate": "passed_two_window",
             "evaluator": "evaluate_fitness_two_window",
             "program_hash": "abc123",
             "real_data_result": {"oos_vs_buyhold": 12.0, "n_trades_oos": 15}}
    ok = db.append_verified(_prog(10.0, cid="v1"), verification=block)
    assert ok is True
    elite = db.elite(("momentum", "high"))
    assert elite is not None and elite.candidate_id == "v1"
    assert elite.verification == block


def test_save_does_not_persist_gate_rejected():
    """Persistence is also a chokepoint: a -inf program can never reach disk."""
    path = tempfile.mktemp(suffix=".db")
    try:
        db = ProgramDatabase(ProgramDBConfig(persist_path=path))
        db.add(_prog(float("-inf"), cid="reject"))  # refused
        db.append_verified(
            _prog(7.0, family="arbitrage", regime="low", cid="ok"),
            verification={"gate": "passed", "real_data_result": {"oos": 7}},
        )
        db.save()
        db2 = ProgramDatabase(ProgramDBConfig(persist_path=path))
        n = db2.load()
        assert n == 1
        assert db2.elite(("arbitrage", "low")) is not None
        assert db2.elite(("momentum", "high")) is None
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_verification_roundtrips_through_persistence():
    path = tempfile.mktemp(suffix=".db")
    try:
        db = ProgramDatabase(ProgramDBConfig(persist_path=path))
        block = {"gate": "passed_two_window", "program_hash": "deadbeef",
                 "real_data_result": {"oos_vs_buyhold": 9.0}}
        db.append_verified(_prog(9.0, cid="v"), verification=block)
        db.save()
        db2 = ProgramDatabase(ProgramDBConfig(persist_path=path))
        db2.load()
        elite = db2.elite(("momentum", "high"))
        assert elite is not None
        assert elite.verification.get("gate") == "passed_two_window"
        assert elite.verification.get("program_hash") == "deadbeef"
    finally:
        if os.path.exists(path):
            os.remove(path)
