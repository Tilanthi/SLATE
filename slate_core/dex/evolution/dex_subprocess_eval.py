"""Subprocess-isolated DEX fitness evaluation (mirrors CEX subprocess_eval).

Runs an evolved signal's DEX backtest in a fresh child process with a hard
RLIMIT_CPU cap + wall-clock kill, so a runaway loop in evolved code can't hang
the evolution loop. Returns a FitnessResult (or a rejected one on timeout/crash).
"""
from __future__ import annotations

import dataclasses
import logging
import multiprocessing as mp
from typing import Any, Dict, Optional

from slate_core.discovery.evolution.fitness_evaluator import FitnessConfig, FitnessResult

logger = logging.getLogger(__name__)


def _worker(code: str, df, config: FitnessConfig, candidate_id: str,
            cpu_s: int, q: "mp.Queue") -> None:
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))
    except Exception:  # noqa: BLE001
        pass
    try:
        from slate_core.discovery.evolution.signal_sandbox import compile_signal
        from slate_core.dex.evolution.dex_fitness import evaluate_dex_fitness
        fn = compile_signal(code)
        result = evaluate_dex_fitness(fn, df, config=config, candidate_id=candidate_id)
        q.put(("ok", dataclasses.asdict(result)))
    except Exception as exc:  # noqa: BLE001
        q.put(("error", f"{type(exc).__name__}: {str(exc)[:160]}"))


def _rejected(candidate_id: str, reason: str) -> FitnessResult:
    return FitnessResult(
        evaluated=False, fitness_score=float("-inf"),
        oos_vs_buyhold=0.0, is_vs_buyhold=0.0, overfit_gap=0.0,
        overfit_penalty=0.0, n_trades_is=0, n_trades_oos=0,
        validation_score=0.0, candidate_id=candidate_id, rejection_reason=reason,
    )


def dex_eval_fitness_subprocess(code: str, df, config: Optional[FitnessConfig] = None,
                                candidate_id: str = "", timeout_s: float = 60.0,
                                cpu_s: int = 20) -> FitnessResult:
    cfg = config or FitnessConfig()
    ctx = mp.get_context("spawn")
    q: "mp.Queue" = ctx.Queue()
    proc = ctx.Process(target=_worker, args=(code, df, cfg, candidate_id, cpu_s, q))
    proc.start()
    proc.join(timeout_s)
    if proc.is_alive():
        proc.terminate()
        proc.join(5)
        if proc.is_alive() and hasattr(proc, "kill"):
            proc.kill()
            proc.join(2)
        logger.warning("dex fitness eval killed (wall>=%ss) for %s", timeout_s, candidate_id)
        return _rejected(candidate_id, f"eval timeout (>{timeout_s:.0f}s / >{cpu_s}s CPU)")
    try:
        status, payload = q.get(timeout=5)
    except Exception:  # noqa: BLE001
        return _rejected(candidate_id, "eval: no result (child crashed)")
    if status == "error":
        return _rejected(candidate_id, f"eval error: {payload}")
    try:
        return FitnessResult(**payload)
    except Exception as exc:  # noqa: BLE001
        return _rejected(candidate_id, f"eval: malformed result ({type(exc).__name__})")
