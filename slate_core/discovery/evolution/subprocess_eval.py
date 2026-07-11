"""Subprocess-isolated fitness evaluation for evolved signals (Fix #1).

Evolved signal code runs in the evolution loop's ThreadPoolExecutor. A signal
with a non-obvious infinite loop (one that slips past the static `while True`
gate, e.g. `while x < 1: x = x*2`) would hang that worker thread forever -
threads can't be cancelled, so this is a DoS that deadlocks the loop over time.

SIGALRM can't help here (main-thread only). Instead we evaluate each candidate
in a fresh child process with a hard CPU-second cap (RLIMIT_CPU -> SIGXCPU) plus
a wall-clock join/terminate backstop. A runaway loop is killed; the parent gets
a rejected FitnessResult and the loop carries on.

The signal source is passed as a string and recompiled inside the worker (a
compiled closure isn't picklable across processes).
"""
from __future__ import annotations

import dataclasses
import logging
import multiprocessing as mp
from typing import Any, Dict, Optional

from slate_core.discovery.evolution.fitness_evaluator import (
    FitnessConfig, FitnessResult, evaluate_fitness_two_window,
)

logger = logging.getLogger(__name__)


def _fitness_worker(code: str, parameters: Dict[str, Any], df, edge_type: str,
                    config: FitnessConfig, candidate_id: str, cpu_s: int,
                    result_q: "mp.Queue") -> None:
    """Runs in the child process. Sets a CPU cap, recompiles the (sandboxed)
    signal, evaluates fitness, and puts the outcome on the queue."""
    try:
        import resource
        # Hard CPU cap -> SIGXCPU kills a runaway loop at cpu_s seconds of CPU.
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))
    except Exception:  # noqa: BLE001 - best-effort; wall-clock backstop still applies
        pass
    try:
        from slate_core.discovery.evolution.signal_sandbox import compile_signal
        fn = compile_signal(code)
        result = evaluate_fitness_two_window(
            fn, parameters, df, edge_type, config=config, candidate_id=candidate_id
        )
        result_q.put(("ok", dataclasses.asdict(result)))
    except Exception as exc:  # noqa: BLE001 - any failure => rejected, never hang the parent
        result_q.put(("error", f"{type(exc).__name__}: {str(exc)[:160]}"))


def _rejected(candidate_id: str, reason: str) -> FitnessResult:
    return FitnessResult(
        evaluated=False, fitness_score=float("-inf"),
        oos_vs_buyhold=0.0, is_vs_buyhold=0.0, overfit_gap=0.0,
        overfit_penalty=0.0, n_trades_is=0, n_trades_oos=0,
        validation_score=0.0, candidate_id=candidate_id, rejection_reason=reason,
    )


def eval_fitness_subprocess(code: str, parameters: Dict[str, Any], df, edge_type: str,
                            config: Optional[FitnessConfig] = None,
                            candidate_id: str = "", timeout_s: float = 30.0,
                            cpu_s: int = 10) -> FitnessResult:
    """Evaluate an evolved signal in an isolated child process.

    Returns a real FitnessResult on success, or a rejected (-inf) FitnessResult
    if the child times out, exceeds its CPU cap, or crashes. Never blocks longer
    than ~timeout_s seconds.
    """
    cfg = config or FitnessConfig()
    ctx = mp.get_context("spawn")  # macOS-safe; fresh interpreter, no fork-inherited state
    result_q: "mp.Queue" = ctx.Queue()
    proc = ctx.Process(
        target=_fitness_worker,
        args=(code, parameters, df, edge_type, cfg, candidate_id, cpu_s, result_q),
    )
    proc.start()
    proc.join(timeout_s)

    if proc.is_alive():
        # Wall-clock backstop: RLIMIT_CPU didn't fire in time (or the loop is
        # wall-clock-bound). Force-kill the child so no executor thread hangs.
        proc.terminate()
        proc.join(5)
        if proc.is_alive() and hasattr(proc, "kill"):
            proc.kill()
            proc.join(2)
        logger.warning("fitness eval killed (cpu_s=%s, wall>=%ss) for %s",
                       cpu_s, timeout_s, candidate_id)
        return _rejected(candidate_id, f"eval timeout (>{timeout_s:.0f}s / >{cpu_s}s CPU)")

    try:
        status, payload = result_q.get(timeout=5)
    except Exception:  # noqa: BLE001 - child died without reporting
        return _rejected(candidate_id, "eval: no result (child crashed)")

    if status == "error":
        return _rejected(candidate_id, f"eval error: {payload}")

    try:
        return FitnessResult(**payload)
    except Exception as exc:  # noqa: BLE001 - malformed payload
        return _rejected(candidate_id, f"eval: malformed result ({type(exc).__name__})")
