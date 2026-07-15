"""Tests for the DEX fitness evaluator (slate_core.dex.evolution.dex_fitness)."""
import numpy as np
import pandas as pd

from slate_core.dex.evolution.dex_fitness import evaluate_dex_fitness, evaluate_dex_mm_fitness
from slate_core.discovery.evolution.fitness_evaluator import FitnessResult


def _syn_df(n=120, seed=0):
    rng = np.random.RandomState(seed)
    rets = 0.002 + rng.normal(0, 0.01, n)            # gentle uptrend + noise
    close = 100.0 * np.exp(np.cumsum(rets))
    high = close * (1 + np.abs(rng.normal(0, 0.004, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.004, n)))
    open_ = np.concatenate([[close[0]], close[:-1]])
    idx = pd.date_range("2026-01-01", periods=n, freq="1h")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=idx)


def test_dex_fitness_rejects_flat_signal():
    df = _syn_df()
    res = evaluate_dex_fitness(lambda d, i, p: 0, df, candidate_id="flat")
    assert isinstance(res, FitnessResult)
    assert res.evaluated is False
    assert res.rejection_reason                        # 0 trades -> rejected


def test_dex_fitness_runs_and_labels_momentum():
    df = _syn_df()
    mom = lambda d, i, p: 1 if d["close"].iloc[i] > d["ema_20"].iloc[i] else -1
    res = evaluate_dex_fitness(mom, df, candidate_id="mom")
    assert isinstance(res, FitnessResult)
    assert res.family_label == "" or res.family_label in {"momentum", "mean_reversion", "other"}


def test_dex_mm_fitness_runs_and_labels_market_maker():
    df = _syn_df()
    qf = lambda st: (15.0, 2.0, 0.5)                     # fixed quote params
    res = evaluate_dex_mm_fitness(qf, df, candidate_id="mm")
    assert isinstance(res, FitnessResult)
    assert res.family_label == "market_maker"


def test_make_walkforward_folds_disjoint_and_anchored():
    import pandas as pd
    from slate_core.dex.evolution.dex_fitness import make_walkforward_folds
    df = pd.DataFrame({"close": range(300)},
                      index=pd.date_range("2026-01-01", periods=300, freq="1h"))
    folds = make_walkforward_folds(df, n_folds=5)
    assert len(folds) == 5
    for is_df, oos_df in folds:
        assert len(is_df) >= 30 and len(oos_df) >= 30
        assert is_df.index[-1] < oos_df.index[0]         # anchored: IS ends before OOS


def test_dex_fitness_walkforward_rejects_flat_and_runs():
    df = _syn_df(500)                                     # big enough for 5 folds
    # flat signal -> fails every fold's gates
    flat = evaluate_dex_fitness(lambda d, i, p: 0, df, candidate_id="wf_flat",
                                validation="walkforward")
    assert isinstance(flat, FitnessResult) and flat.evaluated is False
    # momentum runs across all folds (strict; not asserting a pass)
    mom = lambda d, i, p: 1 if d["close"].iloc[i] > d["ema_20"].iloc[i] else -1
    res = evaluate_dex_fitness(mom, df, candidate_id="wf_mom", validation="walkforward")
    assert isinstance(res, FitnessResult)
