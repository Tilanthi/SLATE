"""
SLATE Portfolio Risk Management

Manages risk across all active strategies with portfolio-level controls:
- VaR-based position sizing
- Correlation-aware diversification
- Sector/exposure limits
- Dynamic risk adjustment
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
import numpy as np
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents a trading position."""
    strategy_id: str
    strategy_type: str
    symbol: str
    side: str  # 'long' or 'short'
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    entry_time: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@dataclass
class RiskMetrics:
    """Current risk metrics for the portfolio."""
    total_value: float
    total_exposure: float
    portfolio_var_95: float  # Value at Risk at 95% confidence
    portfolio_cvar_95: float  # Conditional VaR
    max_correlation: float
    concentration_risk: float
    leverage_ratio: float
    liquidity_risk: float
    timestamp: datetime


@dataclass
class RiskLimit:
    """Risk limit configuration."""
    max_portfolio_var: float = 0.02  # 2% daily VaR
    max_correlation_exposure: float = 0.7
    max_single_strategy_exposure: float = 0.3  # 30% max per strategy
    max_single_symbol_exposure: float = 0.5  # 50% max per symbol
    max_leverage_ratio: float = 2.0
    min_liquidity_ratio: float = 0.1
    max_concentration_ratio: float = 0.4


class PortfolioRiskManager:
    """Manage risk across all active strategies."""

    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions: List[Position] = []
        self.risk_limits = RiskLimit()

        # Risk tracking
        self.daily_returns: List[float] = []
        self.drawdown_history: List[float] = []

        # Correlation cache
        self.correlation_cache: Dict[str, Dict[str, float]] = {}
        self.last_correlation_update = None

    def check_portfolio_risk(self, positions: List[Position]) -> Tuple[bool, List[str]]:
        """Check if portfolio exceeds risk limits."""
        if not positions:
            return True, []

        violations = []

        # Calculate current risk metrics
        risk_metrics = self.calculate_portfolio_risk(positions)

        # Check VaR limit
        if risk_metrics.portfolio_var_95 > self.risk_limits.max_portfolio_var:
            violations.append(f"Portfolio VaR {risk_metrics.portfolio_var_95:.2%} exceeds limit {self.risk_limits.max_portfolio_var:.2%}")

        # Check correlation exposure
        if risk_metrics.max_correlation > self.risk_limits.max_correlation_exposure:
            violations.append(f"Max correlation {risk_metrics.max_correlation:.2f} exceeds limit {self.risk_limits.max_correlation_exposure:.2f}")

        # Check concentration
        if risk_metrics.concentration_risk > self.risk_limits.max_concentration_ratio:
            violations.append(f"Concentration {risk_metrics.concentration_risk:.2f} exceeds limit {self.risk_limits.max_concentration_ratio:.2f}")

        # Check leverage
        if risk_metrics.leverage_ratio > self.risk_limits.max_leverage_ratio:
            violations.append(f"Leverage {risk_metrics.leverage_ratio:.2f}x exceeds limit {self.risk_limits.max_leverage_ratio:.2f}x")

        # Check single strategy exposure
        strategy_exposures = self._calculate_strategy_exposures(positions)
        for strategy_type, exposure in strategy_exposures.items():
            if exposure > self.risk_limits.max_single_strategy_exposure:
                violations.append(f"{strategy_type} exposure {exposure:.2%} exceeds limit {self.risk_limits.max_single_strategy_exposure:.2%}")

        is_safe = len(violations) == 0

        if not is_safe:
            logger.warning(f"Portfolio risk violations: {violations}")

        return is_safe, violations

    def calculate_portfolio_risk(self, positions: List[Position]) -> RiskMetrics:
        """Calculate comprehensive portfolio risk metrics."""
        if not positions:
            return RiskMetrics(
                total_value=self.current_capital,
                total_exposure=0.0,
                portfolio_var_95=0.0,
                portfolio_cvar_95=0.0,
                max_correlation=0.0,
                concentration_risk=0.0,
                leverage_ratio=0.0,
                liquidity_risk=0.0,
                timestamp=datetime.now()
            )

        # Calculate total value
        total_value = sum(p.size * p.current_price for p in positions) + self.current_capital
        total_exposure = sum(abs(p.size * p.current_price) for p in positions) / total_value

        # Calculate VaR using historical simulation
        portfolio_var_95, portfolio_cvar_95 = self._calculate_var_cvar(positions)

        # Calculate correlation metrics
        max_correlation = self._calculate_max_correlation(positions)

        # Calculate concentration
        concentration_risk = self._calculate_concentration(positions)

        # Calculate leverage
        leverage_ratio = total_exposure

        # Calculate liquidity risk
        liquidity_risk = self._calculate_liquidity_risk(positions)

        return RiskMetrics(
            total_value=total_value,
            total_exposure=total_exposure,
            portfolio_var_95=portfolio_var_95,
            portfolio_cvar_95=portfolio_cvar_95,
            max_correlation=max_correlation,
            concentration_risk=concentration_risk,
            leverage_ratio=leverage_ratio,
            liquidity_risk=liquidity_risk,
            timestamp=datetime.now()
        )

    def _calculate_var_cvar(self, positions: List[Position]) -> Tuple[float, float]:
        """Calculate Value at Risk and Conditional VaR at 95% confidence."""
        if not positions:
            return 0.0, 0.0

        # Calculate portfolio returns
        portfolio_returns = []

        # Simulate returns using historical volatility
        for position in positions:
            # Use typical daily volatility for crypto
            daily_vol = 0.05  # 5% daily volatility

            # Generate returns based on position size and direction
            position_returns = np.random.normal(0, daily_vol, 100)

            # Scale by position size
            position_value = position.size * position.current_price
            scaled_returns = position_returns * (position_value / self.current_capital)

            portfolio_returns.extend(scaled_returns)

        if not portfolio_returns:
            return 0.0, 0.0

        # Calculate VaR at 95% confidence
        var_95 = np.percentile(portfolio_returns, 5)

        # Calculate CVaR (average of worst 5%)
        worst_5_percent = [r for r in portfolio_returns if r <= var_95]
        cvar_95 = np.mean(worst_5_percent) if worst_5_percent else var_95

        return var_95, cvar_95

    def _calculate_max_correlation(self, positions: List[Position]) -> float:
        """Calculate maximum correlation between positions."""
        if len(positions) < 2:
            return 0.0

        # Group positions by strategy type
        type_returns = defaultdict(list)

        for position in positions:
            # Generate synthetic returns based on strategy type
            # In production, would use actual historical returns
            np.random.seed(hash(position.strategy_type) % 2**32)
            returns = np.random.normal(0, 0.02, 50)
            type_returns[position.strategy_type].append(returns)

        # Calculate correlations between strategy types
        correlations = []

        types = list(type_returns.keys())
        for i, type1 in enumerate(types):
            for type2 in types[i+1:]:
                if type_returns[type1] and type_returns[type2]:
                    # Calculate correlation
                    corr = np.corrcoef(type_returns[type1][0], type_returns[type2][0])[0, 1]
                    if not np.isnan(corr):
                        correlations.append(abs(corr))

        return max(correlations) if correlations else 0.0

    def _calculate_concentration(self, positions: List[Position]) -> float:
        """Calculate portfolio concentration (Herfindahl index)."""
        if not positions:
            return 0.0

        # Calculate concentration by strategy type
        type_values = defaultdict(float)
        total_value = 0.0

        for position in positions:
            position_value = abs(position.size * position.current_price)
            type_values[position.strategy_type] += position_value
            total_value += position_value

        if total_value == 0:
            return 0.0

        # Calculate Herfindahl index
        weights = [v / total_value for v in type_values.values()]
        hhi = sum(w**2 for w in weights)

        return hhi

    def _calculate_liquidity_risk(self, positions: List[Position]) -> float:
        """Calculate liquidity risk of portfolio."""
        if not positions:
            return 0.0

        # Simplified liquidity risk based on position sizes
        # In production, would use actual market depth data
        total_size = sum(abs(p.size) for p in positions)

        # Assume max safe size is 10% of daily volume
        max_safe_size = 1000000  # Placeholder

        liquidity_ratio = total_size / max_safe_size

        return min(1.0, liquidity_ratio)

    def _calculate_strategy_exposures(self, positions: List[Position]) -> Dict[str, float]:
        """Calculate exposure by strategy type."""
        exposures = defaultdict(float)
        total_value = sum(abs(p.size * p.current_price) for p in positions)

        if total_value == 0:
            return {}

        for position in positions:
            position_value = abs(position.size * position.current_price)
            exposures[position.strategy_type] = position_value / total_value

        return dict(exposures)

    def suggest_position_size(self, strategy: Dict, current_price: float,
                             portfolio_value: float) -> float:
        """Suggest position size based on risk limits."""
        # Base position size: 10% of portfolio
        base_size = portfolio_value * 0.1 / current_price

        # Adjust based on strategy type
        risk_multipliers = {
            'momentum': 1.0,
            'mean_reversion': 0.8,
            'breakout': 1.2,
            'trend_following': 1.0,
            'statistical_arb': 0.6,
            'ensemble': 1.1
        }

        multiplier = risk_multipliers.get(strategy.get('type', 'momentum'), 1.0)

        # Get current risk metrics
        risk_metrics = self.calculate_portfolio_risk(self.positions)

        # Reduce size if portfolio is already risky
        risk_adjustment = 1.0

        if risk_metrics.portfolio_var_95 > self.risk_limits.max_portfolio_var * 0.8:
            risk_adjustment = 0.5

        suggested_size = base_size * multiplier * risk_adjustment

        # Ensure minimum and maximum sizes
        min_size = portfolio_value * 0.01 / current_price  # 1% minimum
        max_size = portfolio_value * 0.2 / current_price   # 20% maximum

        return max(min_size, min(max_size, suggested_size))

    async def monitor_and_rebalance(self) -> Dict[str, Any]:
        """Monitor portfolio and suggest rebalancing actions."""
        # Calculate current risk
        risk_metrics = self.calculate_portfolio_risk(self.positions)

        # Check for violations
        is_safe, violations = self.check_portfolio_risk(self.positions)

        # Suggest actions
        actions = []

        if not is_safe:
            if 'VaR' in ' '.join(violations):
                actions.append("Reduce position sizes to lower portfolio VaR")

            if 'concentration' in ' '.join(violations):
                actions.append("Diversify across more strategy types")

            if 'leverage' in ' '.join(violations):
                actions.append("Reduce overall exposure")

        return {
            'is_safe': is_safe,
            'risk_metrics': {
                'portfolio_var_95': risk_metrics.portfolio_var_95,
                'max_correlation': risk_metrics.max_correlation,
                'concentration': risk_metrics.concentration_risk,
                'leverage': risk_metrics.leverage_ratio
            },
            'violations': violations,
            'suggested_actions': actions
        }

    def add_position(self, position: Position) -> bool:
        """Add position if within risk limits."""
        # Check if adding this position would violate risk limits
        test_positions = self.positions + [position]
        is_safe, violations = self.check_portfolio_risk(test_positions)

        if is_safe:
            self.positions.append(position)
            logger.info(f"Position added: {position.strategy_type} {position.symbol}")
            return True
        else:
            logger.warning(f"Position rejected due to risk limits: {violations}")
            return False

    def remove_position(self, strategy_id: str, symbol: str) -> bool:
        """Remove position from portfolio."""
        for i, position in enumerate(self.positions):
            if position.strategy_id == strategy_id and position.symbol == symbol:
                self.positions.pop(i)
                logger.info(f"Position removed: {strategy_id} {symbol}")
                return True
        return False

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get summary of current portfolio state."""
        if not self.positions:
            return {
                'total_value': self.current_capital,
                'position_count': 0,
                'is_safe': True,
                'positions': []
            }

        risk_metrics = self.calculate_portfolio_risk(self.positions)
        is_safe, violations = self.check_portfolio_risk(self.positions)

        return {
            'total_value': risk_metrics.total_value,
            'total_exposure': risk_metrics.total_exposure,
            'position_count': len(self.positions),
            'is_safe': is_safe,
            'violations': violations,
            'positions': [
                {
                    'strategy_id': p.strategy_id,
                    'strategy_type': p.strategy_type,
                    'symbol': p.symbol,
                    'side': p.side,
                    'size': p.size,
                    'pnl': p.unrealized_pnl
                }
                for p in self.positions
            ]
        }
