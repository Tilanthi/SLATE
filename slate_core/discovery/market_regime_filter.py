#!/usr/bin/env python3
"""
Market Regime Filter for Discovery

Filters market data by volatility regimes to focus discovery on periods
where strategies are more likely to succeed.

Key insight: Mean reversion and adaptive strategies perform better in
high-volatility regimes where price extremes revert to mean more frequently.
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)

# Fix #2: a regime filter must not starve a small dataset. If the optimal regime
# leaves fewer than this many bars, the closed loop widens to all regimes - on a
# scarce daily dataset the regime focus isn't worth losing the bars (it was
# cutting 175 -> 47 bars, leaving too few to generate any trades).
MIN_BARS_FOR_DISCOVERY = 120


class MarketRegimeFilter:
    """
    Filter market data by volatility regimes for targeted discovery.

    Focuses discovery on high-volatility periods where:
    - Mean reversion strategies work better (more extreme reversions)
    - Adaptive strategies have more opportunities (larger moves)
    - Signal-to-noise ratio is more favorable
    """

    def __init__(self):
        self.volatility_percentiles = {
            'low': 0.3,      # Bottom 30%
            'medium': 0.7,   # Top 70% (middle 40%)
            'high': 1.0      # Top 30%
        }

    def analyze_volatility_regimes(self, df: pd.DataFrame) -> Dict[str, any]:
        """
        Analyze volatility regimes in the dataset.

        Returns comprehensive volatility statistics.
        """
        # Calculate volatility
        df = df.copy()
        df['volatility'] = df['close'].pct_change().rolling(20).std()
        df['returns'] = df['close'].pct_change()

        # Get volatility statistics
        vol_stats = df['volatility'].describe()

        # Calculate percentiles
        p30 = df['volatility'].quantile(0.3)
        p70 = df['volatility'].quantile(0.7)

        # Count days in each regime
        low_vol_days = len(df[df['volatility'] < p30])
        medium_vol_days = len(df[(df['volatility'] >= p30) & (df['volatility'] < p70)])
        high_vol_days = len(df[df['volatility'] >= p70])

        total_days = len(df)

        analysis = {
            'volatility_mean': vol_stats['mean'],
            'volatility_median': vol_stats['50%'],
            'volatility_std': vol_stats['std'],
            'volatility_min': vol_stats['min'],
            'volatility_max': vol_stats['max'],
            'p30_threshold': p30,
            'p70_threshold': p70,
            'low_vol_days': low_vol_days,
            'medium_vol_days': medium_vol_days,
            'high_vol_days': high_vol_days,
            'total_days': total_days,
            'low_vol_pct': low_vol_days / total_days,
            'medium_vol_pct': medium_vol_days / total_days,
            'high_vol_pct': high_vol_days / total_days
        }

        logger.info("Volatility Regime Analysis:")
        logger.info(f"  Low Volatility (< {p30:.6f}): {low_vol_days} days ({analysis['low_vol_pct']:.1%})")
        logger.info(f"  Medium Volatility ({p30:.6f} - {p70:.6f}): {medium_vol_days} days ({analysis['medium_vol_pct']:.1%})")
        logger.info(f"  High Volatility (>= {p70:.6f}): {high_vol_days} days ({analysis['high_vol_pct']:.1%})")

        return analysis

    def filter_by_regime(self, df: pd.DataFrame, regime: str = 'high') -> pd.DataFrame:
        """
        Filter dataframe to only include specified volatility regime.

        Args:
            df: Original dataframe
            regime: 'high', 'medium', 'low', or 'all'

        Returns:
            Filtered dataframe
        """
        df = df.copy()

        # Calculate volatility if not already present
        if 'volatility' not in df.columns:
            df['volatility'] = df['close'].pct_change().rolling(20).std()

        # Get thresholds
        p30 = df['volatility'].quantile(0.3)
        p70 = df['volatility'].quantile(0.7)

        original_len = len(df)

        # Filter by regime
        if regime == 'high':
            filtered_df = df[df['volatility'] >= p70]
            logger.info(f"🔥 Filtering to HIGH VOLATILITY regime (>= {p70:.6f}): {len(filtered_df)} days")
        elif regime == 'medium':
            filtered_df = df[(df['volatility'] >= p30) & (df['volatility'] < p70)]
            logger.info(f"📊 Filtering to MEDIUM VOLATILITY regime ({p30:.6f} - {p70:.6f}): {len(filtered_df)} days")
        elif regime == 'low':
            filtered_df = df[df['volatility'] < p30]
            logger.info(f"📉 Filtering to LOW VOLATILITY regime (< {p30:.6f}): {len(filtered_df)} days")
        else:  # 'all'
            filtered_df = df
            logger.info(f"🌐 Using ALL REGIMES: {len(filtered_df)} days")

        reduction_pct = (1 - len(filtered_df) / original_len) * 100
        logger.info(f"  Data reduction: {reduction_pct:.1f}% (from {original_len} to {len(filtered_df)} days)")

        return filtered_df

    def get_optimal_regime_for_strategy(self, strategy_type: str) -> str:
        """
        Recommend optimal volatility regime for given strategy type.

        Args:
            strategy_type: 'mean_reversion', 'momentum', 'arbitrage', etc.

        Returns:
            Recommended regime: 'high', 'medium', 'low', or 'all'
        """
        # Mean reversion works best in high volatility (more reversions)
        if strategy_type in ['mean_reversion', 'adaptive_regime_switching']:
            return 'high'
        # Momentum works better in medium volatility (trends sustain)
        elif strategy_type == 'momentum':
            return 'medium'
        # Arbitrage needs all regimes to find inefficiencies
        elif strategy_type == 'arbitrage':
            return 'all'
        # Default to high volatility
        else:
            return 'high'

    def filter_for_discovery(self, df: pd.DataFrame, strategy_type: str = 'adaptive_regime_switching') -> pd.DataFrame:
        """
        Filter data optimally for given strategy type.

        This is the main entry point for discovery system integration.
        """
        optimal_regime = self.get_optimal_regime_for_strategy(strategy_type)
        filtered_df = self.filter_by_regime(df, optimal_regime)

        # Fix #2: if the optimal regime leaves too few bars to backtest
        # meaningfully, widen to all regimes. The regime focus is only worth
        # keeping on datasets large enough to trade after the cut.
        if len(filtered_df) < MIN_BARS_FOR_DISCOVERY:
            logger.info(
                f"⚠️ {strategy_type}: regime '{optimal_regime}' left only "
                f"{len(filtered_df)} bars (< {MIN_BARS_FOR_DISCOVERY}); using all regimes"
            )
            filtered_df = self.filter_by_regime(df, 'all')

        logger.info(f"✅ Optimized data for {strategy_type}: {len(filtered_df)} days in {optimal_regime.upper()} volatility regime")

        return filtered_df


# Singleton instance
_regime_filter: MarketRegimeFilter = None


def get_market_regime_filter() -> MarketRegimeFilter:
    """Get the global market regime filter instance."""
    global _regime_filter
    if _regime_filter is None:
        _regime_filter = MarketRegimeFilter()
    return _regime_filter
