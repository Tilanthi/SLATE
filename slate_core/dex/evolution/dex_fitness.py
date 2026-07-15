"""DEX fitness evaluator.

Reuses the CEX FitnessResult/FitnessConfig + the correctness/label machinery
(check_signal_correctness, classify_signal_family/regime), but evaluates via the
DEX bar-level backtester with Hyperliquid economics. The evolved unit is a
CEX-form signal_fn(df, i, params) -> {-1,0,1} (so the sandbox/complexity-cap/
SEARCH-REPLACE machinery is reused verbatim), wrapped in DirectionalStrategy so
entries/exits route through maker orders. Two-window (IS/OOS1/OOS2) + overfit
penalty + activity-credit + min_fitness gate, mirroring the CEX fitness contract
so the funnel (verdict_log) and chokepoint (ProgramDatabase) work unchanged.
"""
from __future__ import annotations

from typing import Callable, Optional

from slate_core.discovery.evolution.fitness_evaluator import (
    FitnessConfig, FitnessResult, check_signal_correctness,
    classify_signal_family, classify_active_regime,
)
from slate_core.discovery.perpetual_futures_backtest import add_signal_indicators
from slate_core.dex.backtester.dex_backtester import DexBacktester, DexBacktestConfig
from slate_core.dex.strategies.directional import DirectionalStrategy

SignalFn = Callable[..., int]


def _adapt(signal_fn: SignalFn, tif: str = "Alo", edge_bps: float = 5.0) -> DirectionalStrategy:
    """Wrap a CEX-form signal_fn(df,i,params) into a DirectionalStrategy that
    reads the backtester's BarState (history, i)."""
    return DirectionalStrategy(lambda st: signal_fn(st.history, st.i, {}),
                               tif=tif, edge_bps=edge_bps)


def _buyhold_pnl(window) -> float:
    if len(window) < 2:
        return 0.0
    return float(window["close"].iloc[-1] - window["close"].iloc[0])


def evaluate_dex_fitness(signal_fn: SignalFn, df, config: Optional[FitnessConfig] = None,
                         candidate_id: str = "") -> FitnessResult:
    cfg = config or FitnessConfig()
    base = FitnessResult(
        evaluated=False, fitness_score=float("-inf"),
        oos_vs_buyhold=0.0, is_vs_buyhold=0.0, overfit_gap=0.0,
        overfit_penalty=0.0, n_trades_is=0, n_trades_oos=0,
        validation_score=1.0, candidate_id=candidate_id,
    )

    df = add_signal_indicators(df.copy())            # inject ema_20 etc. for evolved signals
    ok, reason = check_signal_correctness(signal_fn, df, {}, probe_window=cfg.probe_window)
    if not ok:
        base.rejection_reason = f"correctness: {reason}"
        return base
    base.family_label = classify_signal_family(signal_fn, df, {})
    base.regime_label = classify_active_regime(signal_fn, df, {})

    n = len(df)
    if n < 60:
        base.rejection_reason = "too_few_bars"
        return base
    cut1, cut2 = int(n * 0.5), int(n * 0.8)
    is_df, oos1, oos2 = df.iloc[:cut1], df.iloc[cut1:cut2], df.iloc[cut2:]

    bt = DexBacktester(DexBacktestConfig(warmup=min(cfg.probe_window, 20),
                                         funding_interval_bars=0))
    strat = _adapt(signal_fn)
    is_r = bt.backtest(strat, is_df)
    o1 = bt.backtest(strat, oos1)
    o2 = bt.backtest(strat, oos2)

    is_edge = is_r.total_pnl - _buyhold_pnl(is_df)
    o1_edge = o1.total_pnl - _buyhold_pnl(oos1)
    o2_edge = o2.total_pnl - _buyhold_pnl(oos2)
    base.is_vs_buyhold = is_edge
    base.oos_vs_buyhold = min(o1_edge, o2_edge)
    base.n_trades_is = is_r.total_trades
    base.n_trades_oos = min(o1.total_trades, o2.total_trades)
    base.oos_activity = (o1.bars_in_market / max(1, o1.n_bars)
                         + o2.bars_in_market / max(1, o2.n_bars)) / 2.0

    avg_oos = (o1_edge + o2_edge) / 2.0
    base.overfit_gap = max(0.0, is_edge - avg_oos)
    base.overfit_penalty = base.overfit_gap * cfg.overfit_penalty_weight
    exposure = (max(0.0, min(1.0, base.oos_activity / cfg.activity_floor))
                if cfg.activity_floor > 0 else 1.0)
    base.exposure_factor = exposure
    candidate_fitness = base.oos_vs_buyhold * exposure - base.overfit_penalty
    base.metrics_is = is_r.to_dict()
    base.metrics_oos = {"oos1": o1.to_dict(), "oos2": o2.to_dict()}

    reasons = []
    if cfg.require_absolute_oos_profit and o1.total_pnl <= 0:
        reasons.append(f"oos1_total_profit={o1.total_pnl:.2f}<=0")
    if cfg.require_absolute_oos_profit and o2.total_pnl <= 0:
        reasons.append(f"oos2_total_profit={o2.total_pnl:.2f}<=0")
    if o1.total_trades < cfg.min_trades:
        reasons.append(f"oos1_trades={o1.total_trades}<{cfg.min_trades}")
    if o2.total_trades < cfg.min_trades:
        reasons.append(f"oos2_trades={o2.total_trades}<{cfg.min_trades}")
    if cfg.require_beat_buyhold_oos and (o1_edge <= 0 or o2_edge <= 0):
        reasons.append("oos_edge_not_positive_both_windows")
    if candidate_fitness < cfg.min_fitness:
        reasons.append(f"fitness={candidate_fitness:.1f}<{cfg.min_fitness}")
    if reasons:
        base.rejection_reason = "; ".join(reasons)
        return base

    base.evaluated = True
    base.fitness_score = candidate_fitness
    return base
