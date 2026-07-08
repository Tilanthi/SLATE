#!/usr/bin/env python3
"""
Momentum Strategy Implementation

EMA crossover momentum strategy for trending markets.
Following the AdaptiveRegimeSwitchingStrategy pattern.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class MomentumStrategy:
    """
    EMA crossover momentum strategy for trending markets.

    This strategy generates signals based on exponential moving average (EMA) crossovers:
    - Golden cross (fast EMA crosses above slow EMA) → Buy signal (1)
    - Death cross (fast EMA crosses below slow EMA) → Sell signal (-1)
    - Maintain position when trend is still active

    Suitable for trending markets where price momentum persists.
    """

    def __init__(self, fast_ema: int = 12, slow_ema: int = 26, signal_ema: int = 9,
                 allow_short_selling: bool = True):
        """
        Initialize MomentumStrategy.

        Args:
            fast_ema: Fast EMA period (default 12)
            slow_ema: Slow EMA period (default 26)
            signal_ema: Signal line EMA period for MACD-style confirmation (default 9)
            allow_short_selling: Whether to generate short signals (default True)
        """
        self.fast_ema = fast_ema
        self.slow_ema = slow_ema
        self.signal_ema = signal_ema
        self.allow_short_selling = allow_short_selling

        # Performance tracking
        self.signals_generated = 0
        self.golden_crosses = 0
        self.death_crosses = 0

        logger.info(f"MomentumStrategy initialized: fast_ema={fast_ema}, slow_ema={slow_ema}")

    def generate_signal(self, df: pd.DataFrame, i: int, params: Dict[str, Any] = None) -> int:
        """
        Generate momentum signal using EMA crossover.

        Args:
            df: Complete DataFrame with historical data (must include 'close' column)
            i: Current bar index
            params: Optional strategy parameters (overrides instance defaults)

        Returns:
            1 (LONG), -1 (SHORT), or 0 (no position)
        """
        if params is None:
            params = {}

        # Extract parameters (use params if provided, otherwise use instance defaults)
        fast_period = int(params.get('fast_ema', self.fast_ema))
        slow_period = int(params.get('slow_ema', self.slow_ema))

        # Minimum data requirement
        lookback_required = slow_period + 5
        if i < lookback_required:
            return 0

        # Get historical data for EMA calculation
        lookback_df = df.iloc[max(0, i - slow_period + 5):i + 1].copy()

        if len(lookback_df) < slow_period:
            return 0

        try:
            # Calculate EMAs using exponential weighted mean
            fast_ema_values = lookback_df['close'].ewm(span=fast_period, adjust=False).mean()
            slow_ema_values = lookback_df['close'].ewm(span=slow_period, adjust=False).mean()

            # Need at least 2 values to detect crossover
            if len(fast_ema_values) < 2 or len(slow_ema_values) < 2:
                return 0

            # Current and previous EMA values
            fast_ema_current = fast_ema_values.iloc[-1]
            slow_ema_current = slow_ema_values.iloc[-1]
            fast_ema_prev = fast_ema_values.iloc[-2]
            slow_ema_prev = slow_ema_values.iloc[-2]

            # Check for NaN values
            if pd.isna(fast_ema_current) or pd.isna(slow_ema_current) or \
               pd.isna(fast_ema_prev) or pd.isna(slow_ema_prev):
                return 0

            # Detect EMA crossover
            signal = 0

            # Golden cross: fast EMA crosses above slow EMA
            if fast_ema_current > slow_ema_current and fast_ema_prev <= slow_ema_prev:
                signal = 1  # Buy signal
                self.golden_crosses += 1
                logger.debug(f"Golden cross at bar {i}: fast EMA ({fast_ema_current:.2f}) > slow EMA ({slow_ema_current:.2f})")

            # Death cross: fast EMA crosses below slow EMA
            elif fast_ema_current < slow_ema_current and fast_ema_prev >= slow_ema_prev:
                if self.allow_short_selling:
                    signal = -1  # Sell signal
                    self.death_crosses += 1
                    logger.debug(f"Death cross at bar {i}: fast EMA ({fast_ema_current:.2f}) < slow EMA ({slow_ema_current:.2f})")
                else:
                    signal = 0  # Exit only, no short selling

            else:
                # Maintain existing position if trend is still active
                if fast_ema_current > slow_ema_current:
                    signal = 1  # Hold long position
                elif fast_ema_current < slow_ema_current:
                    if self.allow_short_selling:
                        signal = -1  # Hold short position
                    else:
                        signal = 0  # Exit position
                else:
                    signal = 0  # EMAs equal, no position

            # Track signal generation
            if signal != 0:
                self.signals_generated += 1

            return signal

        except Exception as e:
            logger.warning(f"Error generating momentum signal at bar {i}: {e}")
            return 0

    def get_strategy_summary(self) -> Dict[str, Any]:
        """Get summary of strategy performance."""
        return {
            'strategy_type': 'momentum',
            'fast_ema': self.fast_ema,
            'slow_ema': self.slow_ema,
            'signal_ema': self.signal_ema,
            'signals_generated': self.signals_generated,
            'golden_crosses': self.golden_crosses,
            'death_crosses': self.death_crosses,
            'allow_short_selling': self.allow_short_selling
        }

    def reset_statistics(self):
        """Reset performance statistics."""
        self.signals_generated = 0
        self.golden_crosses = 0
        self.death_crosses = 0


def create_momentum_strategy(params: Dict[str, Any] = None) -> MomentumStrategy:
    """
    Factory function to create MomentumStrategy with parameters.

    Args:
        params: Optional parameters dictionary
            - fast_ema: Fast EMA period (default 12)
            - slow_ema: Slow EMA period (default 26)
            - signal_ema: Signal line period (default 9)
            - allow_short_selling: Allow short signals (default True)

    Returns:
        Configured MomentumStrategy instance
    """
    if params is None:
        params = {}

    return MomentumStrategy(
        fast_ema=params.get('fast_ema', 12),
        slow_ema=params.get('slow_ema', 26),
        signal_ema=params.get('signal_ema', 9),
        allow_short_selling=params.get('allow_short_selling', True)
    )
