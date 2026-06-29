#!/usr/bin/env python3
"""
SLATE Portfolio Manager

Coordinates multiple strategies as a unified portfolio with intelligent capital allocation.
Manages the complete lifecycle of multi-strategy portfolio operations.

Key Features:
- Multi-strategy portfolio coordination
- Dynamic capital allocation using advanced optimization methods
- Real-time portfolio performance tracking and attribution
- Automatic portfolio rebalancing on regime changes
- Portfolio-level risk management and controls
"""

import logging
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import sqlite3

logger = logging.getLogger(__name__)


class AllocationMethod(Enum):
    """Portfolio allocation methods."""
    KELLY_CRITERION = "kelly_criterion"           # Growth-optimal allocation
    RISK_PARITY = "risk_parity"                   # Equal risk contribution
    TARGET_VOLATILITY = "target_volatility"       # Volatility-scaled allocation
    CVAR_OPTIMIZATION = "cvar_optimization"       # Tail-risk-aware allocation
    REGIME_ADAPTIVE = "regime_adaptive"           # Regime-specific allocation
    EQUAL_WEIGHT = "equal_weight"                 # 1/N benchmark allocation


class PortfolioStatus(Enum):
    """Portfolio operational status."""
    NORMAL = "normal"                             # All systems operational
    REBALANCING = "rebalancing"                   # Portfolio rebalancing in progress
    RISK_WARNING = "risk_warning"                 # Risk metrics elevated
    RISK_CRITICAL = "risk_critical"               # Risk limits exceeded
    REGIME_CHANGE = "regime_change"               # Market regime change detected


@dataclass
class StrategyAllocation:
    """Allocation details for a single strategy."""
    strategy_id: str
    strategy_name: str
    capital_allocated: float                       # Amount of capital allocated
    allocation_weight: float                        # Portfolio weight (0-1)
    target_weight: float                          # Target allocation weight
    current_value: float                           # Current portfolio value
    unrealized_pnl: float                         # Unrealized profit/loss
    realized_pnl: float                           # Realized profit/loss
    strategy_return: float                         # Strategy return since allocation

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'strategy_id': self.strategy_id,
            'strategy_name': self.strategy_name,
            'capital_allocated': self.capital_allocated,
            'allocation_weight': self.allocation_weight,
            'target_weight': self.target_weight,
            'current_value': self.current_value,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl,
            'strategy_return': self.strategy_return
        }


@dataclass
class PortfolioState:
    """Complete portfolio state and performance."""
    total_capital: float                           # Total portfolio capital
    allocated_capital: float                       # Capital currently allocated
    available_capital: float                       # Capital available for allocation
    portfolio_return: float                        # Total portfolio return
    portfolio_volatility: float                     # Portfolio volatility (annualized)
    sharpe_ratio: float                            # Portfolio Sharpe ratio
    max_drawdown: float                            # Maximum portfolio drawdown
    current_drawdown: float                        # Current portfolio drawdown
    status: PortfolioStatus                        # Portfolio operational status
    allocations: List[StrategyAllocation]          # Strategy allocations
    last_rebalance: datetime                       # Last portfolio rebalance timestamp
    last_update: datetime                          # Last portfolio update timestamp

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'total_capital': self.total_capital,
            'allocated_capital': self.allocated_capital,
            'available_capital': self.available_capital,
            'portfolio_return': self.portfolio_return,
            'portfolio_volatility': self.portfolio_volatility,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'current_drawdown': self.current_drawdown,
            'status': self.status.value,
            'allocations': [alloc.to_dict() for alloc in self.allocations],
            'last_rebalance': self.last_rebalance.isoformat() if self.last_rebalance else None,
            'last_update': self.last_update.isoformat()
        }


@dataclass
class PortfolioAllocation:
    """Result of portfolio allocation optimization."""
    allocations: Dict[str, float]                  # Strategy ID -> allocation weight
    expected_return: float                          # Expected portfolio return
    expected_volatility: float                      # Expected portfolio volatility
    sharpe_ratio: float                             # Expected portfolio Sharpe ratio
    allocation_method: AllocationMethod            # Method used for allocation
    rebalance_reason: str                          # Reason for allocation/rebalance
    allocation_metadata: Dict[str, Any]             # Additional allocation metadata

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'allocations': self.allocations,
            'expected_return': self.expected_return,
            'expected_volatility': self.expected_volatility,
            'sharpe_ratio': self.sharpe_ratio,
            'allocation_method': self.allocation_method.value,
            'rebalance_reason': self.rebalance_reason,
            'allocation_metadata': self.allocation_metadata
        }


@dataclass
class RiskParameters:
    """Portfolio risk management parameters."""
    max_portfolio_var: float = 0.02                # Maximum daily VaR (2%)
    max_portfolio_correlation: float = 0.7         # Maximum strategy correlation
    max_single_strategy_weight: float = 0.30       # Maximum single strategy weight (30%)
    max_single_symbol_weight: float = 0.50         # Maximum single symbol weight (50%)
    max_leverage_ratio: float = 2.0                 # Maximum portfolio leverage
    target_volatility: float = 0.15                # Target portfolio volatility (15%)
    max_drawdown_limit: float = 0.20               # Maximum portfolio drawdown (20%)
    warning_drawdown: float = 0.10                 # Warning drawdown threshold (10%)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'max_portfolio_var': self.max_portfolio_var,
            'max_portfolio_correlation': self.max_portfolio_correlation,
            'max_single_strategy_weight': self.max_single_strategy_weight,
            'max_single_symbol_weight': self.max_single_symbol_weight,
            'max_leverage_ratio': self.max_leverage_ratio,
            'target_volatility': self.target_volatility,
            'max_drawdown_limit': self.max_drawdown_limit,
            'warning_drawdown': self.warning_drawdown
        }


class PortfolioManager:
    """
    Manage multi-strategy portfolio with dynamic capital allocation.

    Features:
    - Capital allocation using multiple optimization methods
    - Real-time portfolio performance tracking and attribution
    - Automatic rebalancing on regime changes or performance shifts
    - Portfolio-level risk management and controls
    - Strategy health monitoring and position management
    """

    def __init__(self,
                 total_capital: float = 10000.0,
                 allocation_method: AllocationMethod = AllocationMethod.KELLY_CRITERION,
                 risk_params: Optional[RiskParameters] = None,
                 db_path: str = "slate_core/slate_realistic_discoveries.db"):
        """
        Initialize portfolio manager.

        Args:
            total_capital: Total portfolio capital (paper trading)
            allocation_method: Default allocation optimization method
            risk_params: Portfolio risk management parameters
            db_path: Database path for persistence
        """
        self.total_capital = total_capital
        self.allocation_method = allocation_method
        self.risk_params = risk_params or RiskParameters()
        self.db_path = db_path

        # Portfolio state
        self.portfolio_state: Optional[PortfolioState] = None
        self.current_allocations: Dict[str, StrategyAllocation] = {}

        # Performance tracking
        self.portfolio_history: List[Dict[str, Any]] = []
        self.rebalance_history: List[Dict[str, Any]] = []

        # Statistics
        self.total_allocations = 0
        self.total_rebalances = 0
        self.allocation_methods_used = {}

        # Try to load existing portfolio state
        self._load_portfolio_state()

        logger.info(f"PortfolioManager initialized: ${total_capital:,.2f}, method={allocation_method.value}")

    def allocate_capital(
        self,
        selected_strategies: List[Any],  # SelectedStrategy objects
        total_capital: Optional[float] = None,
        allocation_method: Optional[AllocationMethod] = None,
        current_regime: str = "TRENDING_UP"
    ) -> PortfolioAllocation:
        """
        Allocate capital using advanced optimization methods.

        Args:
            selected_strategies: List of selected strategies with metadata
            total_capital: Total capital to allocate (overrides default)
            allocation_method: Allocation optimization method
            current_regime: Current market regime for regime-adaptive allocation

        Returns:
            PortfolioAllocation with optimal capital distribution
        """
        self.total_allocations += 1

        # Use provided capital or default
        capital = total_capital or self.total_capital
        method = allocation_method or self.allocation_method

        logger.info(f"Allocating ${capital:,.2f} using {method.value} method")

        # Extract strategy data for allocation
        strategy_data = self._extract_strategy_data(selected_strategies)

        # Apply allocation method
        if method == AllocationMethod.KELLY_CRITERION:
            allocations = self._kelly_criterion_allocation(strategy_data)
        elif method == AllocationMethod.RISK_PARITY:
            allocations = self._risk_parity_allocation(strategy_data)
        elif method == AllocationMethod.TARGET_VOLATILITY:
            allocations = self._target_volatility_allocation(strategy_data)
        elif method == AllocationMethod.CVAR_OPTIMIZATION:
            allocations = self._cvar_optimization_allocation(strategy_data)
        elif method == AllocationMethod.REGIME_ADAPTIVE:
            allocations = self._regime_adaptive_allocation(strategy_data, current_regime)
        else:  # EQUAL_WEIGHT
            allocations = self._equal_weight_allocation(strategy_data)

        # Apply risk constraints
        constrained_allocations = self._apply_risk_constraints(allocations, strategy_data)

        # Calculate portfolio metrics
        portfolio_metrics = self._calculate_portfolio_metrics(constrained_allocations, strategy_data)

        # Store allocation statistics
        self.allocation_methods_used[method.value] = self.allocation_methods_used.get(method.value, 0) + 1

        # Create result
        result = PortfolioAllocation(
            allocations=constrained_allocations,
            expected_return=portfolio_metrics['expected_return'],
            expected_volatility=portfolio_metrics['expected_volatility'],
            sharpe_ratio=portfolio_metrics['sharpe_ratio'],
            allocation_method=method,
            rebalance_reason="initial_allocation" if not self.current_allocations else "optimization",
            allocation_metadata={
                'strategies_count': len(selected_strategies),
                'current_regime': current_regime,
                'risk_constraints_applied': True,
                'allocation_timestamp': datetime.now().isoformat()
            }
        )

        logger.info(f"Capital allocation complete: {len(constrained_allocations)} strategies, expected return={portfolio_metrics['expected_return']:.2%}")

        return result

    def rebalance_portfolio(
        self,
        current_regime: str = "TRENDING_UP",
        allocation_method: Optional[AllocationMethod] = None
    ) -> Optional[PortfolioAllocation]:
        """
        Rebalance portfolio based on performance changes or regime shifts.

        Args:
            current_regime: Current market regime
            allocation_method: Optional override for allocation method

        Returns:
            New portfolio allocation if rebalancing occurred, None otherwise
        """
        if not self.current_allocations:
            logger.info("No existing allocations to rebalance")
            return None

        self.total_rebalances += 1

        logger.info(f"Portfolio rebalancing triggered: regime={current_regime}")

        # Check if rebalancing is needed
        rebalance_needed, reason = self._check_rebalance_necessity(current_regime)

        if not rebalance_needed:
            logger.info("Rebalancing not needed")
            return None

        # Create strategy list from current allocations
        current_strategies = self._create_strategy_list_from_allocations()

        # Perform new allocation
        new_allocation = self.allocate_capital(
            current_strategies,
            self.total_capital,
            allocation_method or self.allocation_method,
            current_regime
        )

        # Update rebalance reason
        new_allocation.rebalance_reason = reason

        # Store rebalance history
        self.rebalance_history.append({
            'timestamp': datetime.now().isoformat(),
            'reason': reason,
            'regime': current_regime,
            'previous_allocations': dict(self.current_allocations),
            'new_allocations': new_allocation.allocations
        })

        # Update portfolio state
        self._update_portfolio_from_allocation(new_allocation)

        logger.info(f"Portfolio rebalanced: {len(new_allocation.allocations)} strategies")

        return new_allocation

    def get_portfolio_state(self) -> PortfolioState:
        """Get current portfolio state and performance."""
        if self.portfolio_state is None:
            # Initialize empty portfolio state
            self.portfolio_state = PortfolioState(
                total_capital=self.total_capital,
                allocated_capital=0.0,
                available_capital=self.total_capital,
                portfolio_return=0.0,
                portfolio_volatility=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                current_drawdown=0.0,
                status=PortfolioStatus.NORMAL,
                allocations=[],
                last_rebalance=None,
                last_update=datetime.now()
            )

        # Update current values
        self.portfolio_state.last_update = datetime.now()
        self.portfolio_state.allocated_capital = sum(alloc.current_value for alloc in self.current_allocations.values())
        self.portfolio_state.available_capital = self.total_capital - self.portfolio_state.allocated_capital
        self.portfolio_state.allocations = list(self.current_allocations.values())

        return self.portfolio_state

    def _extract_strategy_data(self, selected_strategies: List[Any]) -> Dict[str, Dict[str, Any]]:
        """Extract strategy data for allocation optimization."""
        strategy_data = {}

        for selected_strategy in selected_strategies:
            strategy = selected_strategy.strategy if hasattr(selected_strategy, 'strategy') else selected_strategy

            data = {
                'strategy_id': strategy.strategy_id,
                'strategy_type': strategy.strategy_type,
                'expected_return': strategy.expected_return / 100.0,  # Convert to decimal
                'sharpe_ratio': strategy.sharpe_ratio,
                'max_drawdown': strategy.max_drawdown,
                'win_rate': strategy.win_rate,
                'volatility': self._estimate_volatility_from_sharpe(strategy.expected_return / 100.0, strategy.sharpe_ratio),
                'selection_score': getattr(selected_strategy, 'selection_score', 0.5)
            }

            strategy_data[strategy.strategy_id] = data

        return strategy_data

    def _estimate_volatility_from_sharpe(self, return_pct: float, sharpe_ratio: float) -> float:
        """Estimate volatility from return and Sharpe ratio."""
        if sharpe_ratio == 0:
            return 0.20  # Default 20% annual volatility

        # Sharpe = Return / Volatility (roughly, assuming risk-free rate ≈ 0)
        estimated_vol = abs(return_pct) / sharpe_ratio if sharpe_ratio != 0 else 0.20
        return max(estimated_vol, 0.05)  # Minimum 5% volatility

    def _kelly_criterion_allocation(self, strategy_data: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
        """Calculate Kelly Criterion optimal allocation."""
        allocations = {}

        # Calculate Kelly fractions for each strategy
        kelly_fractions = {}
        for strategy_id, data in strategy_data.items():
            # Kelly formula: f* = μ/σ² (simplified)
            expected_return = data['expected_return']
            volatility = data['volatility']
            win_rate = data['win_rate']

            # Simplified Kelly: f = (win_rate * expected_return) / volatility²
            if volatility > 0:
                kelly_fraction = (win_rate * expected_return) / (volatility ** 2)
                # Conservative Kelly: use half Kelly for safety
                kelly_fractions[strategy_id] = max(0, kelly_fraction * 0.5)

        # Normalize to sum to 1
        total_kelly = sum(kelly_fractions.values())
        if total_kelly > 0:
            allocations = {sid: (fraction / total_kelly) for sid, fraction in kelly_fractions.items()}
        else:
            # Fallback to equal weight if all Kelly fractions are 0
            allocations = {sid: (1.0 / len(strategy_data)) for sid in strategy_data.keys()}

        return allocations

    def _risk_parity_allocation(self, strategy_data: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
        """Calculate Risk Parity allocation (equal risk contribution)."""
        # Risk Parity: weights inversely proportional to variance
        allocations = {}

        # Calculate inverse variance weights
        inv_var_weights = {}
        for strategy_id, data in strategy_data.items():
            volatility = data['volatility']
            variance = volatility ** 2
            inv_var_weights[strategy_id] = 1.0 / variance if variance > 0 else 1.0

        # Normalize weights
        total_inv_var = sum(inv_var_weights.values())
        if total_inv_var > 0:
            allocations = {sid: (weight / total_inv_var) for sid, weight in inv_var_weights.items()}

        return allocations

    def _target_volatility_allocation(self, strategy_data: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
        """Calculate target volatility allocation."""
        # Start with equal weights and scale to target volatility
        n_strategies = len(strategy_data)
        equal_weights = {sid: (1.0 / n_strategies) for sid in strategy_data.keys()}

        # Calculate portfolio volatility with equal weights
        portfolio_vol = self._calculate_portfolio_volatility(equal_weights, strategy_data)

        # Scale factor to reach target volatility
        target_vol = self.risk_params.target_volatility
        scale_factor = target_vol / portfolio_vol if portfolio_vol > 0 else 1.0

        # Apply scaling (capped at 2x for safety)
        scale_factor = min(scale_factor, 2.0)
        allocations = {sid: (weight * scale_factor) for sid, weight in equal_weights.items()}

        # Renormalize to sum to 1
        total_weight = sum(allocations.values())
        if total_weight > 0:
            allocations = {sid: (weight / total_weight) for sid, weight in allocations.items()}

        return allocations

    def _cvar_optimization_allocation(self, strategy_data: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
        """Calculate CVaR (Conditional Value at Risk) optimal allocation."""
        # Simplified CVaR optimization using drawdown expectations
        allocations = {}

        # Calculate risk-adjusted weights (accounting for tail risk)
        risk_adjusted_weights = {}
        for strategy_id, data in strategy_data.items():
            expected_return = data['expected_return']
            max_drawdown = data['max_drawdown']
            sharpe_ratio = data['sharpe_ratio']

            # Risk-adjusted return: return / drawdown risk
            if max_drawdown > 0:
                risk_adjusted = expected_return / max_drawdown
            else:
                risk_adjusted = expected_return

            # Adjust by Sharpe ratio
            risk_adjusted_weights[strategy_id] = risk_adjusted * (1 + sharpe_ratio / 2.0)

        # Normalize and ensure positive weights only
        total_weight = sum(max(0, w) for w in risk_adjusted_weights.values())
        if total_weight > 0:
            allocations = {sid: (max(0, w) / total_weight) for sid, w in risk_adjusted_weights.items()}

        return allocations

    def _regime_adaptive_allocation(self, strategy_data: Dict[str, Dict[str, Any]], current_regime: str) -> Dict[str, float]:
        """Calculate regime-adaptive allocation based on market conditions."""
        # Base allocation using Kelly Criterion
        base_allocations = self._kelly_criterion_allocation(strategy_data)

        # Adjust based on regime-specific performance
        regime_adjustments = {
            'TRENDING_UP': 1.2,      # Boost trend-following strategies
            'TRENDING_DOWN': 1.2,    # Boost short/bearish strategies
            'SIDEWAYS': 1.1,         # Boost mean-reversion strategies
            'HIGH_VOLATILITY': 0.8,  # Reduce allocation in high vol
            'LOW_VOLATILITY': 1.1,   # Increase allocation in low vol
            'LIQUIDITY_CRUNCH': 0.7, # Reduce allocation significantly
            'LIQUIDITY_ABUNDANT': 1.2 # Increase allocation
        }

        regime_multiplier = regime_adjustments.get(current_regime, 1.0)

        # Apply regime adjustment
        adjusted_allocations = {sid: (weight * regime_multiplier) for sid, weight in base_allocations.items()}

        # Renormalize
        total_weight = sum(adjusted_allocations.values())
        if total_weight > 0:
            adjusted_allocations = {sid: (weight / total_weight) for sid, weight in adjusted_allocations.items()}

        return adjusted_allocations

    def _equal_weight_allocation(self, strategy_data: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
        """Calculate equal weight (1/N) allocation."""
        n_strategies = len(strategy_data)
        return {sid: (1.0 / n_strategies) for sid in strategy_data.keys()}

    def _apply_risk_constraints(self, allocations: Dict[str, float], strategy_data: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
        """Apply portfolio risk constraints to allocations."""
        constrained = allocations.copy()

        # Apply single strategy weight limit
        max_weight = self.risk_params.max_single_strategy_weight
        for strategy_id in constrained:
            if constrained[strategy_id] > max_weight:
                constrained[strategy_id] = max_weight

        # Renormalize after applying constraints
        total_weight = sum(constrained.values())
        if total_weight > 0:
            constrained = {sid: (weight / total_weight) for sid, weight in constrained.items()}

        return constrained

    def _calculate_portfolio_metrics(self, allocations: Dict[str, float], strategy_data: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
        """Calculate expected portfolio metrics."""
        # Calculate expected portfolio return
        expected_return = sum(
            allocations[sid] * data['expected_return']
            for sid, data in strategy_data.items()
        )

        # Calculate portfolio volatility (simplified, assuming correlations = 0)
        portfolio_variance = sum(
            (allocations[sid] ** 2) * (data['volatility'] ** 2)
            for sid, data in strategy_data.items()
        )
        expected_volatility = np.sqrt(portfolio_variance)

        # Calculate Sharpe ratio
        sharpe_ratio = expected_return / expected_volatility if expected_volatility > 0 else 0

        return {
            'expected_return': expected_return,
            'expected_volatility': expected_volatility,
            'sharpe_ratio': sharpe_ratio
        }

    def _calculate_portfolio_volatility(self, allocations: Dict[str, float], strategy_data: Dict[str, Dict[str, Any]]) -> float:
        """Calculate portfolio volatility for allocation."""
        portfolio_variance = sum(
            (allocations[sid] ** 2) * (data['volatility'] ** 2)
            for sid, data in strategy_data.items()
        )
        return np.sqrt(portfolio_variance)

    def _check_rebalance_necessity(self, current_regime: str) -> Tuple[bool, str]:
        """Check if portfolio rebalancing is needed."""
        # Check if current regime differs from last allocation regime
        last_regime = getattr(self, '_last_allocation_regime', None)

        if last_regime and last_regime != current_regime:
            return True, f"regime_change_from_{last_regime}_to_{current_regime}"

        # Check if any strategy has deviated significantly from target allocation
        for strategy_id, allocation in self.current_allocations.items():
            weight_deviation = abs(allocation.allocation_weight - allocation.target_weight)
            if weight_deviation > 0.10:  # 10% deviation threshold
                return True, f"strategy_{strategy_id}_deviation_{weight_deviation:.1%}"

        # Check if it's been too long since last rebalance
        if self.portfolio_state and self.portfolio_state.last_rebalance:
            days_since_rebalance = (datetime.now() - self.portfolio_state.last_rebalance).days
            if days_since_rebalance > 7:  # Weekly rebalance check
                return True, f"scheduled_weekly_rebalance"

        return False, "no_rebalance_needed"

    def _create_strategy_list_from_allocations(self) -> List[Any]:
        """Create strategy list from current allocations for rebalancing."""
        # This would create SelectedStrategy-like objects from current allocations
        # For now, return empty list (would be implemented in full system)
        return []

    def _update_portfolio_from_allocation(self, allocation: PortfolioAllocation):
        """Update portfolio state from new allocation."""
        # Store last regime
        if 'current_regime' in allocation.allocation_metadata:
            self._last_allocation_regime = allocation.allocation_metadata['current_regime']

        # Update portfolio state
        if self.portfolio_state:
            self.portfolio_state.last_rebalance = datetime.now()
            self.portfolio_state.status = PortfolioStatus.REBALANCING

    def _load_portfolio_state(self):
        """Load portfolio state from database (placeholder for persistence)."""
        # In full implementation, would load from database
        pass

    def get_portfolio_performance(self) -> Dict[str, Any]:
        """Get detailed portfolio performance metrics."""
        portfolio_state = self.get_portfolio_state()

        return {
            'portfolio_state': portfolio_state.to_dict(),
            'performance_summary': {
                'total_return': portfolio_state.portfolio_return,
                'annualized_return': portfolio_state.portfolio_return,  # Simplified
                'sharpe_ratio': portfolio_state.sharpe_ratio,
                'max_drawdown': portfolio_state.max_drawdown,
                'current_drawdown': portfolio_state.current_drawdown,
                'volatility': portfolio_state.portfolio_volatility
            },
            'strategy_breakdown': [
                {
                    'strategy_id': alloc.strategy_id,
                    'weight': alloc.allocation_weight,
                    'return': alloc.strategy_return,
                    'pnl_unrealized': alloc.unrealized_pnl,
                    'pnl_realized': alloc.realized_pnl
                }
                for alloc in portfolio_state.allocations
            ],
            'risk_metrics': self.risk_params.to_dict(),
            'statistics': {
                'total_allocations': self.total_allocations,
                'total_rebalances': self.total_rebalances,
                'allocation_methods_used': self.allocation_methods_used
            }
        }

    def update_strategy_performance(self, strategy_id: str, current_value: float, realized_pnl: float = 0.0):
        """Update performance tracking for a specific strategy."""
        if strategy_id not in self.current_allocations:
            logger.warning(f"Strategy {strategy_id} not found in current allocations")
            return

        allocation = self.current_allocations[strategy_id]
        allocation.current_value = current_value
        allocation.realized_pnl += realized_pnl
        allocation.unrealized_pnl = current_value - allocation.capital_allocated - allocation.realized_pnl

        # Calculate strategy return
        if allocation.capital_allocated > 0:
            allocation.strategy_return = (current_value - allocation.realized_pnl) / allocation.capital_allocated - 1.0

        logger.debug(f"Updated performance for {strategy_id}: return={allocation.strategy_return:.2%}")

    def get_manager_stats(self) -> Dict[str, Any]:
        """Get portfolio manager statistics."""
        return {
            'total_capital': self.total_capital,
            'allocation_method': self.allocation_method.value,
            'current_allocations_count': len(self.current_allocations),
            'total_allocations': self.total_allocations,
            'total_rebalances': self.total_rebalances,
            'allocation_methods_used': self.allocation_methods_used,
            'portfolio_status': self.portfolio_state.status.value if self.portfolio_state else 'not_initialized',
            'risk_parameters': self.risk_params.to_dict()
        }


# Global portfolio manager instance
_portfolio_manager: Optional[PortfolioManager] = None


def get_portfolio_manager(
    total_capital: float = 10000.0,
    allocation_method: AllocationMethod = AllocationMethod.KELLY_CRITERION
) -> PortfolioManager:
    """Get global portfolio manager instance."""
    global _portfolio_manager
    if _portfolio_manager is None:
        _portfolio_manager = PortfolioManager(total_capital=total_capital, allocation_method=allocation_method)
    return _portfolio_manager


if __name__ == "__main__":
    # Test the portfolio manager
    print("Testing Portfolio Manager...")

    # Create a test portfolio manager
    manager = get_portfolio_manager(total_capital=10000.0)

    # Get initial portfolio state
    state = manager.get_portfolio_state()
    print(f"Initial Portfolio State:")
    print(f"  Total Capital: ${state.total_capital:,.2f}")
    print(f"  Available Capital: ${state.available_capital:,.2f}")
    print(f"  Status: {state.status.value}")

    print(f"\n✨ Portfolio Manager is ready for multi-strategy coordination!")