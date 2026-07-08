#!/usr/bin/env python3
"""
Mean Reversion Strategy Implementation

Bollinger Bands + RSI mean reversion strategy for ranging markets.
Following the AdaptiveRegimeSwitchingStrategy pattern.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class MeanReversionStrategy:
    """
    Bollinger Bands + RSI mean reversion strategy for ranging markets.

    This strategy generates signals based on price extremes reverting to the mean:
    - Oversold conditions (price below lower BB or RSI < 30) → Buy signal (1)
    - Overbought conditions (price above upper BB or RSI > 70) → Sell signal (-1)
    - Uses OR logic for better signal coverage

    Suitable for sideways/ranging markets where price oscillates around mean.
    """

    def __init__(self, bb_period: int = 20, bb_std: float = 2.0,
                 rsi_period: int = 14, rsi_oversold: int = 30, rsi_overbought: int = 70,
                 signal_logic: str = 'OR'):
        """
        Initialize MeanReversionStrategy.

        Args:
            bb_period: Bollinger Bands period (default 20)
            bb_std: Bollinger Bands standard deviation multiplier (default 2.0)
            rsi_period: RSI calculation period (default 14)
            rsi_oversold: RSI oversold threshold (default 30)
            rsi_overbought: RSI overbought threshold (default 70)
            signal_logic: 'OR' or 'AND' logic for combining BB and RSI signals (default 'OR')
        """
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.signal_logic = signal_logic.upper()

        # Performance tracking
        self.signals_generated = 0
        self.oversold_signals = 0
        self.overbought_signals = 0
        self.bb_signals = 0
        self.rsi_signals = 0

        logger.info(f"MeanReversionStrategy initialized: bb_period={bb_period}, bb_std={bb_std}, "
                   f"rsi_period={rsi_period}, logic={signal_logic}")

    def generate_signal(self, df: pd.DataFrame, i: int, params: Dict[str, Any] = None) -> int:
        """
        Generate mean reversion signal using Bollinger Bands + RSI.

        Args:
            df: Complete DataFrame with historical data (must include 'close' column)
            i: Current bar index
            params: Optional strategy parameters (overrides instance defaults)

        Returns:
            1 (LONG), -1 (SHORT), or 0 (no position)
        """
        if params is None:
            params = {}

        # Extract parameters
        bb_period = int(params.get('bb_period', self.bb_period))
        bb_std = float(params.get('bb_std', self.bb_std))
        rsi_period = int(params.get('rsi_period', self.rsi_period))
        rsi_oversold = int(params.get('rsi_oversold', self.rsi_oversold))
        rsi_overbought = int(params.get('rsi_overbought', self.rsi_overbought))
        signal_logic = params.get('signal_logic', self.signal_logic)

        # Minimum data requirement
        lookback_required = max(bb_period, rsi_period) + 5
        if i < lookback_required:
            return 0

        try:
            # Calculate Bollinger Bands
            bb_lookback_df = df.iloc[max(0, i - bb_period):i + 1].copy()

            if len(bb_lookback_df) < bb_period:
                return 0

            # Calculate SMA and standard deviation
            sma = bb_lookback_df['close'].mean()
            std = bb_lookback_df['close'].std()

            # Calculate Bollinger Bands
            bb_upper = sma + (std * bb_std)
            bb_lower = sma - (std * bb_std)
            current_price = df['close'].iloc[i]

            # Check for NaN values
            if pd.isna(sma) or pd.isna(std) or pd.isna(bb_upper) or pd.isna(bb_lower) or pd.isna(current_price):
                return 0

            # Generate Bollinger Band signals
            bb_signal = 0
            if current_price < bb_lower:
                bb_signal = 1  # Oversold - buy signal
                self.bb_signals += 1
            elif current_price > bb_upper:
                bb_signal = -1  # Overbought - sell signal
                self.bb_signals += 1

            # Calculate RSI
            rsi_lookback_df = df.iloc[max(0, i - rsi_period):i + 1].copy()

            if len(rsi_lookback_df) < rsi_period:
                rsi = 50  # Default neutral
            else:
                # Calculate RSI
                delta = rsi_lookback_df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(min(rsi_period, len(rsi_lookback_df)), min_periods=1).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(min(rsi_period, len(rsi_lookback_df)), min_periods=1).mean()

                if loss.iloc[-1] == 0 or pd.isna(loss.iloc[-1]) or np.isnan(loss.iloc[-1]):
                    rsi = 50
                else:
                    rs = gain.iloc[-1] / loss.iloc[-1]
                    rsi = 100 - (100 / (1 + rs))

                rsi = rsi if not pd.isna(rsi) else 50

            # Generate RSI signals
            rsi_signal = 0
            if rsi < rsi_oversold:
                rsi_signal = 1  # Oversold - buy signal
                self.rsi_signals += 1
            elif rsi > rsi_overbought:
                rsi_signal = -1  # Overbought - sell signal
                self.rsi_signals += 1

            # Combine signals based on logic
            signal = 0

            if signal_logic == 'AND':
                # Both indicators must agree
                if bb_signal == 1 and rsi_signal == 1:
                    signal = 1  # Buy signal (both oversold)
                elif bb_signal == -1 and rsi_signal == -1:
                    signal = -1  # Sell signal (both overbought)
                else:
                    signal = 0  # No agreement, no signal

            else:  # OR logic (default)
                # Either indicator can generate signal
                if bb_signal == 1 or rsi_signal == 1:
                    signal = 1  # Buy signal (either oversold)
                elif bb_signal == -1 or rsi_signal == -1:
                    signal = -1  # Sell signal (either overbought)
                else:
                    signal = 0  # Both neutral

            # Track signal generation
            if signal != 0:
                self.signals_generated += 1
                if signal == 1:
                    self.oversold_signals += 1
                else:
                    self.overbought_signals += 1

            return signal

        except Exception as e:
            logger.warning(f"Error generating mean reversion signal at bar {i}: {e}")
            return 0

    def get_strategy_summary(self) -> Dict[str, Any]:
        """Get summary of strategy performance."""
        return {
            'strategy_type': 'mean_reversion',
            'bb_period': self.bb_period,
            'bb_std': self.bb_std,
            'rsi_period': self.rsi_period,
            'rsi_oversold': self.rsi_oversold,
            'rsi_overbought': self.rsi_overbought,
            'signal_logic': self.signal_logic,
            'signals_generated': self.signals_generated,
            'oversold_signals': self.oversold_signals,
            'overbought_signals': self.overbought_signals,
            'bb_signals': self.bb_signals,
            'rsi_signals': self.rsi_signals
        }

    def reset_statistics(self):
        """Reset performance statistics."""
        self.signals_generated = 0
        self.oversold_signals = 0
        self.overbought_signals = 0
        self.bb_signals = 0
        self.rsi_signals = 0


def create_mean_reversion_strategy(params: Dict[str, Any] = None) -> MeanReversionStrategy:
    """
    Factory function to create MeanReversionStrategy with parameters.

    Args:
        params: Optional parameters dictionary
            - bb_period: Bollinger Bands period (default 20)
            - bb_std: Bollinger Bands standard deviation multiplier (default 2.0)
            - rsi_period: RSI calculation period (default 14)
            - rsi_oversold: RSI oversold threshold (default 30)
            - rsi_overbought: RSI overbought threshold (default 70)
            - signal_logic: 'OR' or 'AND' logic (default 'OR')

    Returns:
        Configured MeanReversionStrategy instance
    """
    if params is None:
        params = {}

    return MeanReversionStrategy(
        bb_period=params.get('bb_period', 20),
        bb_std=params.get('bb_std', 2.0),
        rsi_period=params.get('rsi_period', 14),
        rsi_oversold=params.get('rsi_oversold', 30),
        rsi_overbought=params.get('rsi_overbought', 70),
        signal_logic=params.get('signal_logic', 'OR')
    )
