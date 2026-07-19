"""Structure-level fitness for GP market-maker individuals.

Compiles an individual's three expression trees to a sandboxed `policy_fn` (via
`signal_sandbox.compile_function`), backtests it walk-forward on the L2 stream
(absolute net profit required in EVERY fold + min fills), and scores behavioral
NOVELTY against textbook symmetric-spread archetype equity curves — so the
search is pushed *away* from the public/arbitraged archetype. LLM-free.
"""
from __future__ import annotations

import statistics
from typing import List, Optional, Sequence

from slate_core.discovery.evolution.fitness_evaluator import FitnessConfig, FitnessResult
from slate_core.discovery.evolution.novelty import novelty_score
from slate_core.discovery.evolution.signal_sandbox import compile_function
from slate_core.dex.backtester.economics import HLFeeSchedule
from slate_core.dex.backtester.mm_tick_backtester import MMPolicy, backtest_mm
from slate_core.dex.evolution.param_optimizer import _snap_oos_windows, mm_vol_regime
from slate_core.dex.evolution.gp.genome import Individual, complexity, policy_source

WALKFORWARD_FOLDS = 5


def textbook_archetype_curves(snaps: Sequence[dict], schedule=None,
                              spreads=(5.0, 10.0, 30.0)) -> List[List[float]]:
    """Pre-compute textbook symmetric-spread MM equity curves (the behavior to
    push AWAY from via novelty). Computed once per run and passed to evaluate()."""
    curves = []
    for h in spreads:
        r = backtest_mm(snaps, MMPolicy(half_spread_bps=h, inv_skew_bps=0.0, size=0.5),
                        schedule=schedule)
        if r.equity_curve:
            curves.append(r.equity_curve)
    return curves


def evaluate_gp_tree(ind: Individual, snaps: Sequence[dict],
                     config: Optional[FitnessConfig] = None,
                     archetype_curves: Optional[Sequence[Sequence[float]]] = None,
                     schedule: Optional[HLFeeSchedule] = None,
                     n_folds: int = WALKFORWARD_FOLDS,
                     max_inventory: float = 2.0,
                     max_complexity: int = 400,
                     max_half_spread_bps: float = 3.0,
                     max_inv_skew_bps: float = 15.0,
                     adverse_selection_bps: float = 0.6) -> FitnessResult:
    """Walk-forward tick-backtest fitness + novelty for a GP individual.

    Returns a FitnessResult where:
      oos_vs_buyhold = worst-fold net PnL (the profit objective),
      metrics_oos['novelty_score'] = behavioral novelty vs textbook archetypes,
      metrics_oos['complexity']    = AST-node count (for the cap).
    """
    cfg = config or FitnessConfig()
    base = FitnessResult(
        evaluated=False, fitness_score=float("-inf"),
        oos_vs_buyhold=0.0, is_vs_buyhold=0.0, overfit_gap=0.0,
        overfit_penalty=0.0, n_trades_is=0, n_trades_oos=0,
        validation_score=1.0, candidate_id="",
        family_label="market_maker_gp", regime_label=mm_vol_regime(list(snaps)),
    )

    cplx = complexity(ind)
    if cplx > max_complexity:
        base.rejection_reason = f"too_complex:{cplx}>{max_complexity}"
        return base

    try:
        fn = compile_function(policy_source(ind), "policy_fn")
    except Exception as exc:  # noqa: BLE001 - SandboxError or syntax
        base.rejection_reason = f"compile:{str(exc)[:80]}"
        return base

    windows = _snap_oos_windows(list(snaps), n_folds)
    if len(windows) < 3:
        base.rejection_reason = f"too_few_folds ({len(windows)})"
        return base

    pnls: List[float] = []
    fills: List[int] = []
    acts: List[float] = []
    worst_curve: List[float] = []
    worst_pnl = float("inf")
    for w in windows:
        r = backtest_mm(w, fn, schedule=schedule, max_inventory=max_inventory,
                        max_half_spread_bps=max_half_spread_bps,
                        max_inv_skew_bps=max_inv_skew_bps,
                        adverse_selection_bps=adverse_selection_bps)
        pnls.append(r.total_pnl)
        fills.append(r.maker_fills)
        acts.append(r.bars_in_market / max(1, r.n_snapshots))
        if r.total_pnl < worst_pnl:
            worst_pnl = r.total_pnl
            worst_curve = r.equity_curve

    base.is_vs_buyhold = statistics.median(pnls)
    base.oos_vs_buyhold = min(pnls)                  # conservative: worst fold
    base.n_trades_oos = min(fills)
    base.oos_activity = statistics.median(acts)
    base.overfit_gap = max(0.0, base.is_vs_buyhold - base.oos_vs_buyhold)
    base.overfit_penalty = base.overfit_gap * cfg.overfit_penalty_weight

    # Plausibility guard: real MM makes single-digit %/YEAR; a single fold
    # (~hours of L2) realizing >5% is a backtester artifact (a policy exploiting
    # the snapshot fill model's optimistic adverse selection), not alpha. Reject
    # outright so artifacts can't corrupt the population.
    _capital = 10_000.0
    _plausibility = 0.05                              # 5%/fold is already ~100x realistic
    if any(abs(p) > _plausibility * _capital for p in pnls):
        base.rejection_reason = (
            f"implausible_backtest_artifact: |fold_pnl|>{_plausibility*_capital:.0f}")
        base.metrics_oos = {"fold_pnls": pnls, "fold_fills": fills,
                            "novelty_score": 1.0, "complexity": cplx,
                            "gate_passed": False, "search_score": float("-inf")}
        base.fitness_score = float("-inf")
        return base

    nov = novelty_score(worst_curve, archetype_curves) if (archetype_curves and worst_curve) else 1.0
    exposure = (max(0.0, min(1.0, base.oos_activity / cfg.activity_floor))
                if cfg.activity_floor > 0 else 1.0)
    candidate_fitness = base.oos_vs_buyhold * exposure - base.overfit_penalty

    # Gate (deployment bar): absolute profit in EVERY fold + min fills + min fitness.
    reasons: List[str] = []
    if cfg.require_absolute_oos_profit:
        for i, p in enumerate(pnls):
            if p <= 0:
                reasons.append(f"fold{i}_pnl={p:.2f}<=0")
    for i, f in enumerate(fills):
        if f < cfg.min_trades:
            reasons.append(f"fold{i}_fills={f}<{cfg.min_trades}")
    if candidate_fitness < cfg.min_fitness:
        reasons.append(f"fitness={candidate_fitness:.2f}<{cfg.min_fitness}")
    gate_passed = not reasons

    base.metrics_oos = {"fold_pnls": pnls, "fold_fills": fills,
                        "novelty_score": float(nov), "complexity": cplx,
                        "worst_fold_pnl": base.oos_vs_buyhold,
                        "gate_passed": bool(gate_passed),
                        "search_score": float(candidate_fitness)}
    # Smooth fitness (can be negative) drives EVOLUTION (so the GP can climb);
    # `evaluated`/gate_passed is the DEPLOYMENT bar. fitness_score is always finite
    # so MAP-Elites can accumulate a population even before anything clears the gate.
    base.fitness_score = float(candidate_fitness)
    base.evaluated = bool(gate_passed)
    base.rejection_reason = "" if gate_passed else "; ".join(reasons)
    return base


__all__ = ["evaluate_gp_tree", "textbook_archetype_curves", "WALKFORWARD_FOLDS"]
