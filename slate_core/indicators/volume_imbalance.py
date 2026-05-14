"""
Volume Imbalance Indicator
Unified implementation to eliminate 7+ duplicate functions
"""

import pandas as pd
import numpy as np
from typing import Union

from ..config.constants import VI_PERIOD_DEFAULT, VI_THRESHOLD_DEFAULT


class VolumeImbalance:
    """
    Volume Imbalance (VI) Indicator Calculator.

    VI = (Volume of up bars - Volume of down bars) / Total Volume

    Used to identify buying/selling pressure imbalances.
    """

    def __init__(self, period: int = VI_PERIOD_DEFAULT):
        """
        Initialize VI calculator.

        Parameters:
        - period: Lookback period for VI calculation (default: 12)
        """
        self.period = period

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate Volume Imbalance indicator.

        Parameters:
        - df: DataFrame with OHLCV data (must have 'open', 'close', 'volume')

        Returns:
        - Series with VI values (-1 to +1)
        """
        df = df.copy()

        # Identify up and down bars
        df['is_up'] = df['close'] > df['open']
        df['is_down'] = df['close'] < df['open']

        # Calculate volume for up and down bars
        df['up_volume'] = df['volume'] * df['is_up']
        df['down_volume'] = df['volume'] * df['is_down']

        # Calculate rolling sums
        up_vol_sum = df['up_volume'].rolling(window=self.period).sum()
        down_vol_sum = df['down_volume'].rolling(window=self.period).sum()
        total_vol = df['volume'].rolling(window=self.period).sum()

        # Calculate Volume Imbalance
        vi = (up_vol_sum - down_vol_sum) / total_vol

        return vi

    def calculate_fast(self, df: pd.DataFrame) -> pd.Series:
        """
        Fast VI calculation using numpy (optimized for large datasets).
        """
        close = df['close'].values
        open_price = df['open'].values
        volume = df['volume'].values

        is_up = close > open_price
        is_down = close < open_price

        up_volume = volume * is_up
        down_volume = volume * is_down

        # Use rolling window with numpy
        up_vol_sum = pd.Series(up_volume).rolling(window=self.period).sum()
        down_vol_sum = pd.Series(down_volume).rolling(window=self.period).sum()
        total_vol = pd.Series(volume).rolling(window=self.period).sum()

        vi = (up_vol_sum - down_vol_sum) / total_vol

        return vi

    def add_to_dataframe(self, df: pd.DataFrame, column_name: str = 'vi') -> pd.DataFrame:
        """
        Add VI column to DataFrame in-place.

        Parameters:
        - df: DataFrame with OHLCV data
        - column_name: Name for VI column (default: 'vi')

        Returns:
        - DataFrame with VI column added
        """
        df = df.copy()
        df[column_name] = self.calculate(df)
        return df

    def get_signals(self, df: pd.DataFrame,
                    threshold: float = VI_THRESHOLD_DEFAULT) -> pd.Series:
        """
        Generate trading signals based on VI thresholds.

        Parameters:
        - df: DataFrame with OHLCV data
        - threshold: VI threshold for signals (default: 0.30)

        Returns:
        - Series with signal values (1=long, -1=short, 0=neutral)
        """
        vi = self.calculate(df)

        signals = pd.Series(0, index=df.index)
        signals[vi > threshold] = 1  # Long signal
        signals[vi < -threshold] = -1  # Short signal

        return signals


# Convenience functions for backward compatibility
def calculate_vi(df: pd.DataFrame, period: int = VI_PERIOD_DEFAULT) -> pd.Series:
    """
    Calculate Volume Imbalance (backward compatible).

    Parameters:
    - df: DataFrame with OHLCV data
    - period: VI calculation period

    Returns:
    - Series with VI values
    """
    calculator = VolumeImbalance(period=period)
    return calculator.calculate(df)


def calculate_volume_imbalance(df: pd.DataFrame, period: int = VI_PERIOD_DEFAULT) -> pd.Series:
    """Calculate Volume Imbalance (alternative name, backward compatible)."""
    return calculate_vi(df, period)


def calculate_vi_fast(df: pd.DataFrame, period: int = VI_PERIOD_DEFAULT) -> pd.Series:
    """Fast VI calculation using numpy (backward compatible)."""
    calculator = VolumeImbalance(period=period)
    return calculator.calculate_fast(df)


def get_vi_signals(df: pd.DataFrame,
                   period: int = VI_PERIOD_DEFAULT,
                   threshold: float = VI_THRESHOLD_DEFAULT) -> pd.Series:
    """
    Get trading signals from VI indicator.

    Parameters:
    - df: DataFrame with OHLCV data
    - period: VI calculation period
    - threshold: Signal threshold

    Returns:
    - Series with signals (1=long, -1=short, 0=neutral)
    """
    calculator = VolumeImbalance(period=period)
    return calculator.get_signals(df, threshold)
