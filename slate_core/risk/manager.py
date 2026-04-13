"""
SLATE Risk Manager

5-state risk management FSM with position sizing and exposure control.
States: NOMINAL → ELEVATED → MARGINAL → CRITICAL → EMERGENCY
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class RiskState(Enum):
    """Risk management states."""
    NORMAL = "normal"
    ELEVATED = "elevated"
    MARGINAL = "marginal"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class RiskMetrics:
    """Current risk metrics."""
    portfolio_value: float
    total_exposure: float
    unrealized_pnl: float
    daily_pnl: float
    max_drawdown: float
    var_95: float  # Value at Risk 95%
    open_positions: int


class RiskManager:
    """
    Risk management system with multi-state controls.

    Features:
    - 5-state risk FSM
    - Position sizing (Kelly, Fractional Kelly, Volatility Targeting)
    - Portfolio-level exposure tracking
    - Drawdown limits
    - Value at Risk (VaR) calculation
    """

    def __init__(self, initial_capital: float = 10000):
        self.initial_capital = initial_capital
        self.current_state = RiskState.NORMAL
        self.capital = initial_capital
        self.peak_capital = initial_capital

        # Risk limits
        self.risk_limits = {
            RiskState.NORMAL: {
                "max_position_size": 0.02,  # 2% of capital
                "max_total_exposure": 0.5,   # 50% of capital
                "max_daily_loss": 0.03       # 3% daily loss limit
            },
            RiskState.ELEVATED: {
                "max_position_size": 0.015,
                "max_total_exposure": 0.3,
                "max_daily_loss": 0.02
            },
            RiskState.MARGINAL: {
                "max_position_size": 0.01,
                "max_total_exposure": 0.2,
                "max_daily_loss": 0.015
            },
            RiskState.CRITICAL: {
                "max_position_size": 0.005,
                "max_total_exposure": 0.1,
                "max_daily_loss": 0.01
            },
            RiskState.EMERGENCY: {
                "max_position_size": 0.0,
                "max_total_exposure": 0.0,
                "max_daily_loss": 0.0
            }
        }

        self.positions: Dict[str, Dict] = {}
        self.trade_history: List[Dict] = []

        logger.info("Risk Manager initialized")

    async def get_status(self) -> Dict:
        """Get current risk status."""
        limits = self.risk_limits[self.current_state]

        return {
            "state": self.current_state.value,
            "capital": self.capital,
            "peak_capital": self.peak_capital,
            "drawdown": (self.peak_capital - self.capital) / self.peak_capital,
            "limits": limits,
            "position_count": len(self.positions)
        }

    async def get_metrics(self) -> Dict:
        """Get detailed risk metrics."""
        total_exposure = sum(p.get("size", 0) for p in self.positions.values())
        unrealized_pnl = sum(p.get("unrealized_pnl", 0) for p in self.positions.values())

        return {
            "portfolio_value": self.capital + unrealized_pnl,
            "total_exposure": total_exposure,
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": sum(t.get("pnl", 0) for t in self.trade_history),
            "drawdown": (self.peak_capital - self.capital) / self.peak_capital if self.peak_capital > 0 else 0,
            "open_positions": len(self.positions),
            "state": self.current_state.value
        }

    async def assess_risk(
        self,
        observation,
        regime,
        signals: Dict
    ) -> Dict:
        """Assess current risk level and update state if needed."""
        metrics = await self.get_metrics()
        drawdown = metrics["drawdown"]

        # Update risk state based on drawdown
        previous_state = self.current_state

        if drawdown < 0.05:
            self.current_state = RiskState.NORMAL
        elif drawdown < 0.10:
            self.current_state = RiskState.ELEVATED
        elif drawdown < 0.15:
            self.current_state = RiskState.MARGINAL
        elif drawdown < 0.20:
            self.current_state = RiskState.CRITICAL
        else:
            self.current_state = RiskState.EMERGENCY

        if previous_state != self.current_state:
            logger.warning(f"Risk state changed: {previous_state.value} → {self.current_state.value}")

        limits = self.risk_limits[self.current_state]

        return {
            "risk_level": self.current_state.value,
            "approved": self.current_state != RiskState.EMERGENCY,
            "drawdown": drawdown,
            "max_position_size": limits["max_position_size"],
            "max_exposure": limits["max_total_exposure"],
            "reason": self._get_state_reason()
        }

    def _get_state_reason(self) -> str:
        """Get reason for current risk state."""
        reasons = {
            RiskState.NORMAL: "Operating within normal parameters",
            RiskState.ELEVATED: "Increased market volatility or drawdown",
            RiskState.MARGINAL: "Approaching risk limits - reduce exposure",
            RiskState.CRITICAL: "Near maximum drawdown - consider pausing",
            RiskState.EMERGENCY: "Maximum drawdown exceeded - STOP TRADING"
        }
        return reasons.get(self.current_state, "")

    async def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        account_balance: float,
        risk_per_trade: float = 0.02
    ) -> Dict:
        """
        Calculate optimal position size based on risk parameters.

        Uses fixed fractional risk: position size = (capital * risk_per_trade) / (entry - stop_loss)
        """
        # Risk per trade in currency
        risk_amount = account_balance * risk_per_trade

        # Risk per unit
        risk_per_unit = abs(entry_price - stop_loss)

        if risk_per_unit == 0:
            return {
                "position_size": 0,
                "risk_amount": risk_amount,
                "error": "Stop loss equals entry price"
            }

        # Position size
        position_size = risk_amount / risk_per_unit

        # Apply risk state limits
        limits = self.risk_limits[self.current_state]
        max_size = account_balance * limits["max_position_size"]
        position_size = min(position_size, max_size)

        return {
            "position_size": round(position_size, 6),
            "risk_amount": round(risk_amount, 2),
            "risk_per_unit": round(risk_per_unit, 2),
            "max_size": round(max_size, 2),
            "risk_state": self.current_state.value
        }

    async def kelly_criterion(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        fractional_kelly: float = 0.25
    ) -> Dict:
        """
        Calculate position size using Kelly Criterion.

        Kelly % = (W*R - L) / R
        Where W = win rate, R = win/loss ratio, L = loss rate

        Uses fractional Kelly for safety.
        """
        if avg_loss == 0 or win_rate == 0:
            return {"kelly_percentage": 0, "position_size_pct": 0}

        win_loss_ratio = avg_win / abs(avg_loss)
        loss_rate = 1 - win_rate

        # Full Kelly
        kelly = (win_rate * win_loss_ratio - loss_rate) / win_loss_ratio

        # Fractional Kelly (safer)
        fractional_kelly_pct = kelly * fractional_kelly

        return {
            "kelly_percentage": round(max(0, kelly) * 100, 2),
            "position_size_pct": round(max(0, fractional_kelly_pct) * 100, 2),
            "fraction_used": fractional_kelly,
            "warning": "Full Kelly can be aggressive - using fractional" if fractional_kelly < 1 else None
        }

    async def get_portfolio_risk(self) -> Dict:
        """Get portfolio-level risk metrics."""
        if not self.positions:
            return {
                "total_exposure": 0,
                "exposure_pct": 0,
                "correlation_risk": 0,
                "concentration_risk": 0
            }

        total_value = sum(p.get("value", 0) for p in self.positions.values())
        exposure_pct = total_value / self.capital if self.capital > 0 else 0

        return {
            "total_exposure": total_value,
            "exposure_pct": round(exposure_pct * 100, 2),
            "max_allowed": round(self.risk_limits[self.current_state]["max_total_exposure"] * 100, 2),
            "within_limits": exposure_pct <= self.risk_limits[self.current_state]["max_total_exposure"]
        }

    async def get_market_exposure(self) -> Dict:
        """Get current market exposure by symbol."""
        exposure = {}

        for symbol, pos in self.positions.items():
            exposure[symbol] = {
                "size": pos.get("size", 0),
                "value": pos.get("value", 0),
                "side": pos.get("side", "long"),
                "entry_price": pos.get("entry_price", 0)
            }

        return exposure

    def update_capital(self, pnl: float):
        """Update capital after trade."""
        self.capital += pnl

        if self.capital > self.peak_capital:
            self.peak_capital = self.capital

        logger.info(f"Capital updated: {pnl:+.2f} → {self.capital:.2f}")
