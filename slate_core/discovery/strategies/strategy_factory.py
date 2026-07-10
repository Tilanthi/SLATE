#!/usr/bin/env python3
"""
Strategy Factory Implementation

Factory pattern for creating concrete strategy implementations from hypotheses.
This is the critical translation layer that connects abstract hypotheses to executable strategies.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from slate_core.discovery.strategies.momentum_strategy import MomentumStrategy, create_momentum_strategy
from slate_core.discovery.strategies.mean_reversion_strategy import MeanReversionStrategy, create_mean_reversion_strategy
from slate_core.discovery.strategies.breakout_strategy import BreakoutStrategy, create_breakout_strategy
from slate_core.discovery.strategies.funding_arbitrage_strategy import FundingArbitrageStrategy, create_funding_arbitrage_strategy
from slate_core.discovery.closed_loop_discovery import StrategyHypothesis, HypothesisType

logger = logging.getLogger(__name__)


class StrategyFactory:
    """
    Factory pattern for creating concrete strategy implementations from hypotheses.

    This class provides the critical translation layer between abstract strategy hypotheses
    and concrete executable strategy implementations. It follows the established SLATE patterns
    and maintains compatibility with the existing backtest system.

    Usage:
        factory = StrategyFactory()
        strategy = factory.create_strategy(hypothesis)
        signal_function = factory.create_signal_function(strategy)
    """

    # Strategy type mapping - connects hypothesis types to concrete implementations
    STRATEGY_MAP = {
        HypothesisType.MOMENTUM: {
            'class': MomentumStrategy,
            'factory': create_momentum_strategy,
            'name': 'momentum'
        },
        HypothesisType.MEAN_REVERSION: {
            'class': MeanReversionStrategy,
            'factory': create_mean_reversion_strategy,
            'name': 'mean_reversion'
        },
        HypothesisType.BREAKOUT: {
            'class': BreakoutStrategy,
            'factory': create_breakout_strategy,
            'name': 'breakout'
        },
        HypothesisType.FUNDING_ARBITRAGE: {
            'class': FundingArbitrageStrategy,
            'factory': create_funding_arbitrage_strategy,
            'name': 'funding_arbitrage'
        },
        # Note: REGIME_SWITCHING is handled separately in backtest due to special AdaptiveRegimeSwitchingStrategy
    }

    def __init__(self):
        """Initialize StrategyFactory."""
        self.strategies_created = 0
        self.creation_history = []

        logger.info("StrategyFactory initialized with strategy mappings for: "
                   f"{list(self.STRATEGY_MAP.keys())}")

    def create_strategy(self, hypothesis: StrategyHypothesis) -> Any:
        """
        Create concrete strategy from hypothesis.

        This is the main translation method that converts abstract hypotheses into
        concrete executable strategy implementations.

        Args:
            hypothesis: StrategyHypothesis with strategy_design containing parameters

        Returns:
            Concrete strategy instance (MomentumStrategy, MeanReversionStrategy, etc.)

        Raises:
            ValueError: If hypothesis type has no implementation
            KeyError: If required parameters are missing
        """
        hypothesis_type = hypothesis.hypothesis_type

        # Check if hypothesis type has a concrete implementation
        if hypothesis_type not in self.STRATEGY_MAP:
            raise ValueError(f"No concrete implementation for hypothesis type: {hypothesis_type}")

        try:
            # Extract parameters from hypothesis.strategy_design
            params = self._extract_parameters(hypothesis)

            # Create strategy using factory function
            strategy_info = self.STRATEGY_MAP[hypothesis_type]
            factory_function = strategy_info['factory']
            strategy = factory_function(params)

            # Track creation
            self.strategies_created += 1
            self.creation_history.append({
                'timestamp': datetime.now(),
                'hypothesis_name': hypothesis.name,
                'hypothesis_type': hypothesis_type.value,
                'strategy_class': strategy.__class__.__name__,
                'parameters': params
            })

            logger.info(f"Created {strategy.__class__.__name__} from hypothesis '{hypothesis.name}'")

            return strategy

        except Exception as e:
            logger.error(f"Error creating strategy for hypothesis '{hypothesis.name}': {e}")
            raise

    def create_signal_function(self, strategy: Any):
        """
        Create signal function for backtest engine compatibility.

        The backtest engine expects a function with signature: signal_function(df, i, params) -> int
        This method wraps the strategy's generate_signal method into that interface.

        Args:
            strategy: Concrete strategy instance

        Returns:
            Signal function compatible with backtest engine
        """
        def signal_function(df, i, params=None):
            """Wrapper function for backtest compatibility."""
            try:
                return strategy.generate_signal(df, i, params)
            except Exception as e:
                logger.warning(f"Error in signal_function at bar {i}: {e}")
                return 0

        return signal_function

    def _extract_parameters(self, hypothesis: StrategyHypothesis) -> Dict[str, Any]:
        """
        Extract concrete parameters from hypothesis.strategy_design.

        This method translates the abstract strategy_design dictionary into concrete
        parameters that can be passed to strategy constructors.

        Args:
            hypothesis: StrategyHypothesis with strategy_design dict

        Returns:
            Dictionary of concrete parameters for strategy constructor
        """
        design = hypothesis.strategy_design
        hypothesis_type = hypothesis.hypothesis_type

        # Extract parameters based on hypothesis type
        if hypothesis_type == HypothesisType.MOMENTUM:
            return self._extract_momentum_parameters(design)

        elif hypothesis_type == HypothesisType.MEAN_REVERSION:
            return self._extract_mean_reversion_parameters(design)

        elif hypothesis_type == HypothesisType.BREAKOUT:
            return self._extract_breakout_parameters(design)

        elif hypothesis_type == HypothesisType.FUNDING_ARBITRAGE:
            return self._extract_funding_arbitrage_parameters(design)

        else:
            # Default empty parameters
            return {}

    def _extract_momentum_parameters(self, design: Dict[str, Any]) -> Dict[str, Any]:
        """Extract parameters for momentum strategy."""
        return {
            'fast_ema': design.get('fast_ema', design.get('entry_ema', 12)),
            'slow_ema': design.get('slow_ema', design.get('exit_ema', 26)),
            'signal_ema': design.get('signal_ema', 9),
            'allow_short_selling': design.get('allow_short_selling', True)
        }

    def _extract_mean_reversion_parameters(self, design: Dict[str, Any]) -> Dict[str, Any]:
        """Extract parameters for mean reversion strategy."""
        return {
            'bb_period': design.get('bb_period', design.get('bollinger_period', 20)),
            'bb_std': design.get('bb_std', design.get('bollinger_std', 2.0)),
            'rsi_period': design.get('rsi_period', 14),
            'rsi_oversold': design.get('rsi_oversold', 30),
            'rsi_overbought': design.get('rsi_overbought', 70),
            'signal_logic': design.get('signal_logic', 'OR')
        }

    def _extract_breakout_parameters(self, design: Dict[str, Any]) -> Dict[str, Any]:
        """Extract parameters for breakout strategy."""
        return {
            'lookback': design.get('lookback', design.get('breakout_lookback', 20)),
            'bb_std': design.get('bb_std', design.get('bollinger_std', 2.0)),
            'squeeze_threshold': design.get('squeeze_threshold', 0.7),
            'atr_confirmation': design.get('atr_confirmation', True),
            'atr_period': design.get('atr_period', 14),
            'atr_multiplier': design.get('atr_multiplier', 1.5)
        }

    def _extract_funding_arbitrage_parameters(self, design: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract parameters for funding arbitrage strategy.

        CRITICAL FIX: Convert percentage strings to numeric values to prevent
        TypeError in signal generation comparisons.
        """
        # Handle percentage strings like '0.01%' → 0.0001
        funding_threshold = design.get('funding_threshold', design.get('entry_threshold', '0.01%'))

        # Convert percentage string to numeric if needed
        if isinstance(funding_threshold, str):
            if '%' in funding_threshold:
                # Remove % and convert to decimal (e.g., '0.01%' → 0.0001)
                funding_threshold = float(funding_threshold.rstrip('%')) / 100
            else:
                funding_threshold = float(funding_threshold)

        return {
            'funding_threshold': funding_threshold,  # Now guaranteed to be numeric
            'holding_period_hours': design.get('holding_period', design.get('holding_period_hours', '8')),
            'max_holding_periods': int(design.get('max_holding_periods', design.get('max_periods', 3))),
            'rate_threshold': design.get('rate_threshold', 0.02)
        }

    def get_supported_types(self) -> list:
        """Get list of supported hypothesis types."""
        return list(self.STRATEGY_MAP.keys())

    def supports_regime_switching(self) -> bool:
        """Check if factory supports regime switching (special handling)."""
        return True  # Regime switching is handled separately in backtest system

    def get_factory_summary(self) -> Dict[str, Any]:
        """Get summary of factory activity."""
        return {
            'strategies_created': self.strategies_created,
            'supported_types': [htype.value for htype in self.STRATEGY_MAP.keys()],
            'recent_creations': self.creation_history[-10:] if self.creation_history else []
        }

    def reset_statistics(self):
        """Reset factory statistics."""
        self.strategies_created = 0
        self.creation_history = []


# Global factory instance for convenience
_global_factory: Optional[StrategyFactory] = None


def get_strategy_factory() -> StrategyFactory:
    """Get global strategy factory instance."""
    global _global_factory
    if _global_factory is None:
        _global_factory = StrategyFactory()
    return _global_factory


def create_strategy_from_hypothesis(hypothesis: StrategyHypothesis) -> Any:
    """
    Convenience function to create strategy from hypothesis.

    Args:
        hypothesis: StrategyHypothesis to convert to concrete strategy

    Returns:
        Concrete strategy instance
    """
    factory = get_strategy_factory()
    return factory.create_strategy(hypothesis)
