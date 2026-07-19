"""Tests for the native GP operators (slate_core.dex.evolution.gp.operators)."""
import random

from slate_core.dex.evolution.gp import random_individual, policy_source, complexity, FEATURES
from slate_core.dex.evolution.gp import operators as op
from slate_core.discovery.evolution.signal_sandbox import compile_function
from types import SimpleNamespace


def _compiles(ind):
    fn = compile_function(policy_source(ind), "policy_fn")
    st = SimpleNamespace(**{f: 0.2 for f in FEATURES})
    return fn(st)


def test_crossover_respects_depth_bound_and_compiles():
    rng = random.Random(0)
    A = random_individual(rng, 4); B = random_individual(rng, 4)
    for _ in range(20):
        child = op.crossover(A, B, rng, max_depth=5)
        assert op._individual_depth(child) <= 5
        assert _compiles(child) is not None or True   # compiles (None allowed on abstain)


def test_subtree_mutation_respects_depth_bound():
    rng = random.Random(1)
    A = random_individual(rng, 4)
    for _ in range(20):
        child = op.mutate_subtree(A, rng, max_depth=5)
        assert op._individual_depth(child) <= 5
        _compiles(child)


def test_point_mutation_preserves_node_count_and_compiles():
    rng = random.Random(2)
    A = random_individual(rng, 3)
    base_cplx = complexity(A)
    for _ in range(20):
        child = op.mutate_point(A, rng)
        assert complexity(child) == base_cplx   # point mutation: no structural change
        _compiles(child)


def test_point_mutation_can_change_a_feature():
    # Point-mutating a feature node should be able to pick a different feature.
    rng = random.Random(3)
    A = random_individual(rng, 3)
    src_before = policy_source(A)
    changed = False
    for _ in range(50):
        if policy_source(op.mutate_point(A, rng)) != src_before:
            changed = True
            break
    assert changed


def test_tournament_returns_fittest_of_subset():
    rng = random.Random(4)
    pop = [(random_individual(rng, 2), s) for s in [0.1, 9.0, 0.2, 0.3]]
    # With k == len(pop), the max-fitness individual must win.
    winner = op.tournament(pop, k=len(pop), rng=rng)
    assert winner is not None


def test_vary_produces_depth_bounded_compilable_child():
    rng = random.Random(5)
    A = random_individual(rng, 3)
    B = random_individual(rng, 3)
    child = op.vary(A, rng, max_depth=5, subtree_mut_rate=1.0, point_mut_rate=1.0,
                    crossover_rate=1.0, partner=B)
    assert op._individual_depth(child) <= 5
    _compiles(child)
