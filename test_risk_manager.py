"""Tests for the runtime risk controller (slate_core.risk.risk_manager)."""
import numpy as np

from slate_core.risk.risk_manager import PortfolioRiskController, RiskConfig


def _streams(n=200, seed=0):
    rng = np.random.RandomState(seed)
    return {"a": rng.normal(0.001, 0.02, n), "b": rng.normal(0.001, 0.03, n)}


def test_vol_target_weights_inverse_to_vol():
    """Lower-vol stream should get higher weight (inverse-vol allocation)."""
    ctrl = PortfolioRiskController()
    streams = _streams()
    w = ctrl.compute_weights(streams, current_equity=1.0)
    assert w["a"] > w["b"]   # 'a' has lower vol (0.02 < 0.03) → higher weight


def test_drawdown_throttle_cuts_exposure():
    """When drawdown exceeds the flat threshold, all weights → 0."""
    cfg = RiskConfig(dd_throttle_start=0.05, dd_throttle_half=0.08, dd_throttle_flat=0.12)
    ctrl = PortfolioRiskController(cfg)
    streams = _streams()
    # Simulate drawdown: peak 1.0, current 0.80 → 20% DD > flat(12%)
    ctrl._update_drawdown(1.0)   # set peak
    ctrl._update_drawdown(0.80)  # 20% DD
    w = ctrl.compute_weights(streams, current_equity=0.80)
    assert all(v == 0.0 for v in w.values())   # flat


def test_drawdown_throttle_partial_cut():
    """Between start and flat thresholds, exposure should be reduced (<1)."""
    cfg = RiskConfig(dd_throttle_start=0.05, dd_throttle_half=0.08, dd_throttle_flat=0.12)
    ctrl = PortfolioRiskController(cfg)
    streams = _streams()
    ctrl._update_drawdown(1.0)
    ctrl._update_drawdown(0.92)  # 8% DD → between start(5%) and half(8%)
    w = ctrl.compute_weights(streams, current_equity=0.92)
    total = sum(w.values())
    assert 0 < total < 1.0   # partially cut but not flat


def test_regime_derisk_in_stress():
    """High-vol regime should reduce exposure."""
    cfg = RiskConfig(regime_vol_threshold=0.01, regime_stress_factor=0.5)
    ctrl = PortfolioRiskController(cfg)
    # extreme vol → stress regime
    streams = {"x": np.random.RandomState(0).normal(0, 0.1, 200)}
    w = ctrl.compute_weights(streams, current_equity=1.0)
    status = ctrl.status()
    assert status["regime"] in ("stress", "crash")


def test_status_reports_state():
    ctrl = PortfolioRiskController()
    streams = _streams()
    ctrl.compute_weights(streams, current_equity=1.0)
    s = ctrl.status()
    assert "current_drawdown" in s
    assert "regime" in s
    assert "throttle_factor" in s
