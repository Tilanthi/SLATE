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
import hashlib
import logging
import random
import uuid
from dataclasses import dataclass
from typing import Optional

from slate_core.discovery.evolution.evolvable_strategy import (
    BASE_SIGNAL_CODE, SEED_ARCHETYPES, apply_diff, extract_code_block,
)
from slate_core.discovery.evolution.fitness_evaluator import FitnessConfig
from slate_core.discovery.evolution.llm_pool import LLMPool
from slate_core.discovery.evolution.program_database import Program, ProgramDatabase
from slate_core.discovery.evolution.prompt_sampler import PromptSampler, PromptObjective
from slate_core.discovery.evolution.signal_sandbox import compile_signal
from slate_core.discovery.evolution.subprocess_eval import eval_fitness_subprocess
from slate_core.discovery.evolution.verdict_log import (
    CandidateVerdict, log_candidate_verdict, verdict_from_fitness_result,
)

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


# Module RNG for seed-archetype rotation when no caller injects one. Created at
# import so successive steps (each a fresh evolution_step call) draw different
# archetypes - the diversity pressure an empty population otherwise lacks.
_SEED_RNG = random.Random()


def pick_seed_parent(config: EvolutionConfig,
                     rng: Optional[random.Random] = None) -> Program:
    """Parent for an EMPTY population: a randomly-rotated SEED archetype, not
    always BASE_SIGNAL_CODE. Without this, every mutation restarts from the same
    seed and the search collapses onto one overfit attractor (no diversity
    pressure - the funnel showed ~163 rejects clustered at one IS edge)."""
    r = rng or _SEED_RNG
    if not SEED_ARCHETYPES:
        return _seed_parent(config)
    family, code = r.choice(SEED_ARCHETYPES)
    return Program(
        candidate_id=f"seed:archetype:{family}",
        niche=(family, config.regime_default),
        family=family, regime=config.regime_default,
        fitness_score=0.0, source="seed", code=code,
    )


async def evolution_step(
    db: ProgramDatabase,
    sampler: PromptSampler,
    pool: LLMPool,
    df,
    config: Optional[EvolutionConfig] = None,
    fitness_config: Optional[FitnessConfig] = None,
    objective: Optional[PromptObjective] = None,
    rng: Optional[random.Random] = None,
) -> Optional[Program]:
    """Run ONE evolution step. Returns the new Program, or None if the proposed
    code failed to compile (the candidate is simply skipped)."""
    cfg = config or EvolutionConfig()
    loop = asyncio.get_running_loop()

    parent, inspirations = db.sample()
    # Empty population -> rotate a diverse SEED archetype (diversity pressure),
    # not always BASE_SIGNAL_CODE.
    parent_prog = parent if parent is not None else pick_seed_parent(cfg, rng)
    parent_code = parent_prog.code or BASE_SIGNAL_CODE

    prompt = sampler.build(parent_prog, inspirations, objective)
    diff = await loop.run_in_executor(None, lambda: pool.generate(prompt, tier="auto"))
    diff = extract_code_block(diff or "")   # strip markdown fences from live models

    # Generated before compile so a compile failure still has an id for the
    # funnel log (we want to SEE compile failures, not just skip them silently).
    candidate_id = f"evo:{uuid.uuid4().hex[:8]}"

    try:
        new_code = apply_diff(parent_code, diff or "")
        compile_signal(new_code)  # validate it compiles under the sandbox
    except Exception as exc:  # noqa: BLE001 - bad code => skip this candidate
        logger.info("candidate rejected at compile: %s", str(exc)[:120])
        log_candidate_verdict(CandidateVerdict(
            candidate_id=candidate_id, death_stage="compile", evaluated=False,
            fitness_score=float("-inf"), rejection_reason=f"compile: {exc}",
            family="", regime="", parent_id=parent_prog.candidate_id, program_hash="",
            is_edge=0.0, oos_edge=0.0, n_trades_oos=0, overfit_gap=0.0, timestamp="",
        ))
        return None

    edge_type = parent_prog.family or cfg.edge_type_default

    # Fix #1: evaluate in an isolated subprocess (RLIMIT_CPU + wall-clock kill)
    # so a non-obvious infinite loop in evolved code cannot hang an executor
    # thread - the worker-thread DoS hole. The signal source is recompiled
    # inside the worker (a compiled closure isn't picklable across processes).
    fitness = await loop.run_in_executor(
        None,
        lambda: eval_fitness_subprocess(new_code, {}, df, edge_type=edge_type,
                                        config=fitness_config,
                                        candidate_id=candidate_id),
    )

    # Fix 6: do NOT store gate-rejected candidates. A -inf program would
    # otherwise become a niche elite (first reject wins the empty niche) and
    # pollute the population with non-trading junk.
    if not fitness.evaluated:
        logger.info("candidate rejected at gate: %s", (fitness.rejection_reason or "")[:120])
        log_candidate_verdict(verdict_from_fitness_result(
            fitness, candidate_id=candidate_id, parent_id=parent_prog.candidate_id,
            program_hash=hashlib.sha256(new_code.encode("utf-8")).hexdigest()[:16],
        ))
        return None

    metrics = {
        "oos_vs_buyhold": fitness.oos_vs_buyhold,
        "is_vs_buyhold": fitness.is_vs_buyhold,
        "overfit_gap": fitness.overfit_gap,
        "overfit_penalty": fitness.overfit_penalty,
        "total_trades": fitness.n_trades_oos,
        "stability": max(0.0, 1.0 / (1.0 + fitness.overfit_gap)) if fitness.overfit_gap else 1.0,
    }
    # Behavioural niche (Phase 3): place the child by its OWN evaluated signal
    # behaviour, not the parent's lineage. Without this every descendant lands
    # on the parent's single MAP-Elites cell (the 'all momentum/unknown'
    # monoculture). Falls back to the parent niche, then the config default,
    # only when the evaluator produced no label.
    family = fitness.family_label or parent_prog.family or cfg.edge_type_default
    regime = fitness.regime_label or parent_prog.regime or cfg.regime_default
    niche = (family, regime)
    child = Program(
        candidate_id=candidate_id,
        niche=niche,
        family=family,
        regime=regime,
        fitness_score=fitness.fitness_score,
        source="evolved",
        code=new_code,
        metrics=metrics,
        parent_id=parent_prog.candidate_id,
        generation=getattr(parent_prog, "generation", 0) + 1,
    )
    # Route through the write CHOKEPOINT (ASTRA §7.1): the child is stored only
    # with a machine-verification block carrying objective real-data evidence
    # (the two-window gate verdict + the actual OOS result + a code hash). This
    # is what makes a stored record trustworthy rather than fiction.
    verification = {
        "gate": "passed_two_window",
        "evaluator": "evaluate_fitness_two_window (subprocess-isolated, RLIMIT_CPU)",
        "program_hash": hashlib.sha256(new_code.encode("utf-8")).hexdigest()[:16],
        "real_data_result": {
            "oos_vs_buyhold": fitness.oos_vs_buyhold,
            "is_vs_buyhold": fitness.is_vs_buyhold,
            "overfit_gap": fitness.overfit_gap,
            "n_trades_oos": fitness.n_trades_oos,
            "fitness_score": fitness.fitness_score,
        },
    }
    db.append_verified(child, verification=verification)
    log_candidate_verdict(verdict_from_fitness_result(
        fitness, candidate_id=candidate_id, parent_id=parent_prog.candidate_id,
        program_hash=verification["program_hash"],
    ))
    return child


async def run_evolution(db, sampler, pool, df, n_steps: int = 10, **kwargs):
    """Run n_steps evolution steps; return the list of produced Programs."""
    produced = []
    for _ in range(n_steps):
        prog = await evolution_step(db, sampler, pool, df, **kwargs)
        if prog is not None:
            produced.append(prog)
    return produced
