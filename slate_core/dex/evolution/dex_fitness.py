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

import math
import statistics
from typing import Callable, List, Optional, Tuple

import numpy as np

from slate_core.discovery.evolution.fitness_evaluator import (
    FitnessConfig, FitnessResult, check_signal_correctness,
    classify_signal_family, classify_active_regime,
)
from slate_core.discovery.perpetual_futures_backtest import add_signal_indicators
from slate_core.dex.backtester.dex_backtester import DexBacktester, DexBacktestConfig
from slate_core.dex.strategies.action import BarState
from slate_core.dex.strategies.directional import DirectionalStrategy
from slate_core.dex.strategies.market_maker import MarketMakerStrategy, _parse_quote

SignalFn = Callable[..., int]


def _adapt(signal_fn: SignalFn, tif: str = "Market", edge_bps: float = 5.0) -> DirectionalStrategy:
    """Wrap a CEX-form signal_fn(df,i,params) into a DirectionalStrategy that
    reads the backtester's BarState (history, i). Default Market execution so the
    signal is reliably expressed (Alo rarely fills on 1h data → 0-trade evaluations)."""
    return DirectionalStrategy(lambda st: signal_fn(st.history, st.i, {}),
                               tif=tif, edge_bps=edge_bps)


def _buyhold_pnl(window) -> float:
    if len(window) < 2:
        return 0.0
    return float(window["close"].iloc[-1] - window["close"].iloc[0])


# ---------------------------------------------------------------------------
# Walk-forward (multi-fold) validation — a stronger overfit defense than one
# IS/OOS split. A signal must profit on several INDEPENDENT OOS folds (anchored:
# each fold trains on all data up to its block, tests on the next block), so a
# curve-fit to one regime fails elsewhere. Strict: ALL folds must clear the gates.
# ---------------------------------------------------------------------------

WALKFORWARD_FOLDS = 5


def make_walkforward_folds(df, n_folds: int = WALKFORWARD_FOLDS
                           ) -> List[Tuple[object, object]]:
    """Anchored walk-forward folds: fold i trains on df[:b_{i+1}], tests on the next
    block. Returns n_folds (is_df, oos_df) pairs whose OOS blocks are disjoint and
    cover the tail of the series."""
    n = len(df)
    n_blocks = n_folds + 1
    bounds = [int(n * k / n_blocks) for k in range(n_blocks + 1)]
    folds = []
    for i in range(n_folds):
        is_df = df.iloc[: bounds[i + 1]]          # anchored: all data up to here
        oos_df = df.iloc[bounds[i + 1]: bounds[i + 2]]
        if len(is_df) >= 30 and len(oos_df) >= 30:
            folds.append((is_df, oos_df))
    return folds


def _walkforward_eval(strat, bt, df, cfg, base) -> FitnessResult:
    folds = make_walkforward_folds(df, WALKFORWARD_FOLDS)
    if len(folds) < 3:
        base.rejection_reason = "too_few_folds"
        return base
    is_edges, oos_edges, oos_pnls, oos_trades, oos_acts = [], [], [], [], []
    for is_df, oos_df in folds:
        is_r = bt.backtest(strat, is_df)
        oos_r = bt.backtest(strat, oos_df)
        is_edges.append(is_r.total_pnl - _buyhold_pnl(is_df))
        oos_edges.append(oos_r.total_pnl - _buyhold_pnl(oos_df))
        oos_pnls.append(oos_r.total_pnl)
        oos_trades.append(oos_r.total_trades)
        oos_acts.append(oos_r.bars_in_market / max(1, oos_r.n_bars))
    base.is_vs_buyhold = statistics.median(is_edges)
    base.oos_vs_buyhold = min(oos_edges)            # conservative: worst fold
    base.n_trades_oos = min(oos_trades)
    base.oos_activity = statistics.median(oos_acts)
    avg_is, avg_oos = statistics.mean(is_edges), statistics.mean(oos_edges)
    base.overfit_gap = max(0.0, avg_is - avg_oos)
    base.overfit_penalty = base.overfit_gap * cfg.overfit_penalty_weight
    exposure = (max(0.0, min(1.0, base.oos_activity / cfg.activity_floor))
                if cfg.activity_floor > 0 else 1.0)
    base.exposure_factor = exposure
    candidate_fitness = base.oos_vs_buyhold * exposure - base.overfit_penalty
    base.metrics_oos = {"fold_oos_edges": oos_edges, "fold_oos_pnls": oos_pnls}

    # STRICT: every fold must clear the gates independently.
    reasons = []
    for i, pnl in enumerate(oos_pnls):
        if cfg.require_absolute_oos_profit and pnl <= 0:
            reasons.append(f"fold{i}_total_profit={pnl:.2f}<=0")
    for i, t in enumerate(oos_trades):
        if t < cfg.min_trades:
            reasons.append(f"fold{i}_trades={t}<{cfg.min_trades}")
    if cfg.require_beat_buyhold_oos and min(oos_edges) <= 0:
        reasons.append("oos_edge_not_positive_all_folds")
    if candidate_fitness < cfg.min_fitness:
        reasons.append(f"fitness={candidate_fitness:.1f}<{cfg.min_fitness}")
    if reasons:
        base.rejection_reason = "; ".join(reasons)
        return base
    base.evaluated = True
    base.fitness_score = candidate_fitness
    return base


def evaluate_dex_fitness(signal_fn: SignalFn, df, config: Optional[FitnessConfig] = None,
                         candidate_id: str = "",
                         validation: str = "two_window") -> FitnessResult:
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
    if validation == "walkforward":
        return _walkforward_eval(strat, bt, df, cfg, base)
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


# ---------------------------------------------------------------------------
# Market-maker fitness: evolve the QUOTING logic (quote_fn), not a directional
# signal. Same two-window + overfit + activity + min_fitness discipline.
# ---------------------------------------------------------------------------

def _df_vol_regime(df) -> str:
    rets = np.diff(np.log(df["close"].astype(float).values))
    rv = float(np.std(rets)) if len(rets) > 2 else 0.0
    if rv < 0.01:
        return "low_vol"
    if rv < 0.02:
        return "med_vol"
    return "high_vol"


def check_quote_correctness(quote_fn, df, probe_window: int = 30):
    """Probe quote_fn over a short window; reject if it crashes or returns
    non-finite / out-of-range quote params."""
    start = min(probe_window, max(0, len(df) - 1))
    for i in range(20, start):
        row = df.iloc[i]
        state = BarState(i=i, open=float(row["open"]), high=float(row["high"]),
                         low=float(row["low"]), close=float(row["close"]),
                         history=df.iloc[: i + 1])
        try:
            params = quote_fn(state)
        except Exception as exc:  # noqa: BLE001
            return False, f"exception at bar {i}: {exc}"
        if params is None:
            continue
        half, skew, size = _parse_quote(params)
        if not (math.isfinite(half) and math.isfinite(skew) and math.isfinite(size)):
            return False, f"non-finite quote at bar {i}"
        if not (1.0 <= half <= 1000.0 and 0.0 <= size <= 1e6):
            return False, f"out-of-range quote at bar {i}: half={half}, size={size}"
    return True, ""


def evaluate_dex_mm_fitness(quote_fn, df, config: Optional[FitnessConfig] = None,
                            candidate_id: str = "") -> FitnessResult:
    cfg = config or FitnessConfig()
    base = FitnessResult(
        evaluated=False, fitness_score=float("-inf"),
        oos_vs_buyhold=0.0, is_vs_buyhold=0.0, overfit_gap=0.0,
        overfit_penalty=0.0, n_trades_is=0, n_trades_oos=0,
        validation_score=1.0, candidate_id=candidate_id,
        family_label="market_maker", regime_label="",
    )
    df = add_signal_indicators(df.copy())
    ok, reason = check_quote_correctness(quote_fn, df, probe_window=cfg.probe_window)
    if not ok:
        base.rejection_reason = f"correctness: {reason}"
        return base
    base.regime_label = _df_vol_regime(df)

    n = len(df)
    if n < 60:
        base.rejection_reason = "too_few_bars"
        return base
    cut1, cut2 = int(n * 0.5), int(n * 0.8)
    is_df, oos1, oos2 = df.iloc[:cut1], df.iloc[cut1:cut2], df.iloc[cut2:]
    bt = DexBacktester(DexBacktestConfig(warmup=min(cfg.probe_window, 20),
                                         funding_interval_bars=0))
    strat = MarketMakerStrategy(quote_fn=quote_fn)
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
    if candidate_fitness < cfg.min_fitness:
        reasons.append(f"fitness={candidate_fitness:.1f}<{cfg.min_fitness}")
    if reasons:
        base.rejection_reason = "; ".join(reasons)
        return base
    base.evaluated = True
    base.fitness_score = candidate_fitness
    return base
