"""LP evolution controller + service.

Mirrors the DEX controller/service pattern. Evolves lp_fn via LLM-guided
evolution with the full crown jewel (chokepoint, funnel, sandbox, gates).
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import uuid
from typing import Optional

from slate_core.discovery.evolution.controller import EvolutionConfig
from slate_core.discovery.evolution.evolvable_strategy import apply_diff, extract_code_block
from slate_core.discovery.evolution.fitness_evaluator import FitnessConfig
from slate_core.discovery.evolution.llm_pool import LLMPool
from slate_core.discovery.evolution.program_database import Program, ProgramDatabase
from slate_core.discovery.evolution.prompt_sampler import PromptSampler
from slate_core.discovery.evolution.signal_sandbox import compile_function, signal_complexity
from slate_core.discovery.evolution.verdict_log import (
    CandidateVerdict, VerdictLogger, verdict_from_fitness_result,
)
from slate_core.amm.lp_subprocess_eval import lp_eval_fitness_subprocess
from slate_core.amm.lp_seeds import LP_SEED_ARCHETYPES, lp_pick_seed_parent

logger = logging.getLogger(__name__)

LP_SYSTEM = (
    "You are evolving a Uniswap V3 concentrated-liquidity LP strategy for a stablecoin "
    "pair (USDC/USDT). Your function MUST follow this exact format:\n\n"
    "def lp_fn(bar):\n"
    "    close = float(bar['close'])\n"
    "    vol = float(bar.get('volume', 0))\n"
    "    return {'action': 'ENTER', 'range_bps': 20}\n\n"
    "RULES:\n"
    "- bar is a pandas Series: bar['close'], bar['high'], bar['low'], bar['volume']\n"
    "- Return a dict with keys 'action' (ENTER/EXIT/HOLD) and 'range_bps' (float, 1-1000)\n"
    "- range_bps = half-width of your LP range in basis points (20 = ±0.20%)\n"
    "- ENTER deploys capital; EXIT withdraws; HOLD does nothing\n"
    "- You earn swap fees ONLY while ENTERed and in range; you suffer IL on price moves\n"
    "- Use float() to cast bar values. Do NOT use df, i, or params — only bar.\n"
    "- Be CONCISE: write CODE, not a rationale. At most ONE short comment line. Your "
    "output is token-limited — a long '# Strategy / # Rationale' preamble gets cut off "
    "before the return statement, and a function with no return earns NOTHING.\n"
    "- The function MUST end with a `return {'action': ..., 'range_bps': ...}`.\n"
    "- LPs earn fees by being IN the market: an LP that rarely ENTERs earns ~0. Prefer "
    "being ENTERed most of the time; only EXIT on a clear IL-risk signal. With a single "
    "bar you cannot reliably detect a multi-bar 'regime' — simple logic that ENTERs "
    "beats compound volatility/residual thresholds that rarely fire on tight stablecoin "
    "data (USDC/USDT deviates only ~4 bps from peg).\n"
    "- Propose a SMALL change improving net yield (APY)."
)

_lp_logger = VerdictLogger("slate_core/amm_verdicts.jsonl")
_LP_EVALUATED_HASHES: set = set()


def log_lp_verdict(verdict: CandidateVerdict) -> None:
    try:
        _lp_logger.log(verdict)
    except Exception as exc:
        logger.warning("lp verdict log failed: %s", exc)


class LPPromptSampler(PromptSampler):
    def __init__(self):
        super().__init__(system_instruction=LP_SYSTEM)


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]


async def lp_evolution_step(
    db: ProgramDatabase, sampler: PromptSampler, pool: LLMPool, df,
    config: Optional[EvolutionConfig] = None,
    fitness_config: Optional[FitnessConfig] = None,
    rng: Optional[random.Random] = None,
) -> Optional[Program]:
    cfg = config or EvolutionConfig()
    loop = asyncio.get_running_loop()

    parent, inspirations = db.sample()
    parent_prog = parent if parent is not None else lp_pick_seed_parent(cfg, rng)
    parent_code = parent_prog.code or LP_SEED_ARCHETYPES[0][1]

    prompt = sampler.build(parent_prog, inspirations, None)
    diff = await loop.run_in_executor(None, lambda: pool.generate(prompt, tier="auto"))
    diff = extract_code_block(diff or "")
    candidate_id = f"ammlp:{uuid.uuid4().hex[:8]}"

    try:
        new_code = apply_diff(parent_code, diff or "")
        compile_function(new_code, "lp_fn")
    except Exception as exc:
        logger.info("amm-lp candidate rejected at compile: %s", str(exc)[:120])
        log_lp_verdict(CandidateVerdict(
            candidate_id=candidate_id, death_stage="compile", evaluated=False,
            fitness_score=float("-inf"), rejection_reason=f"compile: {exc}",
            family="lp", regime="stablecoin", parent_id=parent_prog.candidate_id,
            program_hash="", is_edge=0.0, oos_edge=0.0, n_trades_oos=0,
            overfit_gap=0.0, timestamp=""))
        return None

    if cfg.max_signal_complexity > 0:
        cplx = signal_complexity(new_code)
        if cplx > cfg.max_signal_complexity:
            log_lp_verdict(CandidateVerdict(
                candidate_id=candidate_id, death_stage="too_complex", evaluated=False,
                fitness_score=float("-inf"),
                rejection_reason=f"complexity={cplx}>{cfg.max_signal_complexity}",
                family="lp", regime="stablecoin", parent_id=parent_prog.candidate_id,
                program_hash=_hash(new_code), is_edge=0.0, oos_edge=0.0,
                n_trades_oos=0, overfit_gap=0.0, timestamp=""))
            return None

    h = _hash(new_code)
    if h in _LP_EVALUATED_HASHES:
        return None
    fitness = await loop.run_in_executor(
        None, lambda: lp_eval_fitness_subprocess(new_code, df,
                                                  config=fitness_config,
                                                  candidate_id=candidate_id))
    _LP_EVALUATED_HASHES.add(h)
    if not fitness.evaluated:
        log_lp_verdict(verdict_from_fitness_result(
            fitness, candidate_id=candidate_id, parent_id=parent_prog.candidate_id,
            program_hash=h))
        return None

    metrics = {"oos_pnl": fitness.oos_vs_buyhold, "is_pnl": fitness.is_vs_buyhold,
               "overfit_gap": fitness.overfit_gap, "n_trades_oos": fitness.n_trades_oos}
    child = Program(
        candidate_id=candidate_id, niche=("lp", "stablecoin"),
        family="lp", regime="stablecoin",
        fitness_score=fitness.fitness_score, source="evolved", code=new_code,
        metrics=metrics, parent_id=parent_prog.candidate_id,
        generation=getattr(parent_prog, "generation", 0) + 1)
    verification = {
        "gate": "lp_passed_two_window",
        "evaluator": "evaluate_lp_fitness (subprocess)",
        "program_hash": h,
        "real_data_result": {"oos_pnl": fitness.oos_vs_buyhold,
                             "is_pnl": fitness.is_vs_buyhold,
                             "overfit_gap": fitness.overfit_gap,
                             "n_trades_oos": fitness.n_trades_oos},
    }
    db.append_verified(child, verification=verification)
    log_lp_verdict(verdict_from_fitness_result(
        fitness, candidate_id=candidate_id, parent_id=parent_prog.candidate_id,
        program_hash=verification["program_hash"]))
    return child


async def _run_lp_steps_parallel(step_fn, n_steps: int, concurrency: int = 4):
    produced = []
    remaining = n_steps
    while remaining > 0:
        k = min(max(1, concurrency), remaining)
        batch = await asyncio.gather(*(step_fn() for _ in range(k)), return_exceptions=True)
        for r in batch:
            if isinstance(r, Exception):
                logger.warning("lp evolution step error: %s", str(r)[:120])
                continue
            if r is not None:
                produced.append(r)
        remaining -= k
    return produced


async def run_lp_evolution_parallel(db, sampler, pool, df, n_steps=10, concurrency=4, **kwargs):
    return await _run_lp_steps_parallel(
        lambda: lp_evolution_step(db, sampler, pool, df, **kwargs),
        n_steps, concurrency)
