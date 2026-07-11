"""Overfit-resistant fitness evaluator for SLATE evolution (Phase 0).

Public surface (added incrementally across Tasks 0.2-0.4):
    FitnessConfig                                  (Task 0.2)
    check_signal_correctness(...) -> (ok, reason)  (Task 0.2)
    split_is_oos(df, is_fraction)                  (Task 0.3)
    run_backtest(...) -> dict                       (Task 0.3)
    FitnessResult                                  (Task 0.4)
    evaluate_fitness(...) -> FitnessResult         (Task 0.4)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

import numpy as np
import pandas as pd

SignalFn = Callable[[pd.DataFrame, int, Dict[str, Any]], float]
VALID_SIGNALS = {-1, 0, 1}


@dataclass
class FitnessConfig:
    """Knobs for evaluate_fitness. Defaults are conservative.

    Pluralistic validation is EXPENSIVE (bootstrap 1000 + MC 1000 sims) and
    several validators need additional_data we lack inside the inner loop.
    It defaults OFF: Phase 0's overfit defense is the IS/OOS split + overfit
    penalty + beat-buy-hold-OOS gate. Turn it ON only for finalists.
    """
    is_fraction: float = 0.6                 # first 60% of bars = in-sample
    overfit_penalty_weight: float = 1.0
    min_trades: int = 10                     # gate: enough activity to be meaningful
    require_beat_buyhold_oos: bool = True
    run_pluralistic_validation: bool = False
    validation_score_floor: float = 0.4      # only applied when validation is ON
    random_seed: int = 12345                 # determinism per evaluation
    probe_window: int = 30                   # bars used by the correctness gate


def check_signal_correctness(
    signal_fn: SignalFn,
    df: pd.DataFrame,
    parameters: Dict[str, Any],
    probe_window: int = 30,
) -> Tuple[bool, str]:
    """Correctness-by-construction gate.

    Probes the signal function over a short window and rejects candidates that
    raise, return non-finite values, or emit anything outside {-1, 0, 1}.
    Mirrors AlphaEvolve's randomized-input correctness checks, adapted so the
    safety envelope (sizing/leverage/execution) can never be touched by evolved
    signal code.
    """
    start = min(probe_window, max(0, len(df) - 1))
    for i in range(20, start):  # 20 = backtester warmup
        try:
            sig = signal_fn(df, i, parameters)
        except Exception as exc:  # noqa: BLE001 - any failure means reject
            return False, f"exception at bar {i}: {exc}"
        if sig is None or (isinstance(sig, float) and math.isnan(sig)):
            return False, f"NaN/None signal at bar {i}"
        if sig not in VALID_SIGNALS:
            return False, f"signal {sig!r} at bar {i} not bounded to {{-1,0,1}}"
    return True, ""
