#!/usr/bin/env python3
"""
Funding Arbitrage Strategy Implementation

Perpetual futures funding rate arbitrage strategy.
Following the AdaptiveRegimeSwitchingStrategy pattern.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class FundingArbitrageStrategy:
    """
    Perpetual futures funding rate arbitrage strategy.

    This strategy generates signals based on funding rate arbitrage opportunities:
    - Positive funding rate (longs pay shorts) → Short signal to receive funding
    - Negative funding rate (shorts pay longs) → Long signal to receive funding
    - Uses threshold-based entry to avoid whipsaws
    - Implements position sizing based on funding rate magnitude

    Suitable for perpetual futures markets where funding rates create periodic income opportunities.
    This is a market-neutral strategy focusing on funding rate capture rather than directional price moves.
    """

    def __init__(self, funding_threshold: float = 0.0001, holding_period_hours: int = 8,
                 max_holding_periods: int = 3, rate_threshold: float = 0.02):
        """
        Initialize FundingArbitrageStrategy.

        Args:
            funding_threshold: Minimum funding rate to generate signal (default 0.0001 = 0.01%)
            holding_period_hours: Position holding period in hours (default 8, typical funding interval)
            max_holding_periods: Maximum number of funding periods to hold position (default 3)
            rate_threshold: Maximum funding rate before position becomes too risky (default 0.02 = 2%)
        """
        self.funding_threshold = funding_threshold
        self.holding_period_hours = holding_period_hours
        self.max_holding_periods = max_holding_periods
        self.rate_threshold = rate_threshold

        # Performance tracking
        self.signals_generated = 0
        self.long_signals = 0  # Negative funding rate → receive funding as long
        self.short_signals = 0  # Positive funding rate → receive funding as short
        self.positions_entered = 0

        logger.info(f"FundingArbitrageStrategy initialized: threshold={funding_threshold}, "
                   f"holding_period={holding_period_hours}h, max_periods={max_holding_periods}")

    def generate_signal(self, df: pd.DataFrame, i: int, params: Dict[str, Any] = None) -> int:
        """
        Generate funding arbitrage signal based on funding rates.

        Args:
            df: Complete DataFrame with historical data (must include 'funding_rate' column)
            i: Current bar index
            params: Optional strategy parameters (overrides instance defaults)

        Returns:
            1 (LONG), -1 (SHORT), or 0 (no position)
        """
        if params is None:
            params = {}

        # Extract parameters
        funding_threshold = float(params.get('funding_threshold', self.funding_threshold))
        max_holding_periods = int(params.get('max_holding_periods', self.max_holding_periods))
        rate_threshold = float(params.get('rate_threshold', self.rate_threshold))

        # Minimum data requirement
        if i < 10:
            return 0

        try:
            # Check if funding_rate column exists
            if 'funding_rate' not in df.columns:
                logger.warning("funding_rate column not found in DataFrame")
                return 0

            current_funding_rate = df['funding_rate'].iloc[i]

            # Check for NaN values
            if pd.isna(current_funding_rate):
                return 0

            # Safety check: funding rate too extreme indicates potential data error or crisis
            if abs(current_funding_rate) > rate_threshold:
                logger.debug(f"Funding rate too extreme at bar {i}: {current_funding_rate:.4f}")
                return 0

            # Calculate moving average of funding rates for trend confirmation
            funding_lookback = min(20, i)
            funding_history = df['funding_rate'].iloc[i - funding_lookback:i + 1]
            avg_funding_rate = funding_history.mean()

            # Calculate funding rate trend
            recent_funding = df['funding_rate'].iloc[max(0, i - 5):i + 1]
            funding_trend = recent_funding.mean()

            # Generate signals based on funding rate
            signal = 0

            # Positive funding rate (longs pay shorts) → Short to receive funding
            if current_funding_rate > funding_threshold:
                # Additional confirmation: funding rate trend should be positive
                if funding_trend > 0:
                    signal = -1  # Short position to receive funding
                    self.short_signals += 1
                    logger.debug(f"Short signal at bar {i}: funding_rate={current_funding_rate:.4f} (positive)")

            # Negative funding rate (shorts pay longs) → Long to receive funding
            elif current_funding_rate < -funding_threshold:
                # Additional confirmation: funding rate trend should be negative
                if funding_trend < 0:
                    signal = 1  # Long position to receive funding
                    self.long_signals += 1
                    logger.debug(f"Long signal at bar {i}: funding_rate={current_funding_rate:.4f} (negative)")

            # Track signal generation
            if signal != 0:
                self.signals_generated += 1
                self.positions_entered += 1

            return signal

        except Exception as e:
            logger.warning(f"Error generating funding arbitrage signal at bar {i}: {e}")
            return 0

    def calculate_position_size(self, funding_rate: float, base_position_size: float = 1.0) -> float:
        """
        Calculate position size based on funding rate magnitude.

        Higher funding rates → larger position sizes (within reason).
        This scales opportunity with expected return.

        Args:
            funding_rate: Current funding rate
            base_position_size: Base position size multiplier (default 1.0)

        Returns:
            Adjusted position size multiplier
        """
        # Scale position size by funding rate magnitude
        # More extreme funding rates → larger positions (but capped)
        rate_magnitude = abs(funding_rate)
        scaling_factor = min(rate_magnitude / 0.001, 2.0)  # Cap at 2x base size

        return base_position_size * scaling_factor

    def estimate_funding_income(self, funding_rate: float, position_size: float,
                                holding_periods: int = 1) -> float:
        """
        Estimate expected funding income for a position.

        Args:
            funding_rate: Current funding rate (per 8 hours)
            position_size: Position size in USDT
            holding_periods: Number of funding periods to hold (default 1)

        Returns:
            Expected funding income in USDT
        """
        # Funding income = position_size * funding_rate * holding_periods
        # For short positions: positive funding_rate = positive income
        # For long positions: negative funding_rate = positive income
        return position_size * abs(funding_rate) * holding_periods

    def get_strategy_summary(self) -> Dict[str, Any]:
        """Get summary of strategy performance."""
        return {
            'strategy_type': 'funding_arbitrage',
            'funding_threshold': self.funding_threshold,
            'holding_period_hours': self.holding_period_hours,
            'max_holding_periods': self.max_holding_periods,
            'rate_threshold': self.rate_threshold,
            'signals_generated': self.signals_generated,
            'long_signals': self.long_signals,
            'short_signals': self.short_signals,
            'positions_entered': self.positions_entered
        }

    def reset_statistics(self):
        """Reset performance statistics."""
        self.signals_generated = 0
        self.long_signals = 0
        self.short_signals = 0
        self.positions_entered = 0


def create_funding_arbitrage_strategy(params: Dict[str, Any] = None) -> FundingArbitrageStrategy:
    """
    Factory function to create FundingArbitrageStrategy with parameters.

    Args:
        params: Optional parameters dictionary
            - funding_threshold: Minimum funding rate to generate signal (default 0.0001)
            - holding_period_hours: Position holding period in hours (default 8)
            - max_holding_periods: Maximum funding periods to hold (default 3)
            - rate_threshold: Maximum funding rate before too risky (default 0.02)

    Returns:
        Configured FundingArbitrageStrategy instance
    """
    if params is None:
        params = {}

    return FundingArbitrageStrategy(
        funding_threshold=params.get('funding_threshold', 0.0001),
        holding_period_hours=params.get('holding_period_hours', 8),
        max_holding_periods=params.get('max_holding_periods', 3),
        rate_threshold=params.get('rate_threshold', 0.02)
    )
