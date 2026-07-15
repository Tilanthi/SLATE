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
    add_signal_indicators,
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
    min_fitness: float = 0.0                 # gate: reject if overfit-adjusted fitness < floor.
                                             # Stops overfit survivors (IS>>OOS) that squeak past
                                             # the absolute-profit gate with deeply negative fitness
                                             # from being stored as niche elites.
    activity_floor: float = 0.20             # activity-credit: a signal must hold a position on >=
                                             # this fraction of OOS bars to earn its FULL edge. Below
                                             # it, the OOS edge is credited proportionally (a flat
                                             # signal's cash-beats-losing-buyhold 'edge' -> ~0).

    @classmethod
    def strict(cls) -> "FitnessConfig":
        """Deployment-grade: full overfit protection (the field defaults)."""
        return cls()

    @classmethod
    def exploration(cls) -> "FitnessConfig":
        """Looser preset for the running loop so it produces survivors to learn
        from. Keeps the core defenses (both OOS windows must be profitable) but
        lowers the min-trade floor and the overfit penalty weight."""
        return cls(min_trades=5, overfit_penalty_weight=0.5)


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
        seed=seed,
    )
    d = dataclasses.asdict(result)
    d["beat_market"] = bool(d.get("beat_market", False))
    return d


# ---------------------------------------------------------------------------
# Behavioural niche labels (Phase 3): family + regime derived from the
# candidate's OWN behaviour so MAP-Elites can place each program in a distinct
# cell. Pure functions of (signal_fn, df) — they re-probe the signal series,
# so they do not depend on backtest internals and survive the subprocess
# boundary via FitnessResult.asdict().
# ---------------------------------------------------------------------------

_WARMUP = 20  # bars the backtester needs before it will call the signal


def classify_signal_family(signal_fn: SignalFn, df: pd.DataFrame,
                           parameters: Dict[str, Any], lookback: int = 5,
                           momentum_thresh: float = 0.15) -> str:
    """Strategy family from how the signal relates to recent returns.

    momentum       — signal aligns with the recent move (corr > +thresh)
    mean_reversion — signal opposes the recent move  (corr < -thresh)
    other          — weak/flat/noisy relationship, or never trades

    Diversifies the *family* axis of the niche grid across candidates on the
    same data (a pure-data label could not do this).
    """
    df = add_signal_indicators(df.copy())   # signals may read injected EMA cols
    close = df["close"].astype(float).values
    n = len(close)
    start = max(lookback, _WARMUP)
    signals: list = []
    rets: list = []
    for i in range(start, n):
        try:
            sig = signal_fn(df, i, parameters)
        except Exception:  # noqa: BLE001 - a flaky bar shouldn't crash labelling
            continue
        if sig not in VALID_SIGNALS:
            continue
        signals.append(float(sig))
        rets.append(close[i] / close[i - lookback] - 1.0)
    if len(signals) < 10 or float(np.std(signals)) == 0.0:
        return "other"
    corr = float(np.corrcoef(signals, rets)[0, 1])
    if math.isnan(corr):
        return "other"
    if corr > momentum_thresh:
        return "momentum"
    if corr < -momentum_thresh:
        return "mean_reversion"
    return "other"


def classify_active_regime(signal_fn: SignalFn, df: pd.DataFrame,
                           parameters: Dict[str, Any], window: int = 20) -> str:
    """The realized-vol regime in which this candidate actually holds a position.

    Buckets every bar low_vol / med_vol / high_vol by the tercile of the whole
    window's rolling realized vol, then takes the modal bucket across the bars
    where the candidate is in the market (signal != 0). Candidate-dependent, so
    two strategies on the same data can land in different regime cells. Returns
    'unknown' if the candidate never trades or the series is too short.
    """
    df = add_signal_indicators(df.copy())   # signals may read injected EMA cols
    close = df["close"].astype(float).values
    n = len(close)
    if n <= window + 3:
        return "unknown"
    logret = np.zeros(n)
    logret[1:] = np.log(close[1:] / close[:-1])
    rv = np.full(n, np.nan)
    for i in range(window, n):
        rv[i] = float(np.std(logret[i - window + 1: i + 1], ddof=0))
    valid = rv[~np.isnan(rv)]
    if len(valid) < 3:
        return "unknown"
    t1, t2 = (float(x) for x in np.percentile(valid, [33.333, 66.667]))

    def _bucket(v: float) -> Optional[str]:
        if math.isnan(v):
            return None
        if v <= t1:
            return "low_vol"
        if v <= t2:
            return "med_vol"
        return "high_vol"

    in_market: list = []
    for i in range(_WARMUP, n):
        try:
            sig = signal_fn(df, i, parameters)
        except Exception:  # noqa: BLE001
            continue
        if sig in (1, -1):
            b = _bucket(rv[i])
            if b is not None:
                in_market.append(b)
    if not in_market:
        return "unknown"
    from collections import Counter
    return Counter(in_market).most_common(1)[0][0]


def signal_market_activity(signal_fn: SignalFn, df: pd.DataFrame,
                           parameters: Dict[str, Any], warmup: int = _WARMUP) -> float:
    """Fraction of post-warmup bars where the signal holds a position
    (|signal| == 1). 0.0 = always flat (dormant); 1.0 = always in the market.

    The market-participation measure behind the activity-credit: a strategy that
    sits flat for the whole window has not earned any vs_buy_hold 'edge' - that
    'edge' is just cash outperforming a losing market, not a tradeable signal.
    Probes on the backtester-enriched frame so signals reading injected columns
    (ema_20 etc.) work.
    """
    df = add_signal_indicators(df.copy())
    n = len(df)
    start = min(warmup, n)
    if start >= n:
        return 0.0
    active = 0
    total = 0
    for i in range(start, n):
        try:
            sig = signal_fn(df, i, parameters)
        except Exception:  # noqa: BLE001 - a flaky bar counts as flat
            sig = 0
        total += 1
        if sig in (1, -1):
            active += 1
    return active / total if total else 0.0


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
    # Behavioural niche labels (Phase 3): derived from the candidate's OWN
    # behaviour, not inherited. Let MAP-Elites diversify across cells instead
    # of collapsing every descendant onto the parent's niche. Empty when the
    # candidate was rejected (rejected candidates are never stored anyway).
    family_label: str = ""
    regime_label: str = ""
    # Activity-credit (gradient pressure to actually trade, not just a prompt
    # nudge): oos_activity = fraction of OOS bars in a position; exposure_factor
    # = how much of the OOS edge is credited (0 for dormant, 1 for >= activity_floor).
    oos_activity: float = 0.0
    exposure_factor: float = 1.0


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

    # Behavioural niche labels: computed here (after correctness) so REJECTED
    # candidates carry them too - mirrors evaluate_fitness_two_window.
    base.family_label = classify_signal_family(signal_fn, df, parameters or {})
    base.regime_label = classify_active_regime(signal_fn, df, parameters or {})

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
    # Activity-credit: a signal's OOS edge is credited only proportional to how
    # much it actually participated. A flat signal's vs_buy_hold 'edge' is just
    # cash outperforming a losing market (not tradeable), so it is discounted to
    # ~0 - gradient pressure to trade, not just a prompt nudge.
    base.oos_activity = signal_market_activity(signal_fn, oos_df, parameters or {})
    base.exposure_factor = (
        max(0.0, min(1.0, base.oos_activity / cfg.activity_floor))
        if cfg.activity_floor > 0 else 1.0
    )
    candidate_fitness = base.oos_vs_buyhold * base.exposure_factor - base.overfit_penalty

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
    if candidate_fitness < cfg.min_fitness:
        reasons.append(
            f"fitness={candidate_fitness:.1f}<{cfg.min_fitness} "
            f"(overfit-adjusted edge not positive; IS>>OOS)"
        )
    if reasons:
        base.rejection_reason = "; ".join(reasons)
        return base

    # 6) Final overfit-adjusted OOS edge (behavioural labels were set in step 1)
    base.evaluated = True
    base.fitness_score = candidate_fitness
    return base


def evaluate_fitness_two_window(signal_fn: SignalFn, parameters: Dict[str, Any],
                                df: pd.DataFrame, edge_type: str,
                                config: Optional[FitnessConfig] = None,
                                candidate_id: str = "") -> FitnessResult:
    """Stricter fitness for evolved-code programs: must profit on TWO OOS windows.

    Splits chronologically into IS (50%) / OOS1 (30%) / OOS2 (20%). A candidate
    passes only if BOTH OOS windows are independently profitable (and trade
    enough). The fitness is the WORST window's edge minus the overfit penalty
    (IS edge vs average OOS edge) — conservative, exactly the extra insurance
    Phase 4's maximally-expressive search needs.
    """
    cfg = config or FitnessConfig()
    base = FitnessResult(
        evaluated=False, fitness_score=float("-inf"),
        oos_vs_buyhold=0.0, is_vs_buyhold=0.0, overfit_gap=0.0,
        overfit_penalty=0.0, n_trades_is=0, n_trades_oos=0,
        validation_score=1.0, candidate_id=candidate_id,
    )

    ok, reason = check_signal_correctness(signal_fn, df, parameters or {},
                                          probe_window=cfg.probe_window)
    if not ok:
        base.rejection_reason = f"correctness: {reason}"
        return base

    # Behavioural niche labels: computed HERE (after correctness guarantees the
    # signal is safe to probe) so REJECTED candidates carry them too - the funnel
    # needs to show WHAT kind of signal is failing, not just that it failed.
    base.family_label = classify_signal_family(signal_fn, df, parameters or {})
    base.regime_label = classify_active_regime(signal_fn, df, parameters or {})

    n = len(df)
    cut1 = int(n * 0.5)
    cut2 = int(n * 0.8)
    is_df = df.iloc[:cut1]
    oos1_df = df.iloc[cut1:cut2]
    oos2_df = df.iloc[cut2:]

    seed = cfg.random_seed
    is_m = run_backtest(signal_fn, parameters, is_df, edge_type, seed=seed)
    o1 = run_backtest(signal_fn, parameters, oos1_df, edge_type, seed=seed + 1)
    o2 = run_backtest(signal_fn, parameters, oos2_df, edge_type, seed=seed + 2)

    is_edge = float(is_m.get("vs_buy_hold_usdt", 0.0))
    o1_edge = float(o1.get("vs_buy_hold_usdt", 0.0))
    o2_edge = float(o2.get("vs_buy_hold_usdt", 0.0))
    o1_profit = float(o1.get("total_profit_usdt", 0.0))
    o2_profit = float(o2.get("total_profit_usdt", 0.0))
    o1_trades = int(o1.get("total_trades", 0))
    o2_trades = int(o2.get("total_trades", 0))

    base.is_vs_buyhold = is_edge
    base.oos_vs_buyhold = min(o1_edge, o2_edge)            # conservative
    base.n_trades_is = int(is_m.get("total_trades", 0))
    base.n_trades_oos = min(o1_trades, o2_trades)

    avg_oos = (o1_edge + o2_edge) / 2.0
    base.overfit_gap = max(0.0, is_edge - avg_oos)
    base.overfit_penalty = base.overfit_gap * cfg.overfit_penalty_weight
    # Activity-credit (see evaluate_fitness): credit the OOS edge by market
    # participation across both OOS windows, so a dormant signal cannot ride the
    # cash-beats-losing-buyhold artifact to a positive fitness.
    base.oos_activity = (
        signal_market_activity(signal_fn, oos1_df, parameters or {}) +
        signal_market_activity(signal_fn, oos2_df, parameters or {})
    ) / 2.0
    base.exposure_factor = (
        max(0.0, min(1.0, base.oos_activity / cfg.activity_floor))
        if cfg.activity_floor > 0 else 1.0
    )
    candidate_fitness = base.oos_vs_buyhold * base.exposure_factor - base.overfit_penalty
    base.metrics_is = is_m
    base.metrics_oos = {"oos1": o1, "oos2": o2}

    # Gates on BOTH windows
    reasons = []
    if cfg.require_absolute_oos_profit and o1_profit <= 0:
        reasons.append(f"oos1_total_profit={o1_profit:.2f}<=0")
    if cfg.require_absolute_oos_profit and o2_profit <= 0:
        reasons.append(f"oos2_total_profit={o2_profit:.2f}<=0")
    if o1_trades < cfg.min_trades:
        reasons.append(f"oos1_trades={o1_trades}<{cfg.min_trades}")
    if o2_trades < cfg.min_trades:
        reasons.append(f"oos2_trades={o2_trades}<{cfg.min_trades}")
    if cfg.require_beat_buyhold_oos and (o1_edge <= 0 or o2_edge <= 0):
        reasons.append("oos_edge_not_positive_on_both_windows")
    if candidate_fitness < cfg.min_fitness:
        reasons.append(
            f"fitness={candidate_fitness:.1f}<{cfg.min_fitness} "
            f"(overfit-adjusted edge not positive; IS>>OOS)"
        )
    if reasons:
        base.rejection_reason = "; ".join(reasons)
        return base

    # Behavioural niche labels were computed right after the correctness gate
    # (above), so they are already populated for this passing candidate too.
    base.evaluated = True
    base.fitness_score = candidate_fitness
    return base
