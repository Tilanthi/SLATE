"""Async DEX evolution controller (mirrors the CEX controller; DEX economics).

Reuses the venue-agnostic crown jewel wholesale: ProgramDatabase + append_verified
(write chokepoint), verdict_log (funnel), signal_sandbox (compile_signal +
signal_complexity), evolvable_strategy (SEARCH/REPLACE + SEED_ARCHETYPES),
LLMPool, PromptSampler. DEX-specific: a DEX-flavored system prompt, the
dex_eval_fitness_subprocess evaluator, and a SEPARATE verdict log
(slate_core/dex_verdicts.jsonl) so CEX and DEX stay isolated.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import uuid
from typing import Optional

from slate_core.discovery.evolution.controller import EvolutionConfig, pick_seed_parent
from slate_core.discovery.evolution.evolvable_strategy import (
    BASE_SIGNAL_CODE, apply_diff, extract_code_block,
)
from slate_core.discovery.evolution.fitness_evaluator import FitnessConfig
from slate_core.discovery.evolution.llm_pool import LLMPool
from slate_core.discovery.evolution.program_database import Program, ProgramDatabase
from slate_core.discovery.evolution.prompt_sampler import PromptSampler
from slate_core.discovery.evolution.signal_sandbox import (
    compile_signal, compile_function, signal_complexity,
)
from slate_core.discovery.evolution.verdict_log import (
    CandidateVerdict, VerdictLogger, verdict_from_fitness_result,
)
from slate_core.dex.evolution.dex_subprocess_eval import (
    dex_eval_fitness_subprocess, dex_mm_eval_fitness_subprocess,
)

logger = logging.getLogger(__name__)

DEX_SYSTEM = (
    "You are an expert DEX quant evolving a perpetual-futures signal for "
    "Hyperliquid. Entries/exits route through MAKER orders (zero gas; maker fee "
    "< taker, with rebates at high maker-fraction), so prefer strategies that "
    "earn the spread rather than cross it. Reach past textbook TA toward "
    "regime-conditional / residual / microstructure-aware edges. The signal reads "
    "OHLCV + injected EMAs and returns {-1,0,1}. Propose a SMALL, targeted change "
    "that improves net-of-fee OUT-OF-SAMPLE PnL without increasing overfit."
)

# Separate funnel log for the DEX pipeline (CEX uses evolution_verdicts.jsonl).
_dex_logger = VerdictLogger("slate_core/dex_verdicts.jsonl")


def log_dex_verdict(verdict: CandidateVerdict) -> None:
    try:
        _dex_logger.log(verdict)
    except Exception as exc:  # noqa: BLE001 - logging must not crash the loop
        logger.warning("dex verdict log failed: %s", exc)


class DexPromptSampler(PromptSampler):
    def __init__(self):
        super().__init__(system_instruction=DEX_SYSTEM)


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]


async def dex_evolution_step(
    db: ProgramDatabase,
    sampler: PromptSampler,
    pool: LLMPool,
    df,
    config: Optional[EvolutionConfig] = None,
    fitness_config: Optional[FitnessConfig] = None,
    rng: Optional[random.Random] = None,
) -> Optional[Program]:
    """One DEX evolution step. Returns the new Program, or None if the candidate
    was rejected (compile/complexity/gate)."""
    cfg = config or EvolutionConfig()
    loop = asyncio.get_running_loop()

    parent, inspirations = db.sample()
    parent_prog = parent if parent is not None else pick_seed_parent(cfg, rng)
    parent_code = parent_prog.code or BASE_SIGNAL_CODE

    prompt = sampler.build(parent_prog, inspirations, None)
    diff = await loop.run_in_executor(None, lambda: pool.generate(prompt, tier="auto"))
    diff = extract_code_block(diff or "")

    candidate_id = f"dexevo:{uuid.uuid4().hex[:8]}"
    try:
        new_code = apply_diff(parent_code, diff or "")
        compile_signal(new_code)
    except Exception as exc:  # noqa: BLE001
        logger.info("dex candidate rejected at compile: %s", str(exc)[:120])
        log_dex_verdict(CandidateVerdict(
            candidate_id=candidate_id, death_stage="compile", evaluated=False,
            fitness_score=float("-inf"), rejection_reason=f"compile: {exc}",
            family="", regime="", parent_id=parent_prog.candidate_id, program_hash="",
            is_edge=0.0, oos_edge=0.0, n_trades_oos=0, overfit_gap=0.0, timestamp=""))
        return None

    if cfg.max_signal_complexity > 0:
        cplx = signal_complexity(new_code)
        if cplx > cfg.max_signal_complexity:
            logger.info("dex candidate rejected: complexity %d > %d", cplx, cfg.max_signal_complexity)
            log_dex_verdict(CandidateVerdict(
                candidate_id=candidate_id, death_stage="too_complex", evaluated=False,
                fitness_score=float("-inf"),
                rejection_reason=f"complexity={cplx}>{cfg.max_signal_complexity}",
                family="", regime="", parent_id=parent_prog.candidate_id,
                program_hash=_hash(new_code), is_edge=0.0, oos_edge=0.0,
                n_trades_oos=0, overfit_gap=0.0, timestamp=""))
            return None

    fitness = await loop.run_in_executor(
        None, lambda: dex_eval_fitness_subprocess(new_code, df, config=fitness_config,
                                                   candidate_id=candidate_id))

    if not fitness.evaluated:
        logger.info("dex candidate rejected at gate: %s", (fitness.rejection_reason or "")[:120])
        log_dex_verdict(verdict_from_fitness_result(
            fitness, candidate_id=candidate_id, parent_id=parent_prog.candidate_id,
            program_hash=_hash(new_code)))
        return None

    metrics = {
        "oos_pnl": fitness.oos_vs_buyhold, "is_pnl": fitness.is_vs_buyhold,
        "overfit_gap": fitness.overfit_gap, "n_trades_oos": fitness.n_trades_oos,
        "oos_activity": fitness.oos_activity,
    }
    family = fitness.family_label or parent_prog.family or cfg.edge_type_default
    regime = fitness.regime_label or parent_prog.regime or cfg.regime_default
    child = Program(
        candidate_id=candidate_id, niche=(family, regime), family=family, regime=regime,
        fitness_score=fitness.fitness_score, source="evolved", code=new_code,
        metrics=metrics, parent_id=parent_prog.candidate_id,
        generation=getattr(parent_prog, "generation", 0) + 1,
    )
    verification = {
        "gate": "dex_passed_two_window",
        "evaluator": "evaluate_dex_fitness (subprocess-isolated, RLIMIT_CPU)",
        "program_hash": _hash(new_code),
        "real_data_result": {
            "oos_pnl": fitness.oos_vs_buyhold, "is_pnl": fitness.is_vs_buyhold,
            "overfit_gap": fitness.overfit_gap, "n_trades_oos": fitness.n_trades_oos,
        },
    }
    db.append_verified(child, verification=verification)
    log_dex_verdict(verdict_from_fitness_result(
        fitness, candidate_id=candidate_id, parent_id=parent_prog.candidate_id,
        program_hash=verification["program_hash"]))
    return child


async def run_dex_evolution(db, sampler, pool, df, n_steps: int = 10, **kwargs):
    produced = []
    for _ in range(n_steps):
        prog = await dex_evolution_step(db, sampler, pool, df, **kwargs)
        if prog is not None:
            produced.append(prog)
    return produced


# ---------------------------------------------------------------------------
# Market-maker evolution: evolve the QUOTING logic (quote_fn), not a directional
# signal. Same crown-jewel reuse (chokepoint, funnel, sandbox, complexity cap).
# ---------------------------------------------------------------------------

DEX_MM_BASE_CODE = (
    "def quote_fn(state):\n"
    "    # Evolve this: return (half_spread_bps, inv_skew_bps, size).\n"
    "    return (10.0, 2.0, 0.5)\n"
)

DEX_MM_SYSTEM = (
    "You are evolving a Hyperliquid MARKET-MAKER's quoting logic. quote_fn(state) "
    "must return a tuple (half_spread_bps, inv_skew_bps, size): the half-spread to "
    "quote around mid, an inventory skew (positive leans quotes down when long), and "
    "an order size. Earn the spread + maker rebate while managing inventory and "
    "adverse selection. state has .close, .position, .high, .low, .i, .history "
    "(OHLCV+EMA frame to bar i). Propose a SMALL change improving net-of-fee OOS PnL."
)


class DexMMPromptSampler(PromptSampler):
    def __init__(self):
        super().__init__(system_instruction=DEX_MM_SYSTEM)


async def dex_mm_evolution_step(
    db: ProgramDatabase, sampler: PromptSampler, pool: LLMPool, df,
    config: Optional[EvolutionConfig] = None,
    fitness_config: Optional[FitnessConfig] = None,
    rng: Optional[random.Random] = None,
) -> Optional[Program]:
    """One market-maker evolution step: evolve the quote_fn. Returns the new Program
    or None if rejected."""
    cfg = config or EvolutionConfig()
    loop = asyncio.get_running_loop()
    parent, inspirations = db.sample()
    if parent is None:
        parent = Program(candidate_id="seed:mm_base", niche=("market_maker", "unknown"),
                         family="market_maker", regime="unknown", fitness_score=0.0,
                         source="seed", code=DEX_MM_BASE_CODE)
    parent_code = parent.code or DEX_MM_BASE_CODE

    prompt = sampler.build(parent, inspirations, None)
    diff = await loop.run_in_executor(None, lambda: pool.generate(prompt, tier="auto"))
    diff = extract_code_block(diff or "")
    candidate_id = f"dexmm:{uuid.uuid4().hex[:8]}"

    try:
        new_code = apply_diff(parent_code, diff or "")
        compile_function(new_code, "quote_fn")
    except Exception as exc:  # noqa: BLE001
        logger.info("dex-mm candidate rejected at compile: %s", str(exc)[:120])
        log_dex_verdict(CandidateVerdict(
            candidate_id=candidate_id, death_stage="compile", evaluated=False,
            fitness_score=float("-inf"), rejection_reason=f"compile: {exc}",
            family="market_maker", regime="", parent_id=parent.candidate_id, program_hash="",
            is_edge=0.0, oos_edge=0.0, n_trades_oos=0, overfit_gap=0.0, timestamp=""))
        return None

    if cfg.max_signal_complexity > 0:
        cplx = signal_complexity(new_code)
        if cplx > cfg.max_signal_complexity:
            log_dex_verdict(CandidateVerdict(
                candidate_id=candidate_id, death_stage="too_complex", evaluated=False,
                fitness_score=float("-inf"),
                rejection_reason=f"complexity={cplx}>{cfg.max_signal_complexity}",
                family="market_maker", regime="", parent_id=parent.candidate_id,
                program_hash=_hash(new_code), is_edge=0.0, oos_edge=0.0,
                n_trades_oos=0, overfit_gap=0.0, timestamp=""))
            return None

    fitness = await loop.run_in_executor(
        None, lambda: dex_mm_eval_fitness_subprocess(new_code, df, config=fitness_config,
                                                      candidate_id=candidate_id))
    if not fitness.evaluated:
        log_dex_verdict(verdict_from_fitness_result(
            fitness, candidate_id=candidate_id, parent_id=parent.candidate_id,
            program_hash=_hash(new_code)))
        return None

    metrics = {"oos_pnl": fitness.oos_vs_buyhold, "is_pnl": fitness.is_vs_buyhold,
               "overfit_gap": fitness.overfit_gap, "n_trades_oos": fitness.n_trades_oos}
    child = Program(
        candidate_id=candidate_id,
        niche=(fitness.family_label or "market_maker", fitness.regime_label or "unknown"),
        family=fitness.family_label or "market_maker", regime=fitness.regime_label or "unknown",
        fitness_score=fitness.fitness_score, source="evolved", code=new_code, metrics=metrics,
        parent_id=parent.candidate_id, generation=getattr(parent, "generation", 0) + 1)
    verification = {
        "gate": "dex_mm_passed_two_window", "evaluator": "evaluate_dex_mm_fitness (subprocess)",
        "program_hash": _hash(new_code),
        "real_data_result": {"oos_pnl": fitness.oos_vs_buyhold, "is_pnl": fitness.is_vs_buyhold,
                             "overfit_gap": fitness.overfit_gap, "n_trades_oos": fitness.n_trades_oos},
    }
    db.append_verified(child, verification=verification)
    log_dex_verdict(verdict_from_fitness_result(
        fitness, candidate_id=candidate_id, parent_id=parent.candidate_id,
        program_hash=verification["program_hash"]))
    return child
