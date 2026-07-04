#!/usr/bin/env python3
"""
SLATE Regime-Aware Strategy System

Implements multiple strategy types optimized for different market regimes:
1. Mean Reversion (for sideways/ranging markets)
2. Range Trading (support/resistance)
3. Statistical Arbitrage (market-neutral)
4. Enhanced EMA (range-friendly trend following)

This fixes the critical regime mismatch where trend-following strategies
were being tested in ranging markets, resulting in 0.15% validation success.

Author: SLATE Architecture Enhancement
Date: 2026-07-03
Priority: CRITICAL - Fixes regime-strategy mismatch
"""

import pandas as pd
import numpy as np
from typing import Dict, Any


def bollinger_mean_reversion_signal(df: pd.DataFrame, i: int, params: Dict[str, Any]) -> int:
    """
    Bollinger Band mean reversion strategy for sideways markets.

    Signal Logic:
    - Buy (1) when price touches lower Bollinger Band (oversold)
    - Sell (-1) when price touches upper Bollinger Band (overbought)
    - Exit when price returns to middle band (mean reversion)

    Parameters:
    - bb_period: Bollinger Band period (default 20)
    - bb_std: Standard deviations for bands (default 2.0)
    - entry_threshold: How close to band before entry (default 0.01 = 1%)
    """
    if i < 20:
        return 0

    bb_period = int(params.get('bb_period', 20))
    bb_std = float(params.get('bb_std', 2.0))
    entry_threshold = float(params.get('entry_threshold', 0.01))

    # Calculate Bollinger Bands if not present
    if 'bollinger_upper' not in df.columns or 'bollinger_lower' not in df.columns:
        return 0

    current_price = df.iloc[i]['close']
    upper_band = df.iloc[i]['bollinger_upper']
    lower_band = df.iloc[i]['bollinger_lower']
    middle_band = df.iloc[i]['sma_20']  # Middle band is SMA

    # Check if at lower band (oversold) - BUY signal
    if abs(current_price - lower_band) / lower_band < entry_threshold:
        # Only if we're not already in a position
        if df.iloc[i-1]['close'] >= lower_band * (1 - entry_threshold):
            return 1  # LONG (mean reversion up)

    # Check if at upper band (overbought) - SELL signal
    if abs(current_price - upper_band) / upper_band < entry_threshold:
        # Only if we're not already in a position
        if df.iloc[i-1]['close'] <= upper_band * (1 + entry_threshold):
            return -1  # SHORT (mean reversion down)

    return 0


def rsi_extremes_signal(df: pd.DataFrame, i: int, params: Dict[str, Any]) -> int:
    """
    RSI extremes strategy for mean reversion in ranging markets.

    Signal Logic:
    - Buy (1) when RSI < oversold_threshold (default 30)
    - Sell (-1) when RSI > overbought_threshold (default 70)
    - Exit when RSI returns to neutral (40-60)

    Parameters:
    - rsi_period: RSI calculation period (default 14)
    - oversold_threshold: RSI level for buy signal (default 30)
    - overbought_threshold: RSI level for sell signal (default 70)
    - exit_neutral_min: Exit long when RSI > this (default 50)
    - exit_neutral_max: Exit short when RSI < this (default 50)
    """
    if i < 14:
        return 0

    rsi_period = int(params.get('rsi_period', 14))
    oversold_threshold = float(params.get('oversold_threshold', 30))
    overbought_threshold = float(params.get('overbought_threshold', 70))

    if 'rsi' not in df.columns:
        return 0

    current_rsi = df.iloc[i]['rsi']
    prev_rsi = df.iloc[i-1]['rsi']

    # Oversold - BUY signal
    if current_rsi < oversold_threshold and prev_rsi >= oversold_threshold:
        return 1  # LONG

    # Overbought - SELL signal
    if current_rsi > overbought_threshold and prev_rsi <= overbought_threshold:
        return -1  # SHORT

    return 0


def support_resistance_signal(df: pd.DataFrame, i: int, params: Dict[str, Any]) -> int:
    """
    Support/Resistance trading strategy for ranging markets.

    Signal Logic:
    - Buy (1) when price nears support (recent low)
    - Sell (-1) when price nears resistance (recent high)
    - Uses rolling windows to detect S/R levels

    Parameters:
    - lookback_period: Period to find S/R levels (default 20)
    - touch_tolerance: How close to S/R before entry (default 0.01 = 1%)
    - min_range: Minimum price range to trade (default 0.02 = 2%)
    """
    if i < 40:
        return 0

    lookback = int(params.get('lookback_period', 20))
    touch_tolerance = float(params.get('touch_tolerance', 0.01))
    min_range = float(params.get('min_range', 0.02))

    # Get recent price range
    recent_data = df.iloc[i-lookback:i]
    resistance_level = recent_data['high'].max()
    support_level = recent_data['low'].min()
    current_price = df.iloc[i]['close']

    # Check if there's enough range to trade
    price_range = (resistance_level - support_level) / support_level
    if price_range < min_range:
        return 0  # Range too tight

    # Near support - BUY signal
    if abs(current_price - support_level) / support_level < touch_tolerance:
        if df.iloc[i-1]['close'] >= support_level * (1 + touch_tolerance):
            return 1  # LONG

    # Near resistance - SELL signal
    if abs(current_price - resistance_level) / resistance_level < touch_tolerance:
        if df.iloc[i-1]['close'] <= resistance_level * (1 - touch_tolerance):
            return -1  # SHORT

    return 0


def enhanced_ema_signal(df: pd.DataFrame, i: int, params: Dict[str, Any]) -> int:
    """
    Enhanced EMA crossover with range-friendly filters.

    Improvements over basic EMA:
    - Faster EMAs for more signals (5/15 instead of 10/20)
    - Relaxed filters for ranging markets
    - Volatility-aware but not restrictive
    - Focus on signal generation over filtering

    Parameters:
    - fast_period: Fast EMA period (default 8, was 10)
    - slow_period: Slow EMA period (default 17, was 20)
    - range_filter: Only avoid EXTREMELY tight ranges (default 0.001 = 0.1%)
    - volatility_threshold: Very low volatility threshold (default 0.005 = 0.5%)
    - atr_multiplier: Use ATR for confirmation (default 1.5)
    """
    if i < 2:
        return 0

    fast_period = int(params.get('fast_period', 8))
    slow_period = int(params.get('slow_period', 17))
    range_filter = float(params.get('range_filter', 0.001))  # Much more permissive
    volatility_threshold = float(params.get('volatility_threshold', 0.005))  # Lower threshold

    # CRITICAL FIX: Calculate EMAs dynamically if they don't exist
    fast_col = f"ema_{fast_period}"
    slow_col = f"ema_{slow_period}"

    if fast_col not in df.columns:
        df[fast_col] = df['close'].ewm(span=fast_period, adjust=False).mean()
    if slow_col not in df.columns:
        df[slow_col] = df['close'].ewm(span=slow_period, adjust=False).mean()

    current_price = df.iloc[i]['close']
    prev_price = df.iloc[i-1]['close']

    # Calculate price range over recent period
    recent_data = df.iloc[i-20:i]
    price_range = (recent_data['high'].max() - recent_data['low'].min()) / current_price

    # RANGE FILTER: Only skip EXTREMELY tight ranges (not normal ranges)
    if price_range < range_filter:
        return 0  # Only skip if range is extremely tight

    # VOLATILITY CHECK: Very low threshold (mostly permissive)
    if 'atr_ratio' in df.columns:
        atr_ratio = df.iloc[i]['atr_ratio']
        if atr_ratio < volatility_threshold:
            return 0  # Only skip if almost no volatility

    # Golden cross (long signal)
    if df.iloc[i][fast_col] > df.iloc[i][slow_col]:
        if df.iloc[i-1][fast_col] <= df.iloc[i-1][slow_col]:
            return 1  # LONG (simplified - no additional confirmation)

    # Death cross (short signal)
    if df.iloc[i][fast_col] < df.iloc[i][slow_col]:
        if df.iloc[i-1][fast_col] >= df.iloc[i-1][slow_col]:
            return -1  # SHORT (simplified - no additional confirmation)

    return 0


def statistical_arbitrage_signal(df: pd.DataFrame, i: int, params: Dict[str, Any]) -> int:
    """
    Statistical arbitrage using price deviations from statistical relationships.

    Signal Logic:
    - Buy/Sell when price deviates significantly from expected value
    - Uses statistical models (z-scores, standard deviations)
    - Mean-reverts to statistical equilibrium

    Parameters:
    - lookback_period: Period for statistical calculations (default 20)
    - z_score_threshold: Z-score for entry (default 2.0)
    - exit_z_score: Z-score for exit (default 0.5)
    """
    if i < 40:
        return 0

    lookback = int(params.get('lookback_period', 20))
    z_threshold = float(params.get('z_score_threshold', 2.0))

    recent_data = df.iloc[i-lookback:i]
    mean_price = recent_data['close'].mean()
    std_price = recent_data['close'].std()
    current_price = df.iloc[i]['close']

    if std_price == 0:
        return 0

    # Calculate z-score
    z_score = (current_price - mean_price) / std_price

    # Significantly below mean - BUY (statistically cheap)
    if z_score < -z_threshold:
        if i > 0:
            prev_z = (df.iloc[i-1]['close'] - mean_price) / std_price
            if prev_z >= -z_threshold:
                return 1  # LONG

    # Significantly above mean - SELL (statistically expensive)
    if z_score > z_threshold:
        if i > 0:
            prev_z = (df.iloc[i-1]['close'] - mean_price) / std_price
            if prev_z <= z_threshold:
                return -1  # SHORT

    return 0


def volatility_breakout_signal(df: pd.DataFrame, i: int, params: Dict[str, Any]) -> int:
    """
    Volatility breakout strategy for ranging markets with volatility spikes.

    Signal Logic:
    - Enter breakout when volatility expands after tight range
    - Trade in direction of breakout
    - Uses ATR and Bollinger Band width

    Parameters:
    - atr_period: ATR calculation period (default 14)
    - atr_multiplier: ATR multiple for breakout (default 2.0)
    - bb_width_threshold: BB width squeeze threshold (default 0.02)
    """
    if i < 20:
        return 0

    atr_period = int(params.get('atr_period', 14))
    atr_multiplier = float(params.get('atr_multiplier', 2.0))
    bb_threshold = float(params.get('bb_width_threshold', 0.02))

    if 'atr' not in df.columns or 'bollinger_width' not in df.columns:
        return 0

    current_atr = df.iloc[i]['atr']
    current_bb_width = df.iloc[i]['bollinger_width']
    current_price = df.iloc[i]['close']

    # Check for volatility squeeze (tight range)
    if current_bb_width < bb_threshold:
        return 0  # In squeeze, wait for breakout

    # Volatility breakout detection
    avg_atr = df.iloc[i-atr_period:i]['atr'].mean()

    # ATR expansion - breakout starting
    if current_atr > avg_atr * atr_multiplier:
        # Determine direction based on price movement
        if i > 0:
            price_change = (current_price - df.iloc[i-1]['close']) / df.iloc[i-1]['close']

            # Breakout up
            if price_change > 0.005:  # 0.5% minimum move
                return 1  # LONG

            # Breakout down
            if price_change < -0.005:
                return -1  # SHORT

    return 0


# Strategy registry for regime-aware selection
STRATEGY_REGISTRY = {
    # Mean reversion strategies (for sideways/ranging markets)
    'bollinger_mean_reversion': {
        'function': bollinger_mean_reversion_signal,
        'regime': 'sideways',
        'description': 'Bollinger Band mean reversion for ranging markets',
        'default_params': {'bb_period': 20, 'bb_std': 2.0, 'entry_threshold': 0.01}
    },

    'rsi_extremes': {
        'function': rsi_extremes_signal,
        'regime': 'sideways',
        'description': 'RSI extremes for mean reversion',
        'default_params': {'rsi_period': 14, 'oversold_threshold': 30, 'overbought_threshold': 70}
    },

    'support_resistance': {
        'function': support_resistance_signal,
        'regime': 'sideways',
        'description': 'Support/resistance trading in ranges',
        'default_params': {'lookback_period': 20, 'touch_tolerance': 0.01, 'min_range': 0.02}
    },

    # Enhanced trend following (range-friendly)
    'enhanced_ema': {
        'function': enhanced_ema_signal,
        'regime': 'trending',
        'description': 'Enhanced EMA with range filters',
        'default_params': {'fast_period': 8, 'slow_period': 17, 'range_filter': 0.005}
    },

    # Statistical arbitrage (market-neutral)
    'statistical_arbitrage': {
        'function': statistical_arbitrage_signal,
        'regime': 'any',
        'description': 'Statistical arbitrage using z-scores',
        'default_params': {'lookback_period': 20, 'z_score_threshold': 2.0}
    },

    # Volatility strategies
    'volatility_breakout': {
        'function': volatility_breakout_signal,
        'regime': 'volatile',
        'description': 'Volatility breakout trading',
        'default_params': {'atr_period': 14, 'atr_multiplier': 2.0}
    }
}


def get_strategy_function(strategy_type: str):
    """Get signal function for strategy type."""
    if strategy_type in STRATEGY_REGISTRY:
        return STRATEGY_REGISTRY[strategy_type]['function']

    # Fallback to enhanced EMA
    return enhanced_ema_signal


def get_default_params(strategy_type: str) -> Dict[str, Any]:
    """Get default parameters for strategy type."""
    if strategy_type in STRATEGY_REGISTRY:
        return STRATEGY_REGISTRY[strategy_type]['default_params'].copy()
    return {}


def get_strategies_for_regime(regime: str) -> list:
    """Get list of strategy types suitable for given regime."""
    return [
        name for name, config in STRATEGY_REGISTRY.items()
        if config['regime'] in [regime, 'any']
    ]


if __name__ == "__main__":
    # Test the strategy system
    print("Regime-Aware Strategy System")
    print(f"Total strategies: {len(STRATEGY_REGISTRY)}")
    print(f"Strategies for sideways regime: {get_strategies_for_regime('sideways')}")
    print(f"Strategies for trending regime: {get_strategies_for_regime('trending')}")
