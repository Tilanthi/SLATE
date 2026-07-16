"""LP fitness evaluator — reuses FitnessResult/FitnessConfig from the crown jewel.

Two-window IS/OOS1/OOS2 split, gates on absolute profit + min_trades +
min_fitness. Baseline = holding stablecoins (~0 return), so oos_vs_buyhold
= total_pnl (no buy-and-hold benchmark for an LP yield strategy).
"""
from __future__ import annotations

import math
from typing import Callable, Optional

from slate_core.discovery.evolution.fitness_evaluator import FitnessConfig, FitnessResult
from slate_core.amm.lp_backtester import LPBacktester, LPBacktestConfig

LPFn = Callable[..., Optional[dict]]


def check_lp_correctness(lp_fn: LPFn, df, probe_window: int = 30):
    """Probe lp_fn over a short window; reject on crash or invalid action."""
    for i in range(10, min(probe_window, len(df))):
        bar = df.iloc[i]
        try:
            result = lp_fn(bar)
        except Exception as exc:
            return False, f"exception at bar {i}: {exc}"
        if result is None:
            continue
        action = result.get("action", "HOLD") if isinstance(result, dict) else "HOLD"
        if action not in ("ENTER", "EXIT", "HOLD"):
            return False, f"invalid action {action!r} at bar {i}"
        rb = result.get("range_bps", 50.0) if isinstance(result, dict) else 50.0
        if not math.isfinite(float(rb)) or float(rb) <= 0 or float(rb) > 10000:
            return False, f"invalid range_bps {rb} at bar {i}"
    return True, ""


def evaluate_lp_fitness(lp_fn: LPFn, df, config: Optional[FitnessConfig] = None,
                      candidate_id: str = "") -> FitnessResult:
    """Two-window LP fitness: IS / OOS1 / OOS2. Gates on absolute profit."""
    cfg = config or FitnessConfig()
    base = FitnessResult(
        evaluated=False, fitness_score=float("-inf"),
        oos_vs_buyhold=0.0, is_vs_buyhold=0.0, overfit_gap=0.0,
        overfit_penalty=0.0, n_trades_is=0, n_trades_oos=0,
        validation_score=1.0, candidate_id=candidate_id,
        family_label="lp", regime_label="",
    )

    ok, reason = check_lp_correctness(lp_fn, df, probe_window=cfg.probe_window)
    if not ok:
        base.rejection_reason = f"correctness: {reason}"
        return base
    base.regime_label = "stablecoin"

    n = len(df)
    if n < 100:
        base.rejection_reason = "too_few_bars"
        return base
    cut1, cut2 = int(n * 0.5), int(n * 0.8)
    bt = LPBacktester(LPBacktestConfig())
    is_r = bt.backtest(lp_fn, df.iloc[:cut1])
    o1 = bt.backtest(lp_fn, df.iloc[cut1:cut2])
    o2 = bt.backtest(lp_fn, df.iloc[cut2:])

    base.is_vs_buyhold = is_r.apy * 100  # APY% as the headline (time-normalized)
    base.oos_vs_buyhold = min(o1.apy, o2.apy) * 100  # conservative: worst OOS APY%
    base.n_trades_is = is_r.n_rebalances
    base.n_trades_oos = min(o1.n_rebalances, o2.n_rebalances)
    base.oos_activity = (o1.bars_in_range / max(1, o1.n_bars)
                         + o2.bars_in_range / max(1, o2.n_bars)) / 2.0
    avg_oos = (o1.apy + o2.apy) / 2.0 * 100
    base.overfit_gap = max(0.0, is_r.apy * 100 - avg_oos)
    base.overfit_penalty = base.overfit_gap * cfg.overfit_penalty_weight
    exposure = (max(0.0, min(1.0, base.oos_activity / cfg.activity_floor))
                if cfg.activity_floor > 0 else 1.0)
    base.exposure_factor = exposure
    candidate_fitness = base.oos_vs_buyhold * exposure - base.overfit_penalty
    base.metrics_is = is_r.to_dict()
    base.metrics_oos = {"oos1": o1.to_dict(), "oos2": o2.to_dict()}

    reasons = []
    if cfg.require_absolute_oos_profit and o1.final_equity - 10_000 <= 0:
        reasons.append(f"oos1_pnl={o1.final_equity - 10_000:.2f}<=0")
    if cfg.require_absolute_oos_profit and o2.final_equity - 10_000 <= 0:
        reasons.append(f"oos2_pnl={o2.final_equity - 10_000:.2f}<=0")
    if o1.n_rebalances < cfg.min_trades:
        reasons.append(f"oos1_rebalances={o1.n_rebalances}<{cfg.min_trades}")
    if o2.n_rebalances < cfg.min_trades:
        reasons.append(f"oos2_rebalances={o2.n_rebalances}<{cfg.min_trades}")
    if candidate_fitness < cfg.min_fitness:
        reasons.append(f"fitness={candidate_fitness:.1f}<{cfg.min_fitness}")
    if reasons:
        base.rejection_reason = "; ".join(reasons)
        return base
    base.evaluated = True
    base.fitness_score = candidate_fitness
    return base
