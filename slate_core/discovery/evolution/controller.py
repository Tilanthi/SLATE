"""Async evolution controller (Phase 5).

Ties the whole loop together: sample parent + inspirations -> build prompt ->
LLM proposes a diff -> apply_diff + sandbox-compile -> two-window fitness
evaluation -> add the child Program to the database. This is the AlphaEvolve
controller primitive, one mutation per call.

Async so multiple steps can run concurrently (LLM call + backtest run in a
thread executor, keeping the event loop free). Throughput-oriented, mirroring
AlphaEvolve's distributed pipeline design.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Optional

from slate_core.discovery.evolution.evolvable_strategy import BASE_SIGNAL_CODE, apply_diff, extract_code_block
from slate_core.discovery.evolution.fitness_evaluator import (
    FitnessConfig, evaluate_fitness_two_window,
)
from slate_core.discovery.evolution.llm_pool import LLMPool
from slate_core.discovery.evolution.program_database import Program, ProgramDatabase
from slate_core.discovery.evolution.prompt_sampler import PromptSampler, PromptObjective
from slate_core.discovery.evolution.signal_sandbox import compile_signal

logger = logging.getLogger(__name__)


@dataclass
class EvolutionConfig:
    edge_type_default: str = "momentum"
    regime_default: str = "unknown"


def _seed_parent(config: EvolutionConfig) -> Program:
    return Program(
        candidate_id="seed:base",
        niche=(config.edge_type_default, config.regime_default),
        family=config.edge_type_default, regime=config.regime_default,
        fitness_score=0.0, source="seed", code=BASE_SIGNAL_CODE,
    )


async def evolution_step(
    db: ProgramDatabase,
    sampler: PromptSampler,
    pool: LLMPool,
    df,
    config: Optional[EvolutionConfig] = None,
    fitness_config: Optional[FitnessConfig] = None,
    objective: Optional[PromptObjective] = None,
) -> Optional[Program]:
    """Run ONE evolution step. Returns the new Program, or None if the proposed
    code failed to compile (the candidate is simply skipped)."""
    cfg = config or EvolutionConfig()
    loop = asyncio.get_running_loop()

    parent, inspirations = db.sample()
    parent_prog = parent if parent is not None else _seed_parent(cfg)
    parent_code = parent_prog.code or BASE_SIGNAL_CODE

    prompt = sampler.build(parent_prog, inspirations, objective)
    diff = await loop.run_in_executor(None, lambda: pool.generate(prompt, tier="auto"))
    diff = extract_code_block(diff or "")   # strip markdown fences from live models

    try:
        new_code = apply_diff(parent_code, diff or "")
        fn = compile_signal(new_code)
    except Exception as exc:  # noqa: BLE001 - bad code => skip this candidate
        logger.info("candidate rejected at compile: %s", str(exc)[:120])
        return None

    edge_type = parent_prog.family or cfg.edge_type_default
    candidate_id = f"evo:{uuid.uuid4().hex[:8]}"

    fitness = await loop.run_in_executor(
        None,
        lambda: evaluate_fitness_two_window(fn, {}, df, edge_type=edge_type,
                                            config=fitness_config,
                                            candidate_id=candidate_id),
    )

    metrics = {
        "oos_vs_buyhold": fitness.oos_vs_buyhold,
        "is_vs_buyhold": fitness.is_vs_buyhold,
        "overfit_gap": fitness.overfit_gap,
        "overfit_penalty": fitness.overfit_penalty,
        "total_trades": fitness.n_trades_oos,
        "stability": max(0.0, 1.0 / (1.0 + fitness.overfit_gap)) if fitness.overfit_gap else 1.0,
    }
    niche = (parent_prog.family or cfg.edge_type_default,
             parent_prog.regime or cfg.regime_default)
    child = Program(
        candidate_id=candidate_id,
        niche=niche,
        family=niche[0],
        regime=niche[1],
        fitness_score=fitness.fitness_score,
        source="evolved",
        code=new_code,
        metrics=metrics,
        parent_id=parent_prog.candidate_id,
        generation=getattr(parent_prog, "generation", 0) + 1,
    )
    db.add(child)
    return child


async def run_evolution(db, sampler, pool, df, n_steps: int = 10, **kwargs):
    """Run n_steps evolution steps; return the list of produced Programs."""
    produced = []
    for _ in range(n_steps):
        prog = await evolution_step(db, sampler, pool, df, **kwargs)
        if prog is not None:
            produced.append(prog)
    return produced
