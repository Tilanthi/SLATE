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

import dataclasses
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from slate_core.discovery.perpetual_futures_backtest import (
    PerpetualBacktestConfig,
    PerpetualFuturesBacktester,
)

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
    require_absolute_oos_profit: bool = True  # gate: must actually make money OOS
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


def split_is_oos(df: pd.DataFrame, is_fraction: float = 0.6):
    """Chronological in-sample / out-of-sample split. Never shuffles.

    Shuffling would leak the future into the past and defeat the whole point
    of the overfit check. Both halves are kept tradeable (>= 30 bars).
    """
    n = len(df)
    cut = int(n * is_fraction)
    cut = max(cut, 30)        # keep IS tradeable
    cut = min(cut, n - 30)    # keep OOS tradeable
    return df.iloc[:cut].copy(), df.iloc[cut:].copy()


def run_backtest(signal_fn: SignalFn, parameters: Dict[str, Any],
                 df: pd.DataFrame, edge_type: str, seed: int) -> Dict[str, Any]:
    """Run one brutal-realism backtest deterministically; return a metrics dict.

    Seeds numpy's global RNG so a given (candidate, seed) is reproducible —
    evolution needs stable comparisons. Works on a copy so the caller's frame
    (e.g. a shared session fixture) is not mutated by the backtester's
    indicator columns.
    """
    np.random.seed(seed)
    work = df.copy()
    if "timestamp" in work.columns:                 # ensure a DatetimeIndex
        work["timestamp"] = pd.to_datetime(work["timestamp"])
        work = work.set_index("timestamp").sort_index()
    bt = PerpetualFuturesBacktester(PerpetualBacktestConfig())
    result = bt.backtest_strategy(
        df=work,
        strategy_name="eval_candidate",
        strategy_description="fitness evaluation",
        edge_type=edge_type,
        signal_function=signal_fn,
        parameters=parameters or {},
    )
    d = dataclasses.asdict(result)
    d["beat_market"] = bool(d.get("beat_market", False))
    return d


@dataclass
class FitnessResult:
    """Outcome of evaluate_fitness. fitness_score = -inf means rejected."""
    evaluated: bool                  # passed the gate and produced a real score
    fitness_score: float            # higher = better; -inf if rejected
    oos_vs_buyhold: float
    is_vs_buyhold: float
    overfit_gap: float              # max(0, is - oos)
    overfit_penalty: float
    n_trades_is: int
    n_trades_oos: int
    validation_score: float
    rejection_reason: str = ""
    metrics_oos: Dict[str, Any] = field(default_factory=dict)
    metrics_is: Dict[str, Any] = field(default_factory=dict)
    candidate_id: str = ""


def _validation_score(oos_metrics: Dict[str, Any], oos_df: pd.DataFrame = None,
                      strategy_name: str = "eval_candidate") -> float:
    """Run the existing pluralistic validators on the OOS result; return 0..1.

    Reads PluralisticValidationReport.overall_validation_score
    (rigorous_validation.py:721). Passes price_data so walk-forward works.
    Never raises — a validation failure yields a neutral 0.0 so evolution
    cannot crash on the validator.
    """
    try:
        from slate_core.discovery.rigorous_validation import get_rigorous_validation_system
        system = get_rigorous_validation_system()
        additional = {"price_data": oos_df} if oos_df is not None else None
        report = system.validate_strategy(strategy_name, oos_metrics, additional)
        return float(getattr(report, "overall_validation_score", 0.0) or 0.0)
    except Exception:  # noqa: BLE001 - validation must never crash evolution
        return 0.0


def evaluate_fitness(signal_fn: SignalFn, parameters: Dict[str, Any],
                     df: pd.DataFrame, edge_type: str,
                     config: Optional[FitnessConfig] = None,
                     candidate_id: str = "") -> FitnessResult:
    """Overfit-resistant fitness for one candidate.

    Pipeline: correctness gate -> chronological IS/OOS backtests -> overfit
    penalty -> (optional) pluralistic validation -> gates. The final
    fitness_score is an overfit-adjusted OOS edge in USDT-vs-buy-hold units.
    """
    cfg = config or FitnessConfig()
    base = FitnessResult(
        evaluated=False, fitness_score=float("-inf"),
        oos_vs_buyhold=0.0, is_vs_buyhold=0.0, overfit_gap=0.0,
        overfit_penalty=0.0, n_trades_is=0, n_trades_oos=0,
        validation_score=0.0, candidate_id=candidate_id,
    )

    # 1) Correctness-by-construction gate
    ok, reason = check_signal_correctness(signal_fn, df, parameters or {},
                                          probe_window=cfg.probe_window)
    if not ok:
        base.rejection_reason = f"correctness: {reason}"
        return base

    # 2) Chronological split + deterministic backtests on both halves
    is_df, oos_df = split_is_oos(df, cfg.is_fraction)
    seed = cfg.random_seed
    is_m = run_backtest(signal_fn, parameters, is_df, edge_type, seed=seed)
    oos_m = run_backtest(signal_fn, parameters, oos_df, edge_type, seed=seed + 1)

    base.metrics_is, base.metrics_oos = is_m, oos_m
    base.is_vs_buyhold = float(is_m.get("vs_buy_hold_usdt", 0.0))
    base.oos_vs_buyhold = float(oos_m.get("vs_buy_hold_usdt", 0.0))
    base.n_trades_is = int(is_m.get("total_trades", 0))
    base.n_trades_oos = int(oos_m.get("total_trades", 0))

    # 3) Overfit gap & penalty (only penalize when IS looks better than OOS)
    base.overfit_gap = max(0.0, base.is_vs_buyhold - base.oos_vs_buyhold)
    base.overfit_penalty = base.overfit_gap * cfg.overfit_penalty_weight

    # 4) Optional pluralistic validation on OOS (slow; off by default)
    if cfg.run_pluralistic_validation:
        base.validation_score = _validation_score(oos_m, oos_df=oos_df)
    else:
        base.validation_score = 1.0  # neutral; floor gate skipped below

    # 5) Gates
    reasons = []
    if base.n_trades_oos < cfg.min_trades:
        reasons.append(f"oos_trades={base.n_trades_oos}<{cfg.min_trades}")
    if cfg.require_beat_buyhold_oos and base.oos_vs_buyhold <= 0:
        reasons.append("oos_does_not_beat_buyhold")
    if cfg.require_absolute_oos_profit:
        oos_profit = float(oos_m.get("total_profit_usdt", 0.0))
        if oos_profit <= 0:
            reasons.append(f"oos_total_profit={oos_profit:.2f}<=0 (not profitable)")
    if cfg.run_pluralistic_validation and base.validation_score < cfg.validation_score_floor:
        reasons.append(
            f"validation_score={base.validation_score:.2f}<{cfg.validation_score_floor}"
        )
    if reasons:
        base.rejection_reason = "; ".join(reasons)
        return base

    # 6) Final overfit-adjusted OOS edge
    base.evaluated = True
    base.fitness_score = base.oos_vs_buyhold - base.overfit_penalty
    return base
