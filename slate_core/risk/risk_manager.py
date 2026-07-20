"""Runtime portfolio risk controller: drawdown throttle + regime de-risking.

This is the layer that makes drawdown LOW. Given the premium-stream return
histories + the current portfolio drawdown state + the market regime, it
produces TARGET WEIGHTS (how much capital to deploy in each stream) that:
  - vol-target each stream (weight ∝ 1/σ so none dominates risk),
  - risk-parity the portfolio (equal risk contribution),
  - throttle hard on drawdown (cut sizes after X% DD, go flat after Y%),
  - de-risk in hostile regimes (vol expansion / crash → reduce exposure).

This is NOT a price predictor — it's risk management, which is where durable
low-drawdown positive returns actually come from.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np


@dataclass
class RiskConfig:
    """Configuration for the risk controller."""
    # Drawdown throttle: cut exposure progressively as DD worsens
    dd_throttle_start: float = 0.08    # 8% DD → start cutting
    dd_throttle_half: float = 0.12     # 12% DD → 50% exposure
    dd_throttle_flat: float = 0.18     # 18% DD → go flat
    dd_recovery_threshold: float = 0.04  # recover to <4% DD → restore

    # Regime de-risking
    regime_vol_threshold: float = 0.06  # annualized vol above this → "stress"
    regime_stress_factor: float = 0.5   # in stress, multiply exposure by this

    # Per-stream limits
    max_single_stream_weight: float = 0.40  # no single stream > 40%
    min_streams: int = 2                     # diversify across at least 2

    # Volatility target
    target_portfolio_vol: float = 0.15  # 15% annualized target


@dataclass
class RiskState:
    """Tracks the risk controller's internal state across cycles."""
    current_drawdown: float = 0.0
    peak_equity: float = 1.0
    throttle_factor: float = 1.0     # 1.0 = full exposure, 0.0 = flat
    regime: str = "normal"
    history_drawdowns: List[float] = field(default_factory=list)


class PortfolioRiskController:
    """Produces target weights for premium streams, risk-managed for low drawdown."""

    def __init__(self, config: Optional[RiskConfig] = None):
        self.config = config or RiskConfig()
        self.state = RiskState()

    def compute_weights(self, stream_returns: Dict[str, np.ndarray],
                        current_equity: float = 1.0) -> Dict[str, float]:
        """Produce risk-managed target weights for each premium stream.

        1. Inverse-volatility weights (risk parity approximation).
        2. Apply drawdown throttle (cut if DD exceeds thresholds).
        3. Apply regime de-risk (reduce in high-vol regimes).
        4. Enforce single-stream cap.
        """
        cfg = self.config

        # Update drawdown state
        self._update_drawdown(current_equity)

        # 1) Inverse-vol weights (risk parity heuristic)
        vols = {}
        for name, rets in stream_returns.items():
            v = float(np.std(rets)) if len(rets) > 1 else 0.01
            vols[name] = max(v, 1e-8)   # floor to avoid div-by-zero
        inv_vols = {k: 1.0 / v for k, v in vols.items()}
        total_iv = sum(inv_vols.values())
        weights = {k: v / total_iv for k, v in inv_vols.items()}

        # 2) Drawdown throttle
        dd = self.state.current_drawdown
        if dd >= cfg.dd_throttle_flat:
            self.state.throttle_factor = 0.0
        elif dd >= cfg.dd_throttle_half:
            t = (cfg.dd_throttle_flat - dd) / (cfg.dd_throttle_flat - cfg.dd_throttle_half)
            self.state.throttle_factor = max(0.0, 0.5 * t)
        elif dd >= cfg.dd_throttle_start:
            t = (cfg.dd_throttle_half - dd) / (cfg.dd_throttle_half - cfg.dd_throttle_start)
            self.state.throttle_factor = max(0.5, 0.5 + 0.5 * t)
        elif dd < cfg.dd_recovery_threshold:
            self.state.throttle_factor = 1.0   # fully recovered

        throttle = self.state.throttle_factor

        # 3) Regime de-risk
        regime_factor = self._assess_regime(stream_returns)

        # 4) Apply throttle + regime, enforce caps
        total_exposure = throttle * regime_factor
        for k in weights:
            weights[k] *= total_exposure
            weights[k] = min(weights[k], cfg.max_single_stream_weight)

        return weights

    def _update_drawdown(self, current_equity: float):
        """Track rolling drawdown from peak equity."""
        if current_equity > self.state.peak_equity:
            self.state.peak_equity = current_equity
        if self.state.peak_equity > 0:
            dd = 1.0 - current_equity / self.state.peak_equity
            self.state.current_drawdown = max(dd, 0.0)
            self.state.history_drawdowns.append(self.state.current_drawdown)
            if len(self.state.history_drawdowns) > 500:
                self.state.history_drawdowns = self.state.history_drawdowns[-500:]

    def _assess_regime(self, stream_returns: Dict[str, np.ndarray]) -> float:
        """Assess regime: return a de-risk factor (1.0 = normal, <1 = stress)."""
        cfg = self.config
        # Use the average stream vol as a regime indicator
        vols = []
        for rets in stream_returns.values():
            if len(rets) > 10:
                recent = rets[-30:] if len(rets) >= 30 else rets
                vols.append(float(np.std(recent)))
        if not vols:
            self.state.regime = "normal"
            return 1.0
        avg_vol = np.mean(vols) * np.sqrt(365)   # annualized (approx)
        if avg_vol > cfg.regime_vol_threshold * 1.5:
            self.state.regime = "crash"
            return cfg.regime_stress_factor * 0.5
        if avg_vol > cfg.regime_vol_threshold:
            self.state.regime = "stress"
            return cfg.regime_stress_factor
        self.state.regime = "normal"
        return 1.0

    def status(self) -> Dict:
        """Return current risk state for reporting."""
        return {
            "current_drawdown": round(self.state.current_drawdown, 4),
            "throttle_factor": round(self.state.throttle_factor, 3),
            "regime": self.state.regime,
            "peak_equity": round(self.state.peak_equity, 4),
            "max_historical_dd": round(max(self.state.history_drawdowns or [0]), 4),
        }


__all__ = ["RiskConfig", "RiskState", "PortfolioRiskController"]
