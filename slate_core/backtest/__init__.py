"""SLATE backtest package.

SOURCE OF TRUTH for strategy evaluation: ``slate_core.backtest.honest`` — the
no-lookahead, brutal-real-cost evaluator (tested; 13 regression tests in
``test_honest_backtester.py``). Use ``honest.backtest`` / ``honest.walk_forward``
for any strategy evaluation. The legacy ``engine.BacktestEngine`` (Volume
Imbalance only) and ``discovery.mega_sweep.fast_backtest`` (now patched to match
honest.backtest) must not be treated as independent evaluators.

Honest evaluator provenance: built 2026-07-20 after the +3.43 regime-switch
Sharpe was shown to be a 1-bar-lookahead artifact (see ``verify_lookahead.py``,
``HONEST_DISCOVERY_REPORT.md``).
"""
from .engine import (
    BacktestEngine,
    BacktestConfig,
    BacktestResults,
    Trade,
    run_backtest,
)
# Canonical honest evaluator — re-exported so `from slate_core.backtest import backtest` works.
from .honest import backtest, walk_forward, split_is_oos, CEX, DEX, DEX_WHALE, bars_per_year_from_index
# Realism layer (Tier 1-3): event-driven engine, validation, calibration.
from .event_engine import EventBacktester
from .validation import cscv_pbo, cpcv, deflated_sharpe
from .calibration import calibrate, simulate_live_fills, LiveFill
from .realism import sqrt_impact_bps, capacity_curve

__all__ = [
    "BacktestEngine", "BacktestConfig", "BacktestResults", "Trade", "run_backtest",
    # honest evaluator (source of truth) + realism layer
    "backtest", "walk_forward", "split_is_oos", "CEX", "DEX", "DEX_WHALE",
    "bars_per_year_from_index",
    "EventBacktester", "cscv_pbo", "cpcv", "deflated_sharpe",
    "calibrate", "simulate_live_fills", "LiveFill", "sqrt_impact_bps", "capacity_curve",
]
