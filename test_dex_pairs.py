"""Tests for the pairs (stat-arb) backtester + fitness (P4 multi-leg)."""
import pandas as pd

from slate_core.dex.backtester.pairs_backtester import PairsBacktester, PairsBacktestConfig
from slate_core.dex.evolution.dex_fitness import evaluate_dex_pairs_fitness
from slate_core.dex.strategies.pairs import spread_zscore_signal
from slate_core.discovery.evolution.fitness_evaluator import FitnessResult


def _pair_df(step_a, step_b, n=60):
    idx = pd.date_range("2026-01-01", periods=n, freq="1h")
    dfA = pd.DataFrame({"close": [100.0 + step_a * k for k in range(n)]}, index=idx)
    dfB = pd.DataFrame({"close": [100.0 + step_b * k for k in range(n)]}, index=idx)
    return dfA, dfB


def test_pairs_flat_signal_no_trades_no_pnl():
    dfA, dfB = _pair_df(0.5, 0.1)
    r = PairsBacktester(PairsBacktestConfig(warmup=5)).backtest(lambda a, b, i: 0, dfA, dfB)
    assert r.total_trades == 0 and r.total_pnl == 0.0


def test_pairs_long_spread_profits_when_a_outperforms():
    # A rises faster than B -> a constant long-spread (long A / short B) profits.
    dfA, dfB = _pair_df(0.5, 0.1)
    r = PairsBacktester(PairsBacktestConfig(warmup=5, notional=1000.0)).backtest(
        lambda a, b, i: 1, dfA, dfB)
    assert r.total_trades >= 1
    assert r.total_pnl > 0                    # spread PnL net of fees
    assert r.total_fees > 0                   # paid taker on both legs


def test_dex_pairs_fitness_runs_and_labels():
    dfA, dfB = _pair_df(0.5, 0.1, n=300)
    res = evaluate_dex_pairs_fitness(spread_zscore_signal, dfA, dfB, candidate_id="pairs")
    assert isinstance(res, FitnessResult)
    assert res.family_label == "pairs"
