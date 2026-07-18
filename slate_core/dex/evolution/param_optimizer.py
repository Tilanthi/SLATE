"""Native (non-LLM) parameter optimizer for DEX market-making.

Replaces the GLM-guided `quote_fn` evolution with a derivative-free search over
the (half_spread_bps, inv_skew_bps, size) parameter vector, evaluated by the
tick/L2 backtester (`mm_tick_backtester`). Variation comes from SLATE's own GA
operators (`variation.py`); selection/storage reuses the ProgramDatabase
MAP-Elites infrastructure. No LLM is called anywhere in this path.

Objective: walk-forward over the L2 snapshots — the candidate is backtested on
N disjoint OOS windows and must be net-profitable in EVERY window (mirrors the
`evaluate_dex_mm_fitness` strict gate, `bench_buyhold=False`: an MM is an
absolute-profit strategy, rebates net of adverse selection + fees).
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import statistics
import uuid
from typing import Any, Dict, List, Optional

from slate_core.discovery.evolution.fitness_evaluator import FitnessConfig, FitnessResult
from slate_core.discovery.evolution.program_database import Program, ProgramDatabase
from slate_core.discovery.evolution.variation import (
    clamp, gaussian_mutate, random_params, uniform_crossover,
)
from slate_core.discovery.evolution.verdict_log import (
    VerdictLogger, verdict_from_fitness_result,
)
from slate_core.dex.backtester.mm_tick_backtester import MMPolicy, backtest_mm
from slate_core.dex.backtester.economics import HLFeeSchedule

logger = logging.getLogger(__name__)

# The parameter surface the optimizer searches (bounds match MarketMakerStrategy).
PARAM_SPACE = {
    "half_spread_bps": (1.0, 500.0),
    "inv_skew_bps": (-200.0, 200.0),
    "size": (0.01, 2.0),
}

WALKFORWARD_FOLDS = 5
MIN_SNAPS_PER_FOLD = 200        # ~200s of L2 at 1s cadence

# Baseline MM policies to seed an empty population from (span tight→wide, with
# and without inventory skew). Starting from these — not random points in a wide
# 3D space — is what lets the GA refine into the niche that actually fills.
MM_SEED_PARAMS = [
    {"half_spread_bps": 10.0, "inv_skew_bps": 2.0, "size": 0.5},    # tight (strategy default)
    {"half_spread_bps": 5.0, "inv_skew_bps": 0.0, "size": 0.3},     # ultra-tight
    {"half_spread_bps": 30.0, "inv_skew_bps": 10.0, "size": 1.0},   # wider, skew-on
    {"half_spread_bps": 50.0, "inv_skew_bps": 20.0, "size": 1.0},   # wide
]

_opt_logger = VerdictLogger("slate_core/dex_verdicts.jsonl")


def _hash(params: Dict[str, float]) -> str:
    raw = ",".join(f"{k}={float(params[k]):.6f}" for k in sorted(params))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def mm_vol_regime(snaps: List[dict]) -> str:
    """Classify the snapshot stream's realized volatility (low/med/high)."""
    if len(snaps) < 2:
        return "unknown"
    mids = [float(s["mid"]) for s in snaps]
    rets = [(mids[i] / mids[i - 1] - 1.0) for i in range(1, len(mids)) if mids[i - 1] > 0]
    if not rets:
        return "unknown"
    rv = statistics.pstdev(rets) * 1e4  # bps per snapshot
    if rv < 5.0:
        return "low_vol"
    if rv < 15.0:
        return "med_vol"
    return "high_vol"


def _snap_oos_windows(snaps: List[dict], n_folds: int = WALKFORWARD_FOLDS) -> List[List[dict]]:
    """Disjoint tail OOS windows (anchored walk-forward): fold i tests on block i+1."""
    n = len(snaps)
    nb = n_folds + 1
    bounds = [int(n * k / nb) for k in range(nb + 1)]
    windows = []
    for i in range(n_folds):
        oos = snaps[bounds[i + 1]: bounds[i + 2]]
        if len(oos) >= MIN_SNAPS_PER_FOLD:
            windows.append(oos)
    return windows


def evaluate_mm_params(params: Dict[str, float], snaps: List[dict],
                       config: Optional[FitnessConfig] = None,
                       n_folds: int = WALKFORWARD_FOLDS,
                       max_inventory: float = 2.0,
                       schedule: Optional[HLFeeSchedule] = None) -> FitnessResult:
    """Walk-forward tick-backtest fitness for an MM parameter vector.

    Backtests the policy on each disjoint OOS window; requires absolute net
    profit and min activity in EVERY window. Returns a FitnessResult where
    oos_vs_buyhold = worst-fold net PnL, is_vs_buyhold = median-fold net PnL
    (so overfit_gap captures fold dispersion — a robustness signal).

    `schedule` defaults to the brutal retail fee (maker +0.015%). Pass a
    rebate-tier schedule (maker < 0) to test the maker-rebate hypothesis —
    an unverified assumption that must be stated explicitly.
    """
    cfg = config or FitnessConfig()
    regime = mm_vol_regime(snaps)
    base = FitnessResult(
        evaluated=False, fitness_score=float("-inf"),
        oos_vs_buyhold=0.0, is_vs_buyhold=0.0, overfit_gap=0.0,
        overfit_penalty=0.0, n_trades_is=0, n_trades_oos=0,
        validation_score=1.0, candidate_id="",
        family_label="market_maker", regime_label=regime,
    )
    policy = MMPolicy(
        half_spread_bps=float(params["half_spread_bps"]),
        inv_skew_bps=float(params["inv_skew_bps"]),
        size=float(params["size"]),
    )
    windows = _snap_oos_windows(snaps, n_folds)
    if len(windows) < 3:
        base.rejection_reason = f"too_few_folds ({len(windows)})"
        return base

    pnls: List[float] = []
    fills: List[int] = []
    acts: List[float] = []
    adv: List[float] = []
    for w in windows:
        r = backtest_mm(w, policy, schedule=schedule, max_inventory=max_inventory)
        pnls.append(r.total_pnl)
        fills.append(r.maker_fills)
        acts.append(r.bars_in_market / max(1, r.n_snapshots))
        adv.append(r.adverse_selection_cost)

    base.is_vs_buyhold = statistics.median(pnls)
    base.oos_vs_buyhold = min(pnls)                 # conservative: worst fold
    base.n_trades_oos = min(fills)
    base.oos_activity = statistics.median(acts)
    base.overfit_gap = max(0.0, base.is_vs_buyhold - base.oos_vs_buyhold)
    base.overfit_penalty = base.overfit_gap * cfg.overfit_penalty_weight
    exposure = (max(0.0, min(1.0, base.oos_activity / cfg.activity_floor))
                if cfg.activity_floor > 0 else 1.0)
    base.exposure_factor = exposure
    candidate_fitness = base.oos_vs_buyhold * exposure - base.overfit_penalty
    base.metrics_oos = {"fold_pnls": pnls, "fold_fills": fills,
                        "adverse_selection_cost": sum(adv)}

    reasons: List[str] = []
    if cfg.require_absolute_oos_profit:
        for i, p in enumerate(pnls):
            if p <= 0:
                reasons.append(f"fold{i}_pnl={p:.2f}<=0")
    for i, f in enumerate(fills):
        if f < cfg.min_trades:
            reasons.append(f"fold{i}_fills={f}<{cfg.min_trades}")
    if candidate_fitness < cfg.min_fitness:
        reasons.append(f"fitness={candidate_fitness:.2f}<{cfg.min_fitness}")
    if reasons:
        base.rejection_reason = "; ".join(reasons)
        return base
    base.evaluated = True
    base.fitness_score = candidate_fitness
    return base


async def mm_param_step(db: ProgramDatabase, snaps: List[dict],
                        config: Optional[Any] = None,
                        fitness_config: Optional[FitnessConfig] = None,
                        schedule: Optional[HLFeeSchedule] = None,
                        rng=None) -> Optional[Program]:
    """One native optimization step: sample parent -> mutate -> evaluate -> store.

    No LLM. Parent comes from the ProgramDatabase (MAP-Elites `sample()`);
    variation is Gaussian mutation (+ occasional crossover with an inspiration).
    Survivors are persisted via the `append_verified` chokepoint. Auto-seeds the
    baseline MM policies if the population is empty.
    """
    import random as _r
    r = rng or _r.Random()
    fcfg = fitness_config or FitnessConfig.exploration()

    parent, inspirations = db.sample()
    # Seed if there is no parameter-bearing elite to mutate (empty DB, or only
    # legacy code-bearing programs from the old LLM path).
    if parent is None or not parent.parameters:
        has_param_elite = any(
            (e := db.elite(n)) is not None and e.parameters
            for n in db.occupied_niches()
        )
        if not has_param_elite:
            await seed_mm_population(db, snaps, fcfg)
        parent, inspirations = db.sample()

    if parent is not None and parent.parameters:
        params = dict(parent.parameters)
        if inspirations and inspirations[0].parameters and r.random() < 0.3:
            params = uniform_crossover(params, inspirations[0].parameters, rng=r)
        params = gaussian_mutate(params, PARAM_SPACE, sigma=0.10, rng=r)
    else:
        params = random_params(PARAM_SPACE, rng=r)     # fallback (shouldn't usually trigger)
    params = clamp(params, PARAM_SPACE)

    candidate_id = f"dexmmopt:{uuid.uuid4().hex[:8]}"
    program_hash = _hash(params)
    parent_id = parent.candidate_id if parent is not None else "seed"

    loop = asyncio.get_running_loop()
    fitness = await loop.run_in_executor(
        None, lambda: evaluate_mm_params(params, snaps, fcfg, schedule=schedule))

    _opt_logger.log(verdict_from_fitness_result(
        fitness, candidate_id=candidate_id, parent_id=parent_id, program_hash=program_hash))

    if not fitness.evaluated:
        return None

    metrics = {
        "oos_pnl": fitness.oos_vs_buyhold, "is_pnl": fitness.is_vs_buyhold,
        "overfit_gap": fitness.overfit_gap, "n_trades_oos": fitness.n_trades_oos,
        "adverse_selection": (fitness.metrics_oos or {}).get("adverse_selection_cost", 0.0),
        "params": params,
    }
    child = Program(
        candidate_id=candidate_id,
        niche=("market_maker", fitness.regime_label or "unknown"),
        family="market_maker", regime=fitness.regime_label or "unknown",
        fitness_score=fitness.fitness_score, source="param_optimized",
        parameters=params, code=None, metrics=metrics,
        parent_id=parent_id, generation=(getattr(parent, "generation", 0) or 0) + 1,
    )
    verification = {
        "gate": "mm_param_walkforward_absolute_profit",
        "evaluator": "evaluate_mm_params (tick/L2, no LLM)",
        "program_hash": program_hash,
        "real_data_result": metrics,
    }
    if db.append_verified(child, verification=verification):
        return child
    return None


async def seed_mm_population(db: ProgramDatabase, snaps: List[dict],
                             fitness_config: Optional[FitnessConfig] = None,
                             schedule: Optional[HLFeeSchedule] = None) -> int:
    """Seed the baseline MM policies into an empty population.

    Evaluates each seed on the L2 stream and stores those that clear the
    walk-forward gate as starting elites. Returns the number stored.
    """
    fcfg = fitness_config or FitnessConfig.exploration()
    stored = 0
    loop = asyncio.get_running_loop()
    for params in MM_SEED_PARAMS:
        params = clamp(params, PARAM_SPACE)
        fit = await loop.run_in_executor(
            None, lambda p=params: evaluate_mm_params(p, snaps, fcfg, schedule=schedule))
        cid = f"dexmmseed:{uuid.uuid4().hex[:8]}"
        _opt_logger.log(verdict_from_fitness_result(
            fit, candidate_id=cid, parent_id="seed", program_hash=_hash(params)))
        if not fit.evaluated:
            continue
        prog = Program(
            candidate_id=cid,
            niche=("market_maker", fit.regime_label or "unknown"),
            family="market_maker", regime=fit.regime_label or "unknown",
            fitness_score=fit.fitness_score, source="seed",
            parameters=params, code=None,
            metrics={"oos_pnl": fit.oos_vs_buyhold, "is_pnl": fit.is_vs_buyhold,
                     "overfit_gap": fit.overfit_gap, "n_trades_oos": fit.n_trades_oos,
                     "params": params},
            parent_id="seed", generation=0,
        )
        if db.append_verified(prog, verification={
                "gate": "mm_param_walkforward_absolute_profit",
                "evaluator": "seed_mm_population (tick/L2, no LLM)",
                "program_hash": _hash(params),
                "real_data_result": prog.metrics}):
            stored += 1
    return stored


__all__ = ["PARAM_SPACE", "MM_SEED_PARAMS", "evaluate_mm_params",
           "mm_param_step", "seed_mm_population", "mm_vol_regime"]
