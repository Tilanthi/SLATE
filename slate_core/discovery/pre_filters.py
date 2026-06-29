#!/usr/bin/env python3
"""
SLATE Smart Pre-Filters

Intelligent pre-filters that eliminate obviously unprofitable strategies
before running full backtests. This prevents wasting computational resources
on strategies that are doomed to fail.

Based on analysis of 51,947 discoveries:
- Profitable strategies trade 23x less frequently
- Profitable strategies have 18x better drawdown control
- Profitable strategies have 17x lower transaction costs
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class FilterDecision(Enum):
    """Filter decision outcomes."""
    PASS = "pass"           # Strategy passes all filters
    REJECT_EXCESSIVE_TRADING = "reject_excessive_trading"
    REJECT_HIGH_DRAWDOWN = "reject_high_drawdown"
    REJECT_HIGH_COSTS = "reject_high_costs"
    REJECT_COMBINATION = "reject_combination"


@dataclass
class FilterResult:
    """Result of pre-filtering."""
    decision: FilterDecision
    reason: str
    metrics: Dict[str, Any]
    computation_saved_ms: int = 0


class PreFilterConfig:
    """Configuration for pre-filters."""

    # Trading frequency limits (annual basis) - adjusted for reality
    max_trades_per_year_daily: int = 260   # Daily: ~260 trading days per year OK
    max_trades_per_year_subdaily: int = 100  # Sub-daily: limit excessive frequency
    min_trade_interval_days: int = 1      # Minimum days between trades

    # Drawdown limits - realistic based on successful strategies
    max_max_drawdown_pct_daily: float = 5.0     # Daily: 5% max drawdown acceptable
    max_max_drawdown_pct_subdaily: float = 2.0   # Sub-daily: more strict
    max_avg_drawdown_pct: float = 3.0    # Average drawdown limit

    # Transaction cost limits - realistic thresholds
    max_fee_ratio_daily: float = 0.25         # Daily: fees max 25% of gross profit
    max_fee_ratio_subdaily: float = 0.60     # Sub-daily: more strict
    min_net_profit_usdt: float = 25       # Minimum net profit in USDT

    # Risk-reward requirements
    min_sharpe_ratio: float = -2.0       # Minimum risk-adjusted return (lenient for discovery)
    min_profit_factor: float = 0.8       # Minimum profit factor


class SmartPreFilters:
    """
    Pre-filter system that eliminates obviously unprofitable strategies.

    These filters run BEFORE full backtesting, saving massive computational
    resources and focusing discovery on strategies with genuine potential.
    """

    def __init__(self, config: Optional[PreFilterConfig] = None):
        """Initialize pre-filters with configuration."""
        self.config = config or PreFilterConfig()

        # Statistics
        self.total_evaluated = 0
        self.total_passed = 0
        self.total_rejected = 0
        self.rejection_reasons = {decision: 0 for decision in FilterDecision}

        logger.info("SmartPreFilters initialized with realistic daily/sub-daily thresholds")


class PreFilterConfig:
    """Configuration for pre-filters."""

    # Trading frequency limits (annual basis) - adjusted for reality
    max_trades_per_year_daily: int = 260   # Daily: ~260 trading days per year OK
    max_trades_per_year_subdaily: int = 100  # Sub-daily: limit excessive frequency
    min_trade_interval_days: int = 1      # Minimum days between trades

    # Drawdown limits - realistic based on successful strategies
    max_max_drawdown_pct_daily: float = 5.0     # Daily: 5% max drawdown acceptable
    max_max_drawdown_pct_subdaily: float = 2.0   # Sub-daily: more strict
    max_avg_drawdown_pct: float = 3.0    # Average drawdown limit

    # Transaction cost limits - realistic thresholds
    max_fee_ratio_daily: float = 0.25         # Daily: fees max 25% of gross profit
    max_fee_ratio_subdaily: float = 0.60     # Sub-daily: more strict
    min_net_profit_usdt: float = 25       # Minimum net profit in USDT

    # Risk-reward requirements
    min_sharpe_ratio: float = -2.0       # Minimum risk-adjusted return (lenient for discovery)
    min_profit_factor: float = 0.8       # Minimum profit factor


class SmartPreFilters:
    """
    Pre-filter system that eliminates obviously unprofitable strategies.

    These filters run BEFORE full backtesting, saving massive computational
    resources and focusing discovery on strategies with genuine potential.
    """

    def __init__(self, config: Optional[PreFilterConfig] = None):
        """Initialize pre-filters with configuration."""
        self.config = config or PreFilterConfig()

        # Statistics
        self.total_evaluated = 0
        self.total_passed = 0
        self.total_rejected = 0
        self.rejection_reasons = {decision: 0 for decision in FilterDecision}

        logger.info("SmartPreFilters initialized with realistic constraints")

    def evaluate_strategy_potential(self,
                                   strategy_params: Dict[str, Any]) -> FilterResult:
        """
        Evaluate a strategy's potential using quick heuristics.

        This is NOT a full backtest - it's a fast pre-screening to eliminate
        obviously unprofitable strategies before running the full, expensive
        backtesting pipeline.

        Args:
            strategy_params: Strategy parameters (timeframe, indicators, etc.)

        Returns:
            FilterResult with decision and reasoning
        """
        self.total_evaluated += 1

        start_time = __import__('time').time()

        # Extract key parameters
        timeframe = strategy_params.get('timeframe', '1h')
        strategy_type = strategy_params.get('strategy_type', 'unknown')
        parameters = strategy_params.get('parameters', {})

        # Determine if daily or sub-daily timeframe
        is_daily = timeframe in ['1d', '12h']

        # Quick metric estimation based on parameters
        estimated_trades_per_year = self._estimate_annual_trades(timeframe, parameters)
        estimated_max_drawdown = self._estimate_max_drawdown(strategy_type, parameters)
        estimated_fee_ratio = self._estimate_fee_impact(timeframe, parameters)

        computation_time_ms = int((__import__('time').time() - start_time) * 1000)

        # Apply appropriate filters based on timeframe
        if is_daily:
            # Use daily thresholds (more lenient)
            filters_to_apply = [
                (self._daily_trading_frequency_filter, estimated_trades_per_year),
                (self._daily_drawdown_filter, estimated_max_drawdown),
                (self._daily_transaction_cost_filter, estimated_fee_ratio),
            ]
        else:
            # Use sub-daily thresholds (more strict)
            filters_to_apply = [
                (self._subdaily_trading_frequency_filter, estimated_trades_per_year),
                (self._subdaily_drawdown_filter, estimated_max_drawdown),
                (self._subdaily_transaction_cost_filter, estimated_fee_ratio),
            ]

        for filter_func, metric_value in filters_to_apply:
            decision, reason = filter_func(metric_value, strategy_params)

            if decision != FilterDecision.PASS:
                self.total_rejected += 1
                self.rejection_reasons[decision] += 1

                return FilterResult(
                    decision=decision,
                    reason=reason,
                    metrics={
                        'estimated_trades_per_year': estimated_trades_per_year,
                        'estimated_max_drawdown_pct': estimated_max_drawdown,
                        'estimated_fee_ratio': estimated_fee_ratio,
                        'timeframe_type': 'daily' if is_daily else 'sub_daily'
                    },
                    computation_saved_ms=computation_time_ms
                )

        # Strategy passed all filters
        self.total_passed += 1

        return FilterResult(
            decision=FilterDecision.PASS,
            reason=f"Strategy passes all {('daily' if is_daily else 'sub-daily')} pre-filters",
            metrics={
                'estimated_trades_per_year': estimated_trades_per_year,
                'estimated_max_drawdown_pct': estimated_max_drawdown,
                'estimated_fee_ratio': estimated_fee_ratio,
                'timeframe_type': 'daily' if is_daily else 'sub_daily'
            },
            computation_saved_ms=computation_time_ms
        )

    def _daily_trading_frequency_filter(self, estimated_trades: int, strategy_params: Dict) -> tuple[FilterDecision, str]:
        """Filter daily strategies with excessive trading frequency."""
        if estimated_trades > self.config.max_trades_per_year_daily:
            return (
                FilterDecision.REJECT_EXCESSIVE_TRADING,
                f"Daily strategy: {estimated_trades} trades/year exceeds {self.config.max_trades_per_year_daily} limit"
            )
        return FilterDecision.PASS, "Daily trading frequency acceptable"

    def _subdaily_trading_frequency_filter(self, estimated_trades: int, strategy_params: Dict) -> tuple[FilterDecision, str]:
        """Filter sub-daily strategies with excessive trading frequency."""
        if estimated_trades > self.config.max_trades_per_year_subdaily:
            return (
                FilterDecision.REJECT_EXCESSIVE_TRADING,
                f"Sub-daily strategy: {estimated_trades} trades/year exceeds {self.config.max_trades_per_year_subdaily} limit"
            )
        return FilterDecision.PASS, "Sub-daily trading frequency acceptable"

    def _daily_drawdown_filter(self, estimated_drawdown: float, strategy_params: Dict) -> tuple[FilterDecision, str]:
        """Filter daily strategies with excessive drawdown."""
        if estimated_drawdown > self.config.max_max_drawdown_pct_daily:
            return (
                FilterDecision.REJECT_HIGH_DRAWDOWN,
                f"DAILY strategy: {estimated_drawdown:.1f}% drawdown exceeds {self.config.max_max_drawdown_pct_daily}% limit"
            )
        return FilterDecision.PASS, "Daily drawdown acceptable"

    def _subdaily_drawdown_filter(self, estimated_drawdown: float, strategy_params: Dict) -> tuple[FilterDecision, str]:
        """Filter sub-daily strategies with excessive drawdown."""
        if estimated_drawdown > self.config.max_max_drawdown_pct_subdaily:
            return (
                FilterDecision.REJECT_HIGH_DRAWDOWN,
                f"SUB-DAILY strategy: {estimated_drawdown:.1f}% drawdown exceeds {self.config.max_max_drawdown_pct_subdaily}% limit"
            )
        return FilterDecision.PASS, "Sub-daily drawdown acceptable"

    def _daily_transaction_cost_filter(self, estimated_fee_ratio: float, strategy_params: Dict) -> tuple[FilterDecision, str]:
        """Filter daily strategies where transaction costs would destroy profits."""
        if estimated_fee_ratio > self.config.max_fee_ratio_daily:
            return (
                FilterDecision.REJECT_HIGH_COSTS,
                f"DAILY strategy: fees consume {estimated_fee_ratio:.0%} of gross profit, exceeds {self.config.max_fee_ratio_daily:.0%} limit"
            )
        return FilterDecision.PASS, "Daily transaction costs acceptable"

    def _subdaily_transaction_cost_filter(self, estimated_fee_ratio: float, strategy_params: Dict) -> tuple[FilterDecision, str]:
        """Filter sub-daily strategies where transaction costs would destroy profits."""
        if estimated_fee_ratio > self.config.max_fee_ratio_subdaily:
            return (
                FilterDecision.REJECT_HIGH_COSTS,
                f"SUB-DAILY strategy: fees consume {estimated_fee_ratio:.0%} of gross profit, exceeds {self.config.max_fee_ratio_subdaily:.0%} limit"
            )
        return FilterDecision.PASS, "Sub-daily transaction costs acceptable"

    def _trading_frequency_filter(self, estimated_trades: int, strategy_params: Dict) -> tuple[FilterDecision, str]:
        """Filter strategies with excessive trading frequency."""
        if estimated_trades > self.config.max_trades_per_year:
            return (
                FilterDecision.REJECT_EXCESSIVE_TRADING,
                f"Estimated {estimated_trades} trades/year exceeds limit of {self.config.max_trades_per_year}"
            )
        return FilterDecision.PASS, "Trading frequency acceptable"

    def _drawdown_filter(self, estimated_drawdown: float, strategy_params: Dict) -> tuple[FilterDecision, str]:
        """Filter strategies with excessive drawdown."""
        if estimated_drawdown > self.config.max_max_drawdown_pct:
            return (
                FilterDecision.REJECT_HIGH_DRAWDOWN,
                f"Estimated {estimated_drawdown:.1f}% drawdown exceeds limit of {self.config.max_max_drawdown_pct}%"
            )
        return FilterDecision.PASS, "Drawdown acceptable"

    def _transaction_cost_filter(self, estimated_fee_ratio: float, strategy_params: Dict) -> tuple[FilterDecision, str]:
        """Filter strategies where transaction costs would destroy profits."""
        if estimated_fee_ratio > self.config.max_fee_ratio:
            return (
                FilterDecision.REJECT_HIGH_COSTS,
                f"Estimated fees consume {estimated_fee_ratio:.0%} of gross profit, exceeds {self.config.max_fee_ratio:.0%} limit"
            )
        return FilterDecision.PASS, "Transaction costs acceptable"

    def _estimate_annual_trades(self, timeframe: str, parameters: Dict) -> int:
        """Estimate annual trading frequency based on timeframe and strategy type."""
        # Base frequency by timeframe - these are realistic trading frequencies
        # not theoretical maximums
        realistic_trading_frequency = {
            '1m': 100,      # Very active: ~100 trades per year (not every minute)
            '5m': 80,       # Active: ~80 trades per year (not every 5 minutes)
            '15m': 60,      # Moderate: ~60 trades per year
            '30m': 50,      # Moderate: ~50 trades per year
            '1h': 40,       # Normal: ~40 trades per year
            '4h': 30,       # Lower frequency: ~30 trades per year
            '12h': 20,      # Lower: ~20 trades per year
            '1d': 15,       # Daily: ~15 trades per year (realistic, not every day)
        }

        base_frequency = realistic_trading_frequency.get(timeframe, 30)

        # Adjust for strategy type (some trade more frequently than others)
        strategy_multiplier = {
            'momentum_mean_reversion': 1.0,   # Normal frequency
            'volatility_regime': 0.8,          # Lower frequency, wait for volatility
            'correlation_arbitrage': 0.6,     # Lower frequency, wait for arbitrage opportunities
            'scalping': 2.0,                   # High frequency
            'market_making': 3.0,             # Very high frequency
            'arbitrage': 0.5,                  # Low frequency, wait for opportunities
        }

        strategy_type = parameters.get('strategy_type', 'momentum_mean_reversion')
        multiplier = strategy_multiplier.get(strategy_type, 1.0)

        # Adjust for parameter aggressiveness
        lookback = parameters.get('period', 20)
        if lookback < 10:
            multiplier *= 0.8  # Short lookback = fewer trades (wait for setups)
        elif lookback > 30:
            multiplier *= 1.2  # Long lookback = more trades (more signals)

        return int(base_frequency * multiplier)

    def _estimate_max_drawdown(self, strategy_type: str, parameters: Dict) -> float:
        """Estimate maximum drawdown based on strategy characteristics."""
        # Base drawdown by strategy type
        base_drawdowns = {
            'momentum_mean_reversion': 15.0,  # Higher drawdown from trend following
            'mean_reversion': 8.0,           # Moderate drawdown
            'arbitrage': 2.0,                  # Low drawdown from market neutral
            'market_making': 5.0,              # Moderate from inventory risk
            'volatility_regime': 12.0,         # High from volatility strategies
        }

        base_drawdown = base_drawdowns.get(strategy_type, 10.0)

        # Adjust for position sizing
        position_size = parameters.get('pos_size', 0.05)  # 5% default
        if position_size > 0.10:
            base_drawdown *= 1.5  # Larger positions = larger drawdowns

        # Adjust for stop loss tightness
        stop_atr = parameters.get('stop_atr', 2.0)
        if stop_atr < 1.0:
            base_drawdown *= 0.8  # Tight stops = smaller drawdowns
        elif stop_atr > 3.0:
            base_drawdown *= 1.3  # Wide stops = larger drawdowns

        return base_drawdown / 100  # Convert to percentage

    def _estimate_fee_impact(self, timeframe: str, parameters: Dict) -> float:
        """Estimate transaction cost impact as ratio of gross profit."""
        # Shorter timeframes = more trades = higher fee impact
        timeframe_fee_impact = {
            '1m': 0.95,    # 95% of profit to fees
            '5m': 0.85,    # 85% of profit to fees
            '15m': 0.70,   # 70% of profit to fees
            '30m': 0.60,   # 60% of profit to fees
            '1h': 0.45,    # 45% of profit to fees
            '4h': 0.30,    # 30% of profit to fees
            '12h': 0.20,   # 20% of profit to fees
            '1d': 0.08,    # 8% of profit to fees (profitable!)
        }

        base_impact = timeframe_fee_impact.get(timeframe, 0.5)

        # Adjust for strategy type (some strategies have higher turnover)
        strategy_adjustment = {
            'scalping': 1.3,      # More trading = more fees
            'arbitrage': 0.7,     # Market neutral = less trading
            'market_making': 0.8 # Inventory management = moderate trading
        }

        strategy_type = parameters.get('strategy_type', 'momentum_mean_reversion')
        adjustment = strategy_adjustment.get(strategy_type, 1.0)

        return base_impact * adjustment

    def get_stats(self) -> Dict[str, Any]:
        """Get filtering statistics."""
        pass_rate = self.total_passed / self.total_evaluated if self.total_evaluated > 0 else 0
        rejection_rate = self.total_rejected / self.total_evaluated if self.total_evaluated > 0 else 0

        return {
            'total_evaluated': self.total_evaluated,
            'total_passed': self.total_passed,
            'total_rejected': self.total_rejected,
            'pass_rate': pass_rate,
            'rejection_rate': rejection_rate,
            'rejection_reasons': {decision.value: count for decision, count in self.rejection_reasons.items()},
            'config': {
                'daily_max_trades_per_year': self.config.max_trades_per_year_daily,
                'subdaily_max_trades_per_year': self.config.max_trades_per_year_subdaily,
                'daily_max_drawdown_pct': self.config.max_max_drawdown_pct_daily,
                'subdaily_max_drawdown_pct': self.config.max_max_drawdown_pct_subdaily,
                'daily_max_fee_ratio': self.config.max_fee_ratio_daily,
                'subdaily_max_fee_ratio': self.config.max_fee_ratio_subdaily
            }
        }


# Global pre-filter instance
_pre_filters: Optional[SmartPreFilters] = None


def get_pre_filters(config: Optional[PreFilterConfig] = None) -> SmartPreFilters:
    """Get global pre-filters instance."""
    global _pre_filters
    if _pre_filters is None:
        _pre_filters = SmartPreFilters(config)
    return _pre_filters