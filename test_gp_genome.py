"""Tests for the GP genome (slate_core.dex.evolution.gp.genome)."""
import random

from slate_core.dex.evolution.gp import (
    FEATURES, FUNCTIONS, Node, Individual, random_individual, ramped_half_and_half,
    policy_source, complexity, serialize, deserialize, node_to_source,
)
from slate_core.discovery.evolution.signal_sandbox import compile_function


def test_features_are_microstructure_not_textbook_ta():
    # The feature set must be microstructure (the point: search BEYOND textbook TA).
    assert "imbalance" in FEATURES and "bid_consumed" in FEATURES
    assert "queue_ahead_bid" in FEATURES and "vol_of_vol" in FEATURES
    assert "adv_recent" in FEATURES


def test_random_individual_compiles_in_sandbox():
    # Every generated tree must compile through the AST sandbox.
    rng = random.Random(0)
    from types import SimpleNamespace
    st = SimpleNamespace(**{f: 0.1 for f in FEATURES})
    for _ in range(20):
        ind = random_individual(rng, max_depth=4)
        fn = compile_function(policy_source(ind), "policy_fn")
        out = fn(st)
        assert isinstance(out, tuple) and len(out) == 3


def test_serialize_deserialize_roundtrip_preserves_source():
    rng = random.Random(1)
    ind = random_individual(rng, max_depth=4)
    rt = deserialize(serialize(ind))
    assert policy_source(rt) == policy_source(ind)


def test_complexity_is_positive_and_bounded_by_depth():
    rng = random.Random(2)
    for _ in range(20):
        ind = random_individual(rng, max_depth=3)
        assert complexity(ind) >= 3            # at least 3 root nodes
        assert complexity(ind) < 500


def test_generated_source_is_sandbox_safe():
    # The sandbox validates forbidden names via AST (attr/name nodes), not substring
    # (note "quit" is a substring of "equity" in state.equity_slope — a substring
    # check would false-positive). compile_function is the real validator.
    rng = random.Random(3)
    for _ in range(20):
        compile_function(policy_source(random_individual(rng, max_depth=4)), "policy_fn")


def test_ramped_half_and_half_produces_varied_depths():
    rng = random.Random(4)
    depths = set()
    for _ in range(40):
        ind = ramped_half_and_half(rng, max_depth=4)
        from slate_core.dex.evolution.gp.operators import _max_depth
        depths.add(max(_max_depth(r) for r in ind.roots()))
    assert len(depths) > 1   # ramped -> varied depths
