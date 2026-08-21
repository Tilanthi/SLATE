"""Native (LLM-free) GP evolution loop for DEX market-making.

Samples a parent tree from the ProgramDatabase, varies it via native GP operators
(subtree crossover/mutation + point mutation), evaluates structure-level fitness
on the tick/L2 backtester (walk-forward + novelty), and stores survivors via the
`append_verified` chokepoint. No LLM anywhere in this path.
"""
from __future__ import annotations

import asyncio
import logging
import random
import uuid
from typing import List, Optional, Sequence

from slate_core.discovery.evolution.fitness_evaluator import FitnessConfig
from slate_core.discovery.evolution.program_database import Program, ProgramDatabase
from slate_core.discovery.evolution.verdict_log import VerdictLogger, verdict_from_fitness_result
from slate_core.dex.backtester.economics import HLFeeSchedule
from slate_core.dex.evolution.gp.genome import (
    Individual, complexity, deserialize, individual_hash, policy_source,
    ramped_half_and_half, serialize,
)
from slate_core.dex.evolution.gp.operators import vary
from slate_core.dex.evolution.gp.fitness import evaluate_gp_tree
from slate_core.config.paths import CORE_ROOT

logger = logging.getLogger(__name__)
_gp_logger = VerdictLogger(f"{CORE_ROOT}/dex_verdicts.jsonl")


def _has_gp_elite(db: ProgramDatabase) -> bool:
    return any(
        (e := db.elite(n)) is not None and "half" in (e.parameters or {})
        for n in db.occupied_niches()
    )


def _try_deserialize(prog: Optional[Program]) -> Optional[Individual]:
    if prog is None or not prog.parameters or "half" not in prog.parameters:
        return None
    try:
        return deserialize(prog.parameters)
    except Exception:  # noqa: BLE001
        return None


async def seed_gp_population(db: ProgramDatabase, snaps: Sequence[dict],
                             archetype_curves=None, fitness_config=None,
                             schedule=None, max_complexity: int = 400,
                             n_seed: int = 12) -> int:
    """Seed ramped-half-and-half individuals; store those that clear the gate."""
    fcfg = fitness_config or FitnessConfig.exploration()
    rng = random.Random()
    loop = asyncio.get_running_loop()
    stored = 0
    for _ in range(n_seed):
        ind = ramped_half_and_half(rng, max_depth=4)
        fit = await loop.run_in_executor(
            None, lambda i=ind: evaluate_gp_tree(i, snaps, fcfg,
                                                 archetype_curves=archetype_curves,
                                                 schedule=schedule, max_complexity=max_complexity))
        h = individual_hash(ind)
        cid = f"dexgpmseed:{uuid.uuid4().hex[:8]}"
        _gp_logger.log(verdict_from_fitness_result(fit, candidate_id=cid,
                                                   parent_id="seed", program_hash=h))
        metrics = {"oos_pnl": fit.oos_vs_buyhold,
                   "novelty": (fit.metrics_oos or {}).get("novelty_score", 0.0),
                   "complexity": complexity(ind), "overfit_gap": fit.overfit_gap,
                   "n_trades_oos": fit.n_trades_oos,
                   "gate_passed": bool(fit.evaluated)}
        prog = Program(
            candidate_id=cid, niche=("market_maker_gp", fit.regime_label or "unknown"),
            family="market_maker_gp", regime=fit.regime_label or "unknown",
            fitness_score=fit.fitness_score, source="seed", code=policy_source(ind),
            parameters=serialize(ind), metrics=metrics, parent_id="seed", generation=0)
        if db.add(prog):
            stored += 1
    return stored


async def gp_evolution_step(db: ProgramDatabase, snaps: Sequence[dict],
                            archetype_curves=None, fitness_config=None,
                            schedule: Optional[HLFeeSchedule] = None,
                            rng=None, max_complexity: int = 400) -> Optional[Program]:
    """One native GP step: sample parent -> vary -> evaluate -> store. No LLM."""
    r = rng or random.Random()
    fcfg = fitness_config or FitnessConfig.exploration()

    parent_prog, inspirations = db.sample()
    parent_ind = _try_deserialize(parent_prog)
    if parent_ind is None and not _has_gp_elite(db):
        await seed_gp_population(db, snaps, archetype_curves, fcfg, schedule, max_complexity)
        parent_prog, inspirations = db.sample()
        parent_ind = _try_deserialize(parent_prog)

    if parent_ind is not None:
        partner = None
        if r.random() < 0.3:
            partner = _try_deserialize(inspirations[0]) if inspirations else None
        child = vary(parent_ind, r, max_depth=5, subtree_mut_rate=0.5,
                     point_mut_rate=0.3, crossover_rate=0.3 if partner else 0.0,
                     partner=partner)
    else:
        child = ramped_half_and_half(r, max_depth=4)

    candidate_id = f"dexgpmm:{uuid.uuid4().hex[:8]}"
    program_hash = individual_hash(child)
    parent_id = parent_prog.candidate_id if parent_prog is not None else "seed"

    loop = asyncio.get_running_loop()
    fit = await loop.run_in_executor(
        None, lambda: evaluate_gp_tree(child, snaps, fcfg,
                                       archetype_curves=archetype_curves,
                                       schedule=schedule, max_complexity=max_complexity))
    _gp_logger.log(verdict_from_fitness_result(
        fit, candidate_id=candidate_id, parent_id=parent_id, program_hash=program_hash))

    metrics = {
        "oos_pnl": fit.oos_vs_buyhold,
        "novelty": (fit.metrics_oos or {}).get("novelty_score", 0.0),
        "complexity": complexity(child), "overfit_gap": fit.overfit_gap,
        "n_trades_oos": fit.n_trades_oos,
        "gate_passed": bool(fit.evaluated),   # deployable marker (strict gate)
    }
    prog = Program(
        candidate_id=candidate_id,
        niche=("market_maker_gp", fit.regime_label or "unknown"),
        family="market_maker_gp", regime=fit.regime_label or "unknown",
        fitness_score=fit.fitness_score, source="gp",      # smooth search_score
        code=policy_source(child), parameters=serialize(child), metrics=metrics,
        parent_id=parent_id, generation=(getattr(parent_prog, "generation", 0) or 0) + 1,
    )
    # Evolve on the SMOOTH fitness (db.add places finite-fitness via MAP-Elites,
    # accumulating a population to climb). The strict gate is recorded as
    # metrics["gate_passed"] — the deployment bar, not the search gradient.
    if db.add(prog):
        return prog
    return None


__all__ = ["gp_evolution_step", "seed_gp_population"]
