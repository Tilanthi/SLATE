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
    dex_pairs_eval_fitness_subprocess, dex_cross_market_eval_fitness_subprocess,
)
from slate_core.dex.strategies.dex_seeds import dex_pick_seed_parent

logger = logging.getLogger(__name__)

DEX_SYSTEM = (
    "You are an expert DEX quant evolving a perpetual-futures signal for "
    "Hyperliquid. Entries/exits route through MAKER orders (zero gas; maker fee "
    "< taker, with rebates at high maker-fraction), so prefer strategies that "
    "earn the spread rather than cross it. Reach past textbook TA toward "
    "regime-conditional / residual / microstructure-aware edges. The signal reads "
    "OHLCV + injected EMAs and returns {-1,0,1}. Propose a SMALL, targeted change "
    "that improves net-of-fee OUT-OF-SAMPLE PnL without increasing overfit. "
    "Be CONCISE: write CODE, not a rationale (at most one short comment) — your output "
    "is token-limited, and a function truncated before its return earns nothing. The "
    "signal MUST end with `return` of one of {-1, 0, 1}."
)

# Separate funnel log for the DEX pipeline (CEX uses evolution_verdicts.jsonl).
_dex_logger = VerdictLogger("slate_core/dex_verdicts.jsonl")


def log_dex_verdict(verdict: CandidateVerdict) -> None:
    try:
        _dex_logger.log(verdict)
    except Exception as exc:  # noqa: BLE001 - logging must not crash the loop
        logger.warning("dex verdict log failed: %s", exc)


# Hash-dedup: skip re-evaluating byte-identical code the LLM regenerates. Grows
# with evaluated candidates over a run (bounded by the search itself).
_EVALUATED_HASHES: set = set()


def dex_failure_summary(path: str = "slate_core/dex_verdicts.jsonl", n: int = 60) -> str:
    """Read the tail of the DEX verdict log and summarize where candidates die, for
    injection into the prompt (P5: steer the LLM away from dead patterns)."""
    import collections as _collections
    import json as _json
    import os as _os
    if not _os.path.exists(path):
        return ""
    rows = [_json.loads(l) for l in open(path) if l.strip()][-n:]
    if not rows:
        return ""
    stages = _collections.Counter(r.get("death_stage") for r in rows)
    parts = [f"{k} {100 * v / len(rows):.0f}%" for k, v in stages.most_common(4)]
    return ("recent rejects died at: " + ", ".join(parts)
            + " — propose something structurally different; do not repeat these dead patterns.")


class DexPromptSampler(PromptSampler):
    def __init__(self):
        super().__init__(system_instruction=DEX_SYSTEM)
        self.failure_summary = ""           # P5: funnel feedback injected into the prompt

    def build(self, parent, inspirations, objective=None):
        prompt = super().build(parent, inspirations, objective)
        if self.failure_summary:
            return prompt + "\n\nRECENT FAILURE FEEDBACK: " + self.failure_summary
        return prompt


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
    # Empty population -> rotate a DEX anomaly archetype (carry/residual/vol-regime),
    # not EMH-dead textbook TA.
    parent_prog = parent if parent is not None else dex_pick_seed_parent(cfg, rng)
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

    h = _hash(new_code)
    if h in _EVALUATED_HASHES:
        return None                       # hash-dedup: skip re-evaluating identical code
    fitness = await loop.run_in_executor(
        None, lambda: dex_eval_fitness_subprocess(new_code, df, config=fitness_config,
                                                   candidate_id=candidate_id,
                                                   validation=cfg.validation))
    _EVALUATED_HASHES.add(h)

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


async def _run_steps_parallel(step_coro_fn, n_steps: int, concurrency: int = 4):
    """Run n_steps evolution steps, `concurrency` at a time. Each step is
    independent; the heavy LLM call + subprocess eval run concurrently (true
    parallelism — separate processes), while the shared ProgramDatabase mutations
    happen in the single-threaded event loop and stay race-free."""
    produced = []
    remaining = n_steps
    while remaining > 0:
        k = min(max(1, concurrency), remaining)
        batch = await asyncio.gather(
            *(step_coro_fn() for _ in range(k)), return_exceptions=True)
        for r in batch:
            if isinstance(r, Exception):
                logger.warning("dex evolution step error: %s", str(r)[:120])
                continue
            if r is not None:
                produced.append(r)
        remaining -= k
    return produced


async def run_dex_evolution_parallel(db, sampler, pool, df, n_steps: int = 10,
                                     concurrency: int = 4, **kwargs):
    """Concurrent directional evolution (P1 throughput lever)."""
    return await _run_steps_parallel(
        lambda: dex_evolution_step(db, sampler, pool, df, **kwargs),
        n_steps, concurrency)


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
    "(OHLCV+EMA frame to bar i). Propose a SMALL change improving net-of-fee OOS PnL. "
    "Be CONCISE: write CODE, not a rationale (at most one short comment) — your output "
    "is token-limited, and a long preamble gets cut off before the return, leaving a "
    "function that earns NOTHING. quote_fn MUST end with "
    "`return (half_spread_bps, inv_skew_bps, size)`; never return None or a zero spread "
    "(that opts out of the market and earns nothing)."
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


# ---------------------------------------------------------------------------
# Pairs (stat-arb) evolution: evolve the spread_fn(dfA, dfB, i) of a 2-leg
# market-neutral pair. Same crown-jewel reuse.
# ---------------------------------------------------------------------------

DEX_PAIRS_BASE_CODE = (
    "def spread_fn(dfA, dfB, i):\n"
    "    # Evolve: 1 = long A / short B, -1 = reverse, 0 = flat. Use np (no imports).\n"
    "    if i < 50:\n"
    "        return 0\n"
    "    la = np.log(dfA['close'].astype(float).iloc[i - 50:i].values)\n"
    "    lb = np.log(dfB['close'].astype(float).iloc[i - 50:i].values)\n"
    "    spread = la - lb\n"
    "    sd = np.std(spread)\n"
    "    if sd <= 0:\n"
    "        return 0\n"
    "    cur = np.log(float(dfA['close'].iloc[i])) - np.log(float(dfB['close'].iloc[i]))\n"
    "    z = (cur - np.mean(spread)) / sd\n"
    "    if z < -1.5:\n"
    "        return 1\n"
    "    if z > 1.5:\n"
    "        return -1\n"
    "    return 0\n"
)

DEX_PAIRS_SYSTEM = (
    "You are evolving a Hyperliquid PAIRS (stat-arb) spread signal. spread_fn(dfA, "
    "dfB, i) must return 1 (long A / short B), -1 (reverse), or 0 (flat); A and B are "
    "two aligned perp OHLCV frames. Exploit mean-reversion or momentum of their spread "
    "(log price-ratio z-score, or returns differential). Use np (np.log, np.std, np.mean) "
    "— no imports. Propose a SMALL change improving net-of-fee OUT-OF-SAMPLE PnL. "
    "Be CONCISE: write CODE, not a rationale (at most one short comment); spread_fn MUST "
    "end with `return` of 1 / -1 / 0 — a function truncated before its return earns nothing."
)


class DexPairsPromptSampler(PromptSampler):
    def __init__(self):
        super().__init__(system_instruction=DEX_PAIRS_SYSTEM)


async def dex_pairs_evolution_step(db, sampler, pool, dfA, dfB, config=None,
                                   fitness_config=None, rng=None):
    """One pairs evolution step: evolve the spread_fn. dfA/dfB are aligned markets."""
    cfg = config or EvolutionConfig()
    loop = asyncio.get_running_loop()
    parent, inspirations = db.sample()
    if parent is None:
        parent = Program(candidate_id="seed:pairs_base", niche=("pairs", "unknown"),
                         family="pairs", regime="unknown", fitness_score=0.0,
                         source="seed", code=DEX_PAIRS_BASE_CODE)
    parent_code = parent.code or DEX_PAIRS_BASE_CODE

    prompt = sampler.build(parent, inspirations, None)
    diff = await loop.run_in_executor(None, lambda: pool.generate(prompt, tier="auto"))
    diff = extract_code_block(diff or "")
    candidate_id = f"dexpairs:{uuid.uuid4().hex[:8]}"

    try:
        new_code = apply_diff(parent_code, diff or "")
        compile_function(new_code, "spread_fn")
    except Exception as exc:  # noqa: BLE001
        logger.info("dex-pairs candidate rejected at compile: %s", str(exc)[:120])
        log_dex_verdict(CandidateVerdict(
            candidate_id=candidate_id, death_stage="compile", evaluated=False,
            fitness_score=float("-inf"), rejection_reason=f"compile: {exc}",
            family="pairs", regime="", parent_id=parent.candidate_id, program_hash="",
            is_edge=0.0, oos_edge=0.0, n_trades_oos=0, overfit_gap=0.0, timestamp=""))
        return None

    if cfg.max_signal_complexity > 0:
        cplx = signal_complexity(new_code)
        if cplx > cfg.max_signal_complexity:
            log_dex_verdict(CandidateVerdict(
                candidate_id=candidate_id, death_stage="too_complex", evaluated=False,
                fitness_score=float("-inf"),
                rejection_reason=f"complexity={cplx}>{cfg.max_signal_complexity}",
                family="pairs", regime="", parent_id=parent.candidate_id,
                program_hash=_hash(new_code), is_edge=0.0, oos_edge=0.0,
                n_trades_oos=0, overfit_gap=0.0, timestamp=""))
            return None

    h = _hash(new_code)
    if h in _EVALUATED_HASHES:
        return None
    fitness = await loop.run_in_executor(
        None, lambda: dex_pairs_eval_fitness_subprocess(new_code, dfA, dfB,
                                                         config=fitness_config,
                                                         candidate_id=candidate_id))
    _EVALUATED_HASHES.add(h)
    if not fitness.evaluated:
        log_dex_verdict(verdict_from_fitness_result(
            fitness, candidate_id=candidate_id, parent_id=parent.candidate_id,
            program_hash=h))
        return None

    metrics = {"oos_pnl": fitness.oos_vs_buyhold, "is_pnl": fitness.is_vs_buyhold,
               "overfit_gap": fitness.overfit_gap, "n_trades_oos": fitness.n_trades_oos}
    child = Program(
        candidate_id=candidate_id, niche=("pairs", fitness.regime_label or "unknown"),
        family="pairs", regime=fitness.regime_label or "unknown",
        fitness_score=fitness.fitness_score, source="evolved", code=new_code,
        metrics=metrics, parent_id=parent.candidate_id,
        generation=getattr(parent, "generation", 0) + 1)
    verification = {
        "gate": "dex_pairs_passed_two_window",
        "evaluator": "evaluate_dex_pairs_fitness (subprocess)",
        "program_hash": h,
        "real_data_result": {"oos_pnl": fitness.oos_vs_buyhold, "is_pnl": fitness.is_vs_buyhold,
                             "overfit_gap": fitness.overfit_gap, "n_trades_oos": fitness.n_trades_oos},
    }
    db.append_verified(child, verification=verification)
    log_dex_verdict(verdict_from_fitness_result(
        fitness, candidate_id=candidate_id, parent_id=parent.candidate_id,
        program_hash=verification["program_hash"]))
    return child


# ---------------------------------------------------------------------------
# Cross-market directional evolution (P3): evolve a signal_fn evaluated across ALL
# markets (must profit on each). A directional robustness gate.
# ---------------------------------------------------------------------------

async def dex_cross_market_evolution_step(db, sampler, pool, markets_df, config=None,
                                          fitness_config=None, rng=None):
    """Evolve a directional signal judged across multiple markets (cross-market gate)."""
    cfg = config or EvolutionConfig()
    loop = asyncio.get_running_loop()
    parent, inspirations = db.sample()
    parent_prog = parent if parent is not None else dex_pick_seed_parent(cfg, rng)
    parent_code = parent_prog.code or BASE_SIGNAL_CODE

    prompt = sampler.build(parent_prog, inspirations, None)
    diff = await loop.run_in_executor(None, lambda: pool.generate(prompt, tier="auto"))
    diff = extract_code_block(diff or "")
    candidate_id = f"dexxmrkt:{uuid.uuid4().hex[:8]}"
    try:
        new_code = apply_diff(parent_code, diff or "")
        compile_signal(new_code)
    except Exception as exc:  # noqa: BLE001
        logger.info("dex-xmrkt candidate rejected at compile: %s", str(exc)[:120])
        log_dex_verdict(CandidateVerdict(
            candidate_id=candidate_id, death_stage="compile", evaluated=False,
            fitness_score=float("-inf"), rejection_reason=f"compile: {exc}",
            family="cross_market", regime="", parent_id=parent_prog.candidate_id,
            program_hash="", is_edge=0.0, oos_edge=0.0, n_trades_oos=0,
            overfit_gap=0.0, timestamp=""))
        return None
    if cfg.max_signal_complexity > 0:
        cplx = signal_complexity(new_code)
        if cplx > cfg.max_signal_complexity:
            log_dex_verdict(CandidateVerdict(
                candidate_id=candidate_id, death_stage="too_complex", evaluated=False,
                fitness_score=float("-inf"),
                rejection_reason=f"complexity={cplx}>{cfg.max_signal_complexity}",
                family="cross_market", regime="", parent_id=parent_prog.candidate_id,
                program_hash=_hash(new_code), is_edge=0.0, oos_edge=0.0,
                n_trades_oos=0, overfit_gap=0.0, timestamp=""))
            return None
    h = _hash(new_code)
    if h in _EVALUATED_HASHES:
        return None
    fitness = await loop.run_in_executor(
        None, lambda: dex_cross_market_eval_fitness_subprocess(new_code, markets_df,
                                                               config=fitness_config,
                                                               candidate_id=candidate_id))
    _EVALUATED_HASHES.add(h)
    if not fitness.evaluated:
        log_dex_verdict(verdict_from_fitness_result(
            fitness, candidate_id=candidate_id, parent_id=parent_prog.candidate_id,
            program_hash=h))
        return None
    metrics = {"oos_pnl": fitness.oos_vs_buyhold, "is_pnl": fitness.is_vs_buyhold,
               "overfit_gap": fitness.overfit_gap, "n_trades_oos": fitness.n_trades_oos}
    child = Program(
        candidate_id=candidate_id,
        niche=(fitness.family_label or "cross_market", fitness.regime_label or "unknown"),
        family=fitness.family_label or "cross_market", regime=fitness.regime_label or "unknown",
        fitness_score=fitness.fitness_score, source="evolved", code=new_code, metrics=metrics,
        parent_id=parent_prog.candidate_id, generation=getattr(parent_prog, "generation", 0) + 1)
    verification = {
        "gate": "dex_cross_market_passed_all",
        "evaluator": "evaluate_dex_cross_market (subprocess)",
        "program_hash": h,
        "real_data_result": {"oos_pnl": fitness.oos_vs_buyhold, "is_pnl": fitness.is_vs_buyhold,
                             "overfit_gap": fitness.overfit_gap, "n_trades_oos": fitness.n_trades_oos},
    }
    db.append_verified(child, verification=verification)
    log_dex_verdict(verdict_from_fitness_result(
        fitness, candidate_id=candidate_id, parent_id=parent_prog.candidate_id,
        program_hash=verification["program_hash"]))
    return child
