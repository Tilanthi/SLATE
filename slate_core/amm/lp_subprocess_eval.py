"""Subprocess-isolated LP fitness evaluation.

Mirrors dex_subprocess_eval.py. Compiles lp_fn via compile_function,
evaluates via evaluate_lp_fitness, with RLIMIT_CPU + wall-clock kill.
"""
from __future__ import annotations

import dataclasses
import logging
import multiprocessing as mp
from typing import Optional

from slate_core.discovery.evolution.fitness_evaluator import FitnessConfig, FitnessResult

logger = logging.getLogger(__name__)


def _lp_worker(code: str, df, config: FitnessConfig, candidate_id: str,
               cpu_s: int, q: "mp.Queue") -> None:
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))
    except Exception:
        pass
    try:
        from slate_core.discovery.evolution.signal_sandbox import compile_function
        from slate_core.amm.lp_fitness import evaluate_lp_fitness
        fn = compile_function(code, "lp_fn")
        result = evaluate_lp_fitness(fn, df, config=config, candidate_id=candidate_id)
        q.put(("ok", dataclasses.asdict(result)))
    except Exception as exc:
        q.put(("error", f"{type(exc).__name__}: {str(exc)[:160]}"))


def _rejected(candidate_id: str, reason: str) -> FitnessResult:
    return FitnessResult(
        evaluated=False, fitness_score=float("-inf"),
        oos_vs_buyhold=0.0, is_vs_buyhold=0.0, overfit_gap=0.0,
        overfit_penalty=0.0, n_trades_is=0, n_trades_oos=0,
        validation_score=0.0, candidate_id=candidate_id, rejection_reason=reason,
    )


def lp_eval_fitness_subprocess(code: str, df, config: Optional[FitnessConfig] = None,
                               candidate_id: str = "", timeout_s: float = 120.0,
                               cpu_s: int = 20) -> FitnessResult:
    cfg = config or FitnessConfig()
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    proc = ctx.Process(target=_lp_worker, args=(code, df, cfg, candidate_id, cpu_s, q))
    proc.start()
    proc.join(timeout_s)
    if proc.is_alive():
        proc.terminate()
        proc.join(5)
        if proc.is_alive() and hasattr(proc, "kill"):
            proc.kill()
            proc.join(2)
        return _rejected(candidate_id, f"eval timeout (>{timeout_s:.0f}s / >{cpu_s}s CPU)")
    try:
        status, payload = q.get(timeout=5)
    except Exception:
        return _rejected(candidate_id, "eval: no result (child crashed)")
    if status == "error":
        return _rejected(candidate_id, f"eval error: {payload}")
    try:
        return FitnessResult(**payload)
    except Exception as exc:
        return _rejected(candidate_id, f"eval: malformed result ({type(exc).__name__})")
