#!/usr/bin/env python3
"""
Breakout Strategy Implementation

Volatility breakout strategy for explosive moves.
Following the AdaptiveRegimeSwitchingStrategy pattern.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class BreakoutStrategy:
    """
    Volatility breakout strategy for explosive price moves.

    This strategy generates signals based on volatility expansion after consolidation:
    - Detects Bollinger Band squeeze (low volatility consolidation)
    - Generates signals when price breaks through BB bands with expansion
    - Uses ATR-based confirmation for stronger signals
    - Suitable for high-volatility regimes and breakout scenarios

    The logic: Low volatility (squeeze) → High volatility (breakout) → Trade the breakout direction
    """

    def __init__(self, lookback: int = 20, bb_std: float = 2.0, squeeze_threshold: float = 0.7,
                 atr_confirmation: bool = True, atr_period: int = 14, atr_multiplier: float = 1.5):
        """
        Initialize BreakoutStrategy.

        Args:
            lookback: Lookback period for calculations (default 20)
            bb_std: Bollinger Bands standard deviation multiplier (default 2.0)
            squeeze_threshold: Threshold for squeeze detection (default 0.7 = 30% squeeze)
            atr_confirmation: Use ATR for signal confirmation (default True)
            atr_period: ATR calculation period (default 14)
            atr_multiplier: ATR multiplier for confirmation (default 1.5)
        """
        self.lookback = lookback
        self.bb_std = bb_std
        self.squeeze_threshold = squeeze_threshold
        self.atr_confirmation = atr_confirmation
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier

        # Performance tracking
        self.signals_generated = 0
        self.bullish_breakouts = 0
        self.bearish_breakouts = 0
        self.squeeze_detected = 0

        logger.info(f"BreakoutStrategy initialized: lookback={lookback}, bb_std={bb_std}, "
                   f"squeeze_threshold={squeeze_threshold}, atr_confirmation={atr_confirmation}")

    def generate_signal(self, df: pd.DataFrame, i: int, params: Dict[str, Any] = None) -> int:
        """
        Generate breakout signal using Bollinger Band squeeze and expansion.

        Args:
            df: Complete DataFrame with historical data (must include 'close', 'high', 'low' columns)
            i: Current bar index
            params: Optional strategy parameters (overrides instance defaults)

        Returns:
            1 (LONG), -1 (SHORT), or 0 (no position)
        """
        if params is None:
            params = {}

        # Extract parameters
        lookback = int(params.get('lookback', self.lookback))
        bb_std = float(params.get('bb_std', self.bb_std))
        squeeze_threshold = float(params.get('squeeze_threshold', self.squeeze_threshold))
        atr_confirmation = params.get('atr_confirmation', self.atr_confirmation)
        atr_period = int(params.get('atr_period', self.atr_period))
        atr_multiplier = float(params.get('atr_multiplier', self.atr_multiplier))

        # Minimum data requirement
        lookback_required = lookback * 2 + atr_period + 10
        if i < lookback_required:
            return 0

        try:
            # Calculate Bollinger Bands
            bb_lookback_df = df.iloc[max(0, i - lookback):i + 1].copy()

            if len(bb_lookback_df) < lookback:
                return 0

            # Calculate SMA and standard deviation
            sma = bb_lookback_df['close'].mean()
            std = bb_lookback_df['close'].std()

            # Calculate Bollinger Bands
            bb_upper = sma + (std * bb_std)
            bb_lower = sma - (std * bb_std)
            current_price = df['close'].iloc[i]

            # Calculate bandwidth (volatility indicator)
            bandwidth = (bb_upper - bb_lower) / sma if sma > 0 else 0

            # Check for NaN values
            if pd.isna(sma) or pd.isna(std) or pd.isna(bb_upper) or pd.isna(bb_lower) or pd.isna(bandwidth):
                return 0

            # Calculate historical bandwidths for squeeze detection
            historical_start = max(0, i - lookback * 2)
            historical_data = df.iloc[historical_start:i].copy()

            historical_bandwidths = []
            for j in range(lookback, len(historical_data)):
                temp_data = historical_data.iloc[j - lookback:j + 1]
                temp_sma = temp_data['close'].mean()
                temp_std = temp_data['close'].std()
                temp_bb_upper = temp_sma + (temp_std * bb_std)
                temp_bb_lower = temp_sma - (temp_std * bb_std)
                temp_bandwidth = (temp_bb_upper - temp_bb_lower) / temp_sma if temp_sma > 0 else 0
                historical_bandwidths.append(temp_bandwidth)

            avg_bandwidth = np.mean(historical_bandwidths) if historical_bandwidths else bandwidth

            # Detect squeeze (low volatility condition)
            is_squeeze = bandwidth < avg_bandwidth * squeeze_threshold

            if is_squeeze:
                self.squeeze_detected += 1

            # Generate breakout signals
            signal = 0

            if is_squeeze:
                # Squeeze detected, look for breakout
                if current_price > bb_upper:
                    # Potential bullish breakout
                    signal = 1

                    # ATR confirmation if enabled
                    if atr_confirmation and 'atr' in df.columns:
                        current_atr = df['atr'].iloc[i] if not pd.isna(df['atr'].iloc[i]) else 0
                        atr_threshold = current_atr * atr_multiplier

                        # Confirm breakout with ATR expansion
                        price_move = current_price - sma
                        if price_move < atr_threshold:
                            signal = 0  # Not enough expansion

                    if signal == 1:
                        self.bullish_breakouts += 1
                        logger.debug(f"Bullish breakout at bar {i}: price ({current_price:.2f}) > BB upper ({bb_upper:.2f})")

                elif current_price < bb_lower:
                    # Potential bearish breakout
                    signal = -1

                    # ATR confirmation if enabled
                    if atr_confirmation and 'atr' in df.columns:
                        current_atr = df['atr'].iloc[i] if not pd.isna(df['atr'].iloc[i]) else 0
                        atr_threshold = current_atr * atr_multiplier

                        # Confirm breakout with ATR expansion
                        price_move = sma - current_price
                        if price_move < atr_threshold:
                            signal = 0  # Not enough expansion

                    if signal == -1:
                        self.bearish_breakouts += 1
                        logger.debug(f"Bearish breakout at bar {i}: price ({current_price:.2f}) < BB lower ({bb_lower:.2f})")

            # Track signal generation
            if signal != 0:
                self.signals_generated += 1

            return signal

        except Exception as e:
            logger.warning(f"Error generating breakout signal at bar {i}: {e}")
            return 0

    def get_strategy_summary(self) -> Dict[str, Any]:
        """Get summary of strategy performance."""
        return {
            'strategy_type': 'breakout',
            'lookback': self.lookback,
            'bb_std': self.bb_std,
            'squeeze_threshold': self.squeeze_threshold,
            'atr_confirmation': self.atr_confirmation,
            'atr_period': self.atr_period,
            'atr_multiplier': self.atr_multiplier,
            'signals_generated': self.signals_generated,
            'bullish_breakouts': self.bullish_breakouts,
            'bearish_breakouts': self.bearish_breakouts,
            'squeeze_detected': self.squeeze_detected
        }

    def reset_statistics(self):
        """Reset performance statistics."""
        self.signals_generated = 0
        self.bullish_breakouts = 0
        self.bearish_breakouts = 0
        self.squeeze_detected = 0


def create_breakout_strategy(params: Dict[str, Any] = None) -> BreakoutStrategy:
    """
    Factory function to create BreakoutStrategy with parameters.

    Args:
        params: Optional parameters dictionary
            - lookback: Lookback period for calculations (default 20)
            - bb_std: Bollinger Bands standard deviation multiplier (default 2.0)
            - squeeze_threshold: Threshold for squeeze detection (default 0.7)
            - atr_confirmation: Use ATR for signal confirmation (default True)
            - atr_period: ATR calculation period (default 14)
            - atr_multiplier: ATR multiplier for confirmation (default 1.5)

    Returns:
        Configured BreakoutStrategy instance
    """
    if params is None:
        params = {}

    return BreakoutStrategy(
        lookback=params.get('lookback', 20),
        bb_std=params.get('bb_std', 2.0),
        squeeze_threshold=params.get('squeeze_threshold', 0.7),
        atr_confirmation=params.get('atr_confirmation', True),
        atr_period=params.get('atr_period', 14),
        atr_multiplier=params.get('atr_multiplier', 1.5)
    )
