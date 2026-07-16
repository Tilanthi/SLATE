"""Tests for the AMM LP module (amm_math + lp_backtester + pool_data)."""
import math
import pandas as pd
import numpy as np

from slate_core.amm.amm_math import (
    price_to_tick, tick_to_price, impermanent_loss,
    amounts_for_liquidity, liquidity_for_amounts, in_range,
)
from slate_core.amm.lp_backtester import LPBacktester, LPBacktestConfig


# ---- amm_math ----

def test_tick_price_roundtrip():
    for price in [0.99, 1.0, 1.01, 50.0, 200.0]:
        tick = price_to_tick(price)
        recovered = tick_to_price(tick)
        assert abs(recovered - price) / price < 0.01  # <1% rounding


def test_il_zero_at_no_change():
    assert abs(impermanent_loss(1.0)) < 1e-9


def test_il_small_for_stablecoin_move():
    """A 1% price move (typical stablecoin) should have tiny IL."""
    il = impermanent_loss(1.01)
    assert -0.001 < il < 0.0  # <0.1% loss for 1% move


def test_il_grows_with_price_move():
    """A 2x price move should have ~5.7% IL."""
    il = impermanent_loss(2.0)
    assert -0.06 < il < -0.05


def test_in_range():
    assert in_range(1.0, 0.99, 1.01)
    assert not in_range(0.98, 0.99, 1.01)
    assert not in_range(1.02, 0.99, 1.01)


# ---- lp_backtester ----

def _flat_df(n=60, price=1.0):
    """Stablecoin-like: price barely moves around 1.0."""
    idx = pd.date_range("2026-01-01", periods=n, freq="1D")
    rng = np.random.RandomState(0)
    close = price + rng.normal(0, 0.0005, n)  # ±0.05% daily noise
    return pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999,
                         "close": close, "volume": [1000000] * n}, index=idx)


def _volatile_df(n=60, start=1.0):
    """A trending pair that moves 10%+ (high IL)."""
    idx = pd.date_range("2026-01-01", periods=n, freq="1D")
    close = start * np.cumprod(1 + np.random.RandomState(1).normal(0.002, 0.02, n))
    return pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99,
                         "close": close, "volume": [1000000] * n}, index=idx)


def test_flat_price_earns_fees_low_il():
    """LP in stablecoin-like data should earn fees with minimal IL."""
    df = _flat_df()
    always_enter = lambda bar: {"action": "ENTER", "range_bps": 20}
    r = LPBacktester(LPBacktestConfig(capital=10000)).backtest(always_enter, df)
    assert r.total_fees_earned > 0
    assert r.bars_in_range > 30            # mostly in range
    assert r.total_il > -50               # small IL


def test_out_of_range_stops_earning():
    """When price moves outside the tight range, fee earning stops."""
    df = _volatile_df(n=60, start=1.0)
    tight = lambda bar: {"action": "ENTER", "range_bps": 5}  # very tight ±5bps
    r = LPBacktester(LPBacktestConfig(capital=10000)).backtest(tight, df)
    # volatile data should have fewer in-range bars than flat data
    assert r.bars_in_range < 50


def test_hold_does_nothing():
    """A HOLD-only lp_fn should earn no fees."""
    df = _flat_df()
    hold = lambda bar: {"action": "HOLD"}
    r = LPBacktester(LPBacktestConfig(capital=10000)).backtest(hold, df)
    assert r.total_fees_earned == 0
    assert r.n_rebalances == 0


def test_apy_computed():
    df = _flat_df(n=365)
    always_enter = lambda bar: {"action": "ENTER", "range_bps": 20}
    r = LPBacktester(LPBacktestConfig(capital=10000)).backtest(always_enter, df)
    assert isinstance(r.apy, float)
    assert -1.0 < r.apy < 10.0  # sanity: APY between -100% and +1000%


# ---- lp_fitness ----

def test_lp_seeds_compile():
    from slate_core.amm.lp_seeds import LP_SEED_ARCHETYPES
    from slate_core.discovery.evolution.signal_sandbox import compile_function
    for _fam, code in LP_SEED_ARCHETYPES:
        compile_function(code, "lp_fn")


def test_lp_fitness_runs_and_labels():
    from slate_core.amm.lp_fitness import evaluate_lp_fitness
    from slate_core.discovery.evolution.fitness_evaluator import FitnessResult
    df = _flat_df(n=300)
    always_enter = lambda bar: {"action": "ENTER", "range_bps": 20}
    res = evaluate_lp_fitness(always_enter, df, candidate_id="lp1")
    assert isinstance(res, FitnessResult)
    assert res.family_label == "lp"


def test_lp_fitness_rejects_hold_only():
    from slate_core.amm.lp_fitness import evaluate_lp_fitness
    df = _flat_df(n=300)
    hold = lambda bar: {"action": "HOLD"}
    res = evaluate_lp_fitness(hold, df, candidate_id="hold")
    assert res.evaluated is False  # never enters → 0 rebalances → rejected


def test_lp_fitness_tight_range_profitable_on_flat():
    from slate_core.amm.lp_fitness import evaluate_lp_fitness
    from slate_core.discovery.evolution.fitness_evaluator import FitnessConfig
    df = _flat_df(n=300)
    tight = lambda bar: {"action": "ENTER", "range_bps": 10}
    # LP strategies legitimately have few rebalances (enter once, stay in)
    cfg = FitnessConfig(min_trades=1)
    res = evaluate_lp_fitness(tight, df, candidate_id="tight", config=cfg)
    # On flat stablecoin data, tight LP should be profitable (fees > IL)
    assert res.evaluated is True


def test_lp_pick_seed_parent_rotates():
    import random as _r
    from slate_core.amm.lp_seeds import lp_pick_seed_parent
    from slate_core.discovery.evolution.controller import EvolutionConfig
    rng = _r.Random(0)
    seen = {lp_pick_seed_parent(EvolutionConfig(), rng=rng).candidate_id for _ in range(30)}
    assert len(seen) >= 2
    assert all(cid.startswith("seed:lp:") for cid in seen)


# ---- lp_controller ----

def test_lp_step_stores_verified_candidate(monkeypatch):
    import asyncio
    from slate_core.discovery.evolution.program_database import Program, ProgramDatabase, ProgramDBConfig
    from slate_core.discovery.evolution.llm_client import MockLLMClient, LLMConfig
    from slate_core.discovery.evolution.llm_pool import LLMPool, LLMPoolConfig
    from slate_core.discovery.evolution.fitness_evaluator import FitnessResult
    from slate_core.amm.lp_controller import lp_evolution_step, LPPromptSampler

    def _passing(*a, **kw):
        return FitnessResult(evaluated=True, fitness_score=500.0,
                             oos_vs_buyhold=500.0, is_vs_buyhold=600.0,
                             overfit_gap=100.0, overfit_penalty=20.0,
                             n_trades_is=2, n_trades_oos=2, validation_score=1.0,
                             candidate_id="t", family_label="lp", regime_label="stablecoin")
    db = ProgramDatabase(ProgramDBConfig(persist_path=None))
    recorded = []
    monkeypatch.setattr("slate_core.amm.lp_controller.lp_eval_fitness_subprocess", _passing)
    monkeypatch.setattr("slate_core.amm.lp_controller.log_lp_verdict",
                        lambda v: recorded.append(v))
    canned = "def lp_fn(bar):\n    return {'action': 'ENTER', 'range_bps': 20}\n"

    def _mock_pool(canned=None):
        s = MockLLMClient(LLMConfig(), canned=canned) if canned else MockLLMClient(LLMConfig())
        f = MockLLMClient(LLMConfig(), canned=canned) if canned else MockLLMClient(LLMConfig())
        return LLMPool(s, f, LLMPoolConfig(), rng=__import__('random').Random(0))

    df = _flat_df(n=60)
    prog = asyncio.run(lp_evolution_step(
        db, LPPromptSampler(), _mock_pool(canned=canned), df))
    assert prog is not None
    assert prog.verification.get("gate") == "lp_passed_two_window"
    assert len(recorded) == 1 and recorded[0].death_stage == "passed"
