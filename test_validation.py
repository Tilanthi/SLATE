"""Tests for the CPCV / PBO / DSR validation suite."""
import numpy as np
import pytest

from slate_core.backtest.validation import cscv_pbo, cpcv, deflated_sharpe


def _sharpe(R, ppy=365):
    sd = R.std(ddof=1)
    return R.mean() / sd * np.sqrt(ppy) if sd > 0 else 0


# 1. PBO flags selection-from-noise as overfit (the whole point)
def test_pbo_flags_overfit_selection_from_noise():
    rng = np.random.RandomState(0)
    # 40 pure-noise strategies, 2000 bars: the "best" is noise -> PBO should be high
    pool = rng.normal(0, 0.01, (2000, 40))
    res = cscv_pbo(pool, ppy=365, n_groups=10)
    assert res["pbo"] > 0.4, f"expected high PBO for noise, got {res['pbo']}"


# 2. PBO is LOW when one strategy is genuinely predictive
def test_pbo_low_for_genuine_edge():
    rng = np.random.RandomState(1)
    pool = rng.normal(0, 0.01, (2000, 20))
    pool[:, 0] += 0.002   # strategy 0 has a real positive drift (Sharpe ~ +3)
    res = cscv_pbo(pool, ppy=365, n_groups=10)
    assert res["pbo"] < 0.5, f"expected low PBO with a real edge, got {res['pbo']}"


# 3. CPCV produces an OOS Sharpe distribution
def test_cpcv_returns_distribution():
    rng = np.random.RandomState(2)
    returns = rng.normal(0.001, 0.02, 1000)   # a strategy with mild positive drift
    res = cpcv(returns, ppy=365, n_groups=6, n_test=2)
    assert res["paths"] > 0
    assert "oos_sharpe_median" in res
    assert np.isfinite(res["oos_sharpe_median"])


# 4. DSR re-export works and kills our survivors under multiple testing
def test_dsr_reexport_multiple_testing():
    d = deflated_sharpe(sharpe_annualized=0.6, n_trials=547, n_bars=432, ppy=365)
    assert d["dsr_p"] < 0.5     # a 0.6 Sharpe from 547 trials is not significant
    assert not d["significant"]
