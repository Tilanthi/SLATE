#!/usr/bin/env python3
"""
Adaptive Regime-Switching Strategy

A single intelligent strategy that automatically switches its trading approach
based on real-time market regime detection.

This replaces multiple fixed strategies with one adaptive strategy that:
- Detects current market regime in real-time
- Predicts regime transitions
- Automatically selects appropriate trading modules
- Adapts position sizing and risk management
- Handles regime transitions smoothly

Key Advantage: Works across all market conditions instead of failing in wrong regime.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

from slate_core.intelligence.market_regime_detector import MarketRegimeDetector
from slate_core.intelligence.regime_transition_detector import get_regime_transition_detector

logger = logging.getLogger(__name__)


class AdaptiveRegimeSwitchingStrategy:
    """
    Single adaptive strategy that automatically switches trading approaches
    based on real-time market regime detection.

    This is the "Chameleon Strategy" - changes colors based on environment.
    """

    def __init__(self):
        # Detection systems
        self.regime_detector = MarketRegimeDetector()
        self.transition_detector = get_regime_transition_detector()

        # Signal generation modules
        self.mean_reversion_module = MeanReversionModule()
        self.momentum_module = MomentumModule()
        self.arbitrage_module = ArbitrageModule()
        self.volatility_module = VolatilityModule()
        self.transition_module = TransitionModule()

        # Current state
        self.current_regime = None
        self.current_approach = None
        self.regime_history = []
        self.performance_by_regime = {}

        # Statistics
        self.regime_changes = 0
        self.signals_generated = 0
        self.trades_by_regime = {}

        logger.info("AdaptiveRegimeSwitchingStrategy initialized")

    def generate_signal(self, df: pd.DataFrame, i: int,
                       params: Dict[str, Any] = None) -> int:
        """
        Generate trading signal using adaptive regime-switching logic.

        This is the main entry point - called by backtest engine.

        Args:
            df: Complete DataFrame with historical data
            i: Current bar index
            params: Strategy parameters (optional)

        Returns: 1 (long), -1 (short), or 0 (no position)
        """
        if params is None:
            params = {}

        # Need minimum history for regime detection
        lookback_required = 100
        if i < lookback_required:
            return 0  # Not enough data yet

        # Get historical data for regime detection
        lookback_df = df.iloc[max(0, i - lookback_required):i + 1]

        # Detect regime with transition prediction
        try:
            regime_info = self.regime_detector.detect_regime_with_transition_prediction(lookback_df)
        except Exception as e:
            logger.warning(f"Regime detection failed at bar {i}: {e}")
            return 0

        # Get strategy recommendation
        strategy_rec = regime_info.get('recommended_strategy', {})

        # Log regime change
        if self.current_regime != regime_info['regime']:
            self._handle_regime_change(i, regime_info, strategy_rec)

        # Generate signal using appropriate module
        signal = self._generate_adaptive_signal(df, i, regime_info, strategy_rec)

        # Track signal generation
        self.signals_generated += 1

        # Track by regime
        regime = regime_info['regime']
        if regime not in self.trades_by_regime:
            self.trades_by_regime[regime] = 0

        if signal != 0:
            self.trades_by_regime[regime] += 1

        return signal

    def _handle_regime_change(self, bar: int, regime_info: Dict, strategy_rec: Dict):
        """Handle regime transition and logging"""

        old_regime = self.current_regime
        new_regime = regime_info['regime']

        logger.info(f"🔄 Regime Change at bar {bar}: {old_regime} → {new_regime}")
        logger.info(f"   Transition Probability: {regime_info['transition_info']['transition_probability']:.1%}")
        logger.info(f"   Next Regime: {regime_info['transition_info']['likely_next_regime']}")
        logger.info(f"   Strategy: {strategy_rec.get('primary_approach', 'unknown')}")
        logger.info(f"   Position Size: {strategy_rec.get('position_sizing_multiplier', 1.0):.1%}x")
        logger.info(f"   Reasoning: {strategy_rec.get('reasoning', '')}")

        # Update state
        self.current_regime = new_regime
        self.current_approach = strategy_rec.get('primary_approach', 'unknown')
        self.regime_changes += 1

        # Record in history
        self.regime_history.append({
            'bar': bar,
            'old_regime': old_regime,
            'new_regime': new_regime,
            'approach': strategy_rec.get('primary_approach', 'unknown'),
            'timestamp': datetime.now()
        })

    def _generate_adaptive_signal(self, df: pd.DataFrame, i: int,
                                regime_info: Dict, strategy_rec: Dict) -> int:
        """
        Generate signal using the appropriate strategy module.

        This is where the strategy switching happens - different modules
        are used based on current regime conditions.
        """
        approach = strategy_rec.get('primary_approach', 'mean_reversion')

        # Route to appropriate signal generation module
        if approach == 'mean_reversion':
            return self.mean_reversion_module.generate_signal(df, i, regime_info)

        elif approach == 'momentum':
            return self.momentum_module.generate_signal(df, i, regime_info)

        elif approach == 'short_momentum':
            return self.momentum_module.generate_short_signal(df, i, regime_info)

        elif approach == 'statistical_arbitrage':
            return self.arbitrage_module.generate_signal(df, i, regime_info)

        elif approach == 'volatility_breakout':
            return self.volatility_module.generate_signal(df, i, regime_info)

        elif approach == 'transition_handling':
            return self.transition_module.generate_signal(df, i, regime_info)

        elif approach == 'adaptive_mean_reversion':
            # Blend of mean reversion and other approaches
            return self._generate_blended_signal(df, i, regime_info)

        else:
            # Default to mean reversion
            return self.mean_reversion_module.generate_signal(df, i, regime_info)

    def _generate_blended_signal(self, df: pd.DataFrame, i: int,
                               regime_info: Dict) -> int:
        """
        Generate blended signal combining multiple approaches.

        Used during unstable or transition periods when no single approach
        is clearly best.
        """
        # Get signals from multiple modules
        mr_signal = self.mean_reversion_module.generate_signal(df, i, regime_info)
        arb_signal = self.arbitrage_module.generate_signal(df, i, regime_info)
        vol_signal = self.volatility_module.generate_signal(df, i, regime_info)

        # Weight signals based on regime characteristics
        regime = regime_info['regime']
        stability = regime_info.get('stability', 'unknown')

        if regime == 'sideways' and stability == 'unstable':
            # Blend mean reversion and arbitrage
            weights = {'mr': 0.6, 'arb': 0.3, 'vol': 0.1}
        elif regime == 'high_volatility':
            # Blend volatility and arbitrage
            weights = {'mr': 0.2, 'arb': 0.4, 'vol': 0.4}
        else:
            # Equal blend
            weights = {'mr': 0.33, 'arb': 0.33, 'vol': 0.34}

        # Calculate weighted signal
        weighted_signal = (
            mr_signal * weights['mr'] +
            arb_signal * weights['arb'] +
            vol_signal * weights['vol']
        )

        # Convert to integer signal
        if weighted_signal > 0.3:
            return 1
        elif weighted_signal < -0.3:
            return -1
        else:
            return 0

    def get_strategy_summary(self) -> Dict[str, Any]:
        """Get summary of adaptive strategy performance"""
        return {
            'regime_changes': self.regime_changes,
            'signals_generated': self.signals_generated,
            'trades_by_regime': self.trades_by_regime,
            'current_regime': self.current_regime,
            'current_approach': self.current_approach,
            'performance_by_regime': self.performance_by_regime
        }


# ============================================================================
# Signal Generation Modules
# ============================================================================

class MeanReversionModule:
    """Mean reversion signals for sideways/ranging markets"""

    def generate_signal(self, df: pd.DataFrame, i: int, regime_info: Dict) -> int:
        """Generate mean reversion signal with regime-adaptive parameters"""

        # Adaptive parameters based on regime stability
        stability = regime_info.get('stability', 'unknown')

        if stability == 'stable':
            bb_period = 20
            bb_std = 2.5
            rsi_oversold = 30
            rsi_overbought = 70
        else:  # unstable
            bb_period = 15
            bb_std = 2.0
            rsi_oversold = 25
            rsi_overbought = 75

        # Calculate Bollinger Bands
        lookback_df = df.iloc[max(0, i - bb_period):i + 1]
        if len(lookback_df) < bb_period:
            return 0

        sma = lookback_df['close'].mean()
        std = lookback_df['close'].std()

        bb_upper = sma + (std * bb_std)
        bb_lower = sma - (std * bb_std)
        current_price = df['close'].iloc[i]

        # Calculate RSI
        rsi_lookback = 14
        rsi_df = df.iloc[max(0, i - rsi_lookback):i + 1]
        if len(rsi_df) < rsi_lookback:
            rsi = 50  # Default neutral
        else:
            delta = rsi_df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(min(rsi_lookback, len(rsi_df))).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(min(rsi_lookback, len(rsi_df))).mean()

            if loss.iloc[-1] == 0 or np.isnan(loss.iloc[-1]):
                rsi = 50
            else:
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                rsi = rsi.iloc[-1]

        # Generate signals
        bb_signal = 0
        if current_price < bb_lower:
            bb_signal = 1  # Buy (oversold)
        elif current_price > bb_upper:
            bb_signal = -1  # Sell (overbought)

        rsi_signal = 0
        if rsi < rsi_oversold:
            rsi_signal = 1  # Buy
        elif rsi > rsi_overbought:
            rsi_signal = -1  # Sell

        # Combine signals (OR logic for better signal coverage)
        # Generate signal if EITHER BB or RSI agrees (was AND, now OR for 3-5x more signals)
        if bb_signal == 1 or rsi_signal == 1:
            return 1  # Buy signal (either BB oversold OR RSI oversold)
        elif bb_signal == -1 or rsi_signal == -1:
            return -1  # Sell signal (either BB overbought OR RSI overbought)
        else:
            return 0  # No signal (both indicators neutral)


class MomentumModule:
    """Momentum signals for trending markets"""

    def generate_signal(self, df: pd.DataFrame, i: int, regime_info: Dict) -> int:
        """Generate momentum signal for uptrends"""

        # Adaptive EMA periods based on regime
        stability = regime_info.get('stability', 'unknown')

        if stability == 'stable':
            fast_ema = 12
            slow_ema = 26
        else:
            fast_ema = 8   # Faster signals in unstable trends
            slow_ema = 17

        # Calculate EMAs
        lookback_df = df.iloc[max(0, i - slow_ema + 5):i + 1]

        if len(lookback_df) < slow_ema:
            return 0

        fast_ema_values = lookback_df['close'].ewm(span=fast_ema, adjust=False).mean()
        slow_ema_values = lookback_df['close'].ewm(span=slow_ema, adjust=False).mean()

        if len(fast_ema_values) < 2 or len(slow_ema_values) < 2:
            return 0

        fast_ema_current = fast_ema_values.iloc[-1]
        slow_ema_current = slow_ema_values.iloc[-1]
        fast_ema_prev = fast_ema_values.iloc[-2]
        slow_ema_prev = slow_ema_values.iloc[-2]

        # EMA crossover signal
        if fast_ema_current > slow_ema_current and fast_ema_prev <= slow_ema_prev:
            return 1  # Golden cross - buy signal
        elif fast_ema_current < slow_ema_current and fast_ema_prev >= slow_ema_prev:
            return -1  # Death cross - sell signal
        else:
            # Maintain existing position if trend still active
            if fast_ema_current > slow_ema_current:
                return 1  # Hold long
            else:
                return -1  # Hold short (if short selling allowed)

    def generate_short_signal(self, df: pd.DataFrame, i: int, regime_info: Dict) -> int:
        """Generate momentum signal for downtrends (short positions)"""

        # Use momentum logic but for short side
        signal = self.generate_signal(df, i, regime_info)

        # Invert signal for short positions
        if signal == 1:
            return -1  # Short instead of long
        elif signal == -1:
            return 1  # Cover instead of sell
        else:
            return 0


class ArbitrageModule:
    """Statistical arbitrage signals"""

    def generate_signal(self, df: pd.DataFrame, i: int, regime_info: Dict) -> int:
        """Generate statistical arbitrage signal"""

        # Z-score parameters
        lookback = 20

        # Adaptive thresholds based on volatility
        regime = regime_info.get('regime', 'sideways')

        if regime == 'high_volatility':
            z_entry = 2.5
            z_exit = 0.8
        else:
            z_entry = 2.0
            z_exit = 0.5

        # Calculate z-score
        lookback_df = df.iloc[max(0, i - lookback):i + 1]

        if len(lookback_df) < lookback:
            return 0

        mean = lookback_df['close'].mean()
        std = lookback_df['close'].std()

        current_price = df['close'].iloc[i]

        if std == 0:
            return 0

        z_score = (current_price - mean) / std

        # Generate signal
        if z_score < -z_entry:
            return 1  # Buy (oversold)
        elif z_score > z_entry:
            return -1  # Sell (overbought)
        else:
            return 0  # No signal


class VolatilityModule:
    """Volatility breakout signals"""

    def generate_signal(self, df: pd.DataFrame, i: int, regime_info: Dict) -> int:
        """Generate volatility breakout signal"""

        # Bollinger Band squeeze / breakout detection
        bb_period = 20

        lookback_df = df.iloc[max(0, i - bb_period):i + 1]

        if len(lookback_df) < bb_period:
            return 0

        sma = lookback_df['close'].mean()
        std = lookback_df['close'].std()

        bb_upper = sma + (std * 2)
        bb_lower = sma - (std * 2)

        # Calculate bandwidth (volatility indicator)
        bandwidth = (bb_upper - bb_lower) / sma if sma > 0 else 0

        # Check for squeeze (low volatility before breakout)
        # Use historical bandwidth for comparison
        historical_data = df.iloc[max(0, i - bb_period * 2):i]
        if len(historical_data) > 0:
            historical_bandwidths = []
            for j in range(bb_period, len(historical_data)):
                temp_data = historical_data.iloc[j - bb_period:j + 1]
                temp_sma = temp_data['close'].mean()
                temp_std = temp_data['close'].std()
                temp_bb_upper = temp_sma + (temp_std * 2)
                temp_bb_lower = temp_sma - (temp_std * 2)
                temp_bandwidth = (temp_bb_upper - temp_bb_lower) / temp_sma if temp_sma > 0 else 0
                historical_bandwidths.append(temp_bandwidth)

            avg_bandwidth = np.mean(historical_bandwidths) if historical_bandwidths else bandwidth
        else:
            avg_bandwidth = bandwidth

        current_price = df['close'].iloc[i]

        # Breakout signals
        if bandwidth < avg_bandwidth * 0.7:  # Squeeze condition
            if current_price > bb_upper:
                return 1  # Bullish breakout
            elif current_price < bb_lower:
                return -1  # Bearish breakout

        return 0  # No breakout


class TransitionModule:
    """Conservative signals during regime transitions"""

    def generate_signal(self, df: pd.DataFrame, i: int, regime_info: Dict) -> int:
        """Generate conservative signals during transitions"""

        # During transitions, use very conservative approach
        # Only take highest-confidence signals

        # Use very tight mean reversion only
        lookback_df = df.iloc[max(0, i - 10):i + 1]

        if len(lookback_df) < 5:
            return 0

        # Simple mean reversion with tight thresholds
        mean = lookback_df['close'].mean()
        std = lookback_df['close'].std()

        current_price = df['close'].iloc[i]

        # Only signal at 2 standard deviations (very high confidence)
        if std == 0:
            return 0

        z_score = (current_price - mean) / std

        if z_score < -2.0:
            return 1  # Very oversold
        elif z_score > 2.0:
            return -1  # Very overbought
        else:
            return 0  # No signal (prefer to stay in cash during transitions)


def get_adaptive_regime_switching_strategy() -> AdaptiveRegimeSwitchingStrategy:
    """Factory function to get adaptive regime-switching strategy"""
    return AdaptiveRegimeSwitchingStrategy()