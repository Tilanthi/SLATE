"""Tests for subprocess-isolated fitness evaluation (Fix #1 / DoS hardening).

A signal whose infinite loop is NOT statically detectable (e.g. `while x < 1:
x = x*2`) must be killed by the subprocess + RLIMIT_CPU, not hang the evaluator.
"""
import time

import pandas as pd

from slate_core.discovery.evolution.load_data import load_daily_data
from slate_core.discovery.evolution.subprocess_eval import eval_fitness_subprocess


_DAILY = None


def _daily():
    global _DAILY
    if _DAILY is None:
        _DAILY = load_daily_data("sol_data_cache/SOLUSDT_perpetual_1h_6m.csv")
    return _DAILY


_LOOP_CODE = (
    "def signal_fn(df, i, params):\n"
    "    x = 0\n"
    "    while x < 1:\n"      # infinite at runtime; passes the static `while True` gate
    "        x = x * 2\n"
    "    return 0\n"
)

_OK_CODE = (
    "def signal_fn(df, i, params):\n"
    "    if i < 1:\n"
    "        return 0\n"
    "    return 1 if df['close'].iloc[i] > df['close'].iloc[i - 1] else -1\n"
)


def test_infinite_loop_signal_is_killed_not_hung():
    """A runtime-infinite-loop signal must be abandoned within a bounded time,
    not hang the calling thread (the executor-thread DoS hole)."""
    t0 = time.time()
    result = eval_fitness_subprocess(
        _LOOP_CODE, {}, _daily(), "momentum",
        candidate_id="loop", timeout_s=10, cpu_s=3,
    )
    elapsed = time.time() - t0
    assert result.evaluated is False, "infinite-loop signal was not rejected"
    assert result.fitness_score == float("-inf")
    assert elapsed < 25, (
        f"eval took {elapsed:.1f}s - subprocess isolation did not bound the runtime"
    )


def test_normal_signal_evaluates_through_subprocess():
    """Sanity: a well-formed signal returns a real FitnessResult (not a
    timeout/crash) through the subprocess path."""
    result = eval_fitness_subprocess(
        _OK_CODE, {}, _daily(), "momentum",
        candidate_id="ok", timeout_s=40, cpu_s=20,
    )
    reason = (result.rejection_reason or "").lower()
    assert "timeout" not in reason, f"normal signal timed out: {reason}"
    assert "no result" not in reason and "crash" not in reason, f"worker crashed: {reason}"
