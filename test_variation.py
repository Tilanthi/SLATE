"""Tests for native variation operators (slate_core.discovery.evolution.variation)."""
import random

from slate_core.discovery.evolution.variation import (
    clamp, gaussian_mutate, uniform_crossover, tournament_select, random_params,
    params_equal,
)

BOUNDS = {"half_spread_bps": (1.0, 500.0), "inv_skew_bps": (-200.0, 200.0), "size": (0.01, 2.0)}


def test_clamp_respects_bounds():
    out = clamp({"half_spread_bps": -5.0, "inv_skew_bps": 999.0, "size": 0.5}, BOUNDS)
    assert out == {"half_spread_bps": 1.0, "inv_skew_bps": 200.0, "size": 0.5}


def test_gaussian_mutate_stays_in_bounds():
    rng = random.Random(0)
    p = {"half_spread_bps": 250.0, "inv_skew_bps": 0.0, "size": 1.0}
    for _ in range(200):
        m = gaussian_mutate(p, BOUNDS, sigma=0.5, rng=rng)
        for k, (lo, hi) in BOUNDS.items():
            assert lo <= m[k] <= hi


def test_gaussian_mutate_changes_something():
    rng = random.Random(1)
    p = {"half_spread_bps": 250.0, "inv_skew_bps": 0.0, "size": 1.0}
    m = gaussian_mutate(p, BOUNDS, sigma=0.2, rng=rng)
    assert not params_equal(p, m, tol=1e-6)


def test_uniform_crossover_mixes_genes():
    rng = random.Random(2)
    p1 = {"half_spread_bps": 10.0, "inv_skew_bps": 0.0, "size": 0.5}
    p2 = {"half_spread_bps": 200.0, "inv_skew_bps": 100.0, "size": 1.5}
    child = uniform_crossover(p1, p2, rng=rng)
    for k in p1:
        assert child[k] in (p1[k], p2[k])       # each gene is from one parent


class _Prog:
    def __init__(self, fit):
        self.fitness_score = fit


def test_tournament_select_picks_fittest_of_subset():
    rng = random.Random(3)
    pop = [_Prog(f) for f in [0.1, 5.0, 0.2, 0.3, 0.4]]
    # With k == len(pop), the global best must win.
    assert tournament_select(pop, k=len(pop), rng=rng).fitness_score == 5.0


def test_random_params_in_bounds():
    rng = random.Random(4)
    for _ in range(100):
        p = random_params(BOUNDS, rng=rng)
        for k, (lo, hi) in BOUNDS.items():
            assert lo <= p[k] <= hi


# --- Verified HL fee schedule (economics.py) ---
from slate_core.dex.backtester.economics import (
    hl_perp_fee_schedule, HL_PERP_FEE_TIERS, HL_MAKER_REBATE_TIERS,
)


def test_hl_retail_fee_is_positive_maker_cost():
    s = hl_perp_fee_schedule()                       # defaults: retail
    assert s.taker == 0.00045 and s.maker == 0.00015  # +0.045% / +0.015% (costs)


def test_hl_maker_fee_reaches_zero_at_volume_tier4():
    s = hl_perp_fee_schedule(volume_14d_usd=600_000_000)   # >$500M tier 4
    assert s.maker == 0.0                                   # maker free at scale
    assert 0 < s.taker < 0.00045


def test_hl_rebate_tier_overrides_maker_negative():
    # Whale-gated rebate tier (>0.5% of venue maker volume) -> negative maker.
    s = hl_perp_fee_schedule(maker_share_of_venue=0.006)
    assert s.maker == -0.00001                              # -0.001% rebate
    s3 = hl_perp_fee_schedule(maker_share_of_venue=0.04)    # >3.0% -> tier 3
    assert s3.maker == -0.00003                             # -0.003%
