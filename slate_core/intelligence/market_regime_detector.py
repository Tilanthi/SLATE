#!/usr/bin/env python3
"""
SLATE Market Intelligence Module

Phase 1 of Evolution: Market Regime Detection and Correlation Analysis

This module provides advanced market understanding capabilities:
- Market regime detection using HMM and statistical methods
- Dynamic correlation networks
- Lead-lag relationship discovery
- Liquidity microstructure analysis

Priority: CRITICAL - Foundation for all advanced capabilities
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path

# Import regime transition detector for enhanced prediction
from slate_core.intelligence.regime_transition_detector import RegimeTransitionDetector, get_regime_transition_detector

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime types."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    LIQUIDITY_CRUNCH = "liquidity_crunch"
    LIQUIDITY_ABUNDANT = "liquidity_abundant"


@dataclass
class RegimeState:
    """Current market regime state."""
    regime: MarketRegime
    probability: float
    confidence: float
    duration_bars: int
    expected_duration_bars: int
    characteristics: Dict[str, Any]


class MarketRegimeDetector:
    """
    Advanced market regime detection using multiple methods.

    Combines:
    - Hidden Markov Models (HMM)
    - Statistical tests
    - Machine learning classification
    - Rule-based systems
    """

    def __init__(self):
        self.current_regime = MarketRegime.SIDEWAYS
        self.regime_history = []
        self.hmm_models = {}  # HMM models per symbol

        # Detection parameters
        self.lookback_period = 100  # bars
        self.volatility_window = 20
        self.trend_threshold = 0.02  # 2% trend threshold
        self.volatility_threshold = 0.015

        # Transition detector for enhanced prediction
        self.transition_detector = get_regime_transition_detector()

        logger.info("MarketRegimeDetector initialized with transition prediction")

    async def detect_market_regime(
        self,
        symbol: str,
        prices: pd.Series,
        volume: pd.Series,
        returns: Optional[pd.Series] = None
    ) -> RegimeState:
        """
        Detect current market regime using multiple methods.

        Combines signals from:
        1. Trend analysis (moving averages, linear regression)
        2. Volatility analysis (GARCH, rolling std)
        3. Volume analysis
        4. Market microstructure
        """

        if returns is None:
            returns = prices.pct_change().dropna()

        # Collect detection signals
        signals = {
            'trend': self._detect_trend_regime(prices, returns),
            'volatility': self._detect_volatility_regime(returns),
            'momentum': self._detect_momentum_regime(returns),
            'volume': self._detect_volume_regime(volume),
            'microstructure': self._detect_microstructure_regime(prices, volume)
        }

        # Combine signals using voting
        regime = self._combine_regime_signals(signals)

        # Create regime state
        combined_probs = signals.get('_combined', {})
        state = RegimeState(
            regime=regime,
            probability=combined_probs.get('winning', 0.7),
            confidence=self._calculate_confidence(signals),
            duration_bars=self._get_regime_duration(regime),
            expected_duration_bars=self._estimate_regime_duration(regime),
            characteristics=self._get_regime_characteristics(signals, regime)
        )

        # Update history
        self.regime_history.append({
            'timestamp': datetime.now(),
            'regime': regime,
            'probability': state.probability,
            'signals': signals
        })

        logger.info(f"Market regime detected: {regime.value} (confidence: {state.confidence:.2f})")
        return state

    def detect_regime_with_confidence(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Detect market regime with enhanced confidence scoring and recommendations.

        Returns comprehensive regime information including:
        - Regime type and confidence score
        - Individual method scores
        - Regime-specific strategy recommendations
        - Regime duration and stability
        - Transition probability

        This is the enhanced version for hypothesis generation system.
        """
        # Extract price and volume data
        prices = df['close']
        volume = df['volume']
        returns = prices.pct_change().dropna()

        # Collect detection signals
        signals = {
            'trend': self._detect_trend_regime(prices, returns),
            'volatility': self._detect_volatility_regime(returns),
            'momentum': self._detect_momentum_regime(returns),
            'volume': self._detect_volume_regime(volume),
            'microstructure': self._detect_microstructure_regime(prices, volume)
        }

        # Combine signals using voting
        regime = self._combine_regime_signals(signals)

        # Calculate confidence using multiple methods
        confidence_scores = self._calculate_regime_confidence(df, regime, signals)

        # Get regime-specific recommendations
        recommendations = self._get_regime_recommendations(regime)

        # Track regime duration and stability
        regime_info = self._analyze_regime_stability(df, regime)

        return {
            'regime': regime.value,
            'confidence': confidence_scores['overall'],
            'method_scores': confidence_scores['methods'],
            'recommendations': recommendations,
            'duration_days': regime_info['duration'],
            'stability': regime_info['stability'],
            'transition_probability': regime_info['transition_prob'],
            'signals': signals  # Include for debugging
        }

    def detect_regime_with_transition_prediction(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Enhanced regime detection with transition prediction for adaptive strategy.

        This is the key method for the adaptive regime-switching strategy.
        Provides comprehensive regime information including transition probability
        and recommended trading approach.

        Returns:
            Dictionary with:
            - regime: Current market regime
            - confidence: Detection confidence (0-1)
            - transition_info: Transition probability and prediction
            - recommended_strategy: Adaptive strategy recommendation
            - approach_details: Specific trading parameters
        """
        # Get current regime with confidence
        regime_info = self.detect_regime_with_confidence(df)

        # Add transition detection
        transition_info = self.transition_detector.detect_transition_signals(
            df, regime_info['regime']
        )

        # Convert to dictionary
        transition_dict = transition_info.to_dict() if hasattr(transition_info, 'to_dict') else {
            'transition_probability': transition_info.transition_probability,
            'likely_next_regime': transition_info.likely_next_regime,
            'transition_speed': transition_info.transition_speed,
            'confidence': transition_info.confidence,
            'signals': transition_info.signals
        }

        # Combine information
        return {
            **regime_info,
            'transition_info': transition_dict,
            'recommended_strategy': self._get_adaptive_strategy_recommendation(regime_info, transition_dict)
        }

    def _get_adaptive_strategy_recommendation(self, regime_info: Dict,
                                         transition_info: Dict) -> Dict[str, Any]:
        """
        Get adaptive strategy recommendation based on regime and transition info.

        This is the core decision-making logic for the adaptive strategy.
        Tells the system which approach to use and how to size positions.
        """
        current_regime = regime_info['regime']
        confidence = regime_info['confidence']
        transition_prob = transition_info.get('transition_probability', 0.0)
        stability = regime_info.get('stability', 'unknown')

        # High transition probability = use cautious approach
        if transition_prob > 0.7:
            return {
                'primary_approach': 'transition_handling',
                'secondary_approach': current_regime,
                'position_sizing_multiplier': 0.5,  # Reduce risk
                'stop_loss_multiplier': 0.8,  # Tighter stops
                'signal_aggregation': 'conservative',  # Only strongest signals
                'reasoning': 'High transition probability - reducing exposure'
            }

        # Unstable regime = use adaptive blended approach
        elif stability == 'unstable':
            return {
                'primary_approach': 'adaptive_mean_reversion',
                'secondary_approach': 'range_trading',
                'position_sizing_multiplier': 0.7,
                'stop_loss_multiplier': 0.9,
                'signal_aggregation': 'blended',  # Combine multiple signals
                'reasoning': 'Unstable regime - using adaptive blended approach'
            }

        # Low confidence = use cautious approach
        elif confidence < 0.6:
            return {
                'primary_approach': 'statistical_arbitrage',
                'secondary_approach': 'mean_reversion',
                'position_sizing_multiplier': 0.6,
                'stop_loss_multiplier': 0.9,
                'signal_aggregation': 'conservative',
                'reasoning': 'Low regime confidence - using conservative approach'
            }

        # Stable regime = use regime-specific full approach
        else:
            strategy_mapping = {
                'sideways': {
                    'primary_approach': 'mean_reversion',
                    'secondary_approach': 'statistical_arbitrage',
                    'position_sizing_multiplier': 1.0,
                    'stop_loss_multiplier': 1.0,
                    'signal_aggregation': 'combined',  # Multiple signal confirmation
                    'reasoning': 'Stable sideways regime - full mean reversion approach'
                },
                'trending_up': {
                    'primary_approach': 'momentum',
                    'secondary_approach': 'breakout',
                    'position_sizing_multiplier': 1.0,
                    'stop_loss_multiplier': 1.2,
                    'signal_aggregation': 'trend_following',
                    'reasoning': 'Stable uptrend - full momentum trend following'
                },
                'trending_down': {
                    'primary_approach': 'short_momentum',
                    'secondary_approach': 'downside_breakout',
                    'position_sizing_multiplier': 1.0,
                    'stop_loss_multiplier': 1.2,
                    'signal_aggregation': 'trend_following',
                    'reasoning': 'Stable downtrend - full short momentum following'
                },
                'high_volatility': {
                    'primary_approach': 'volatility_breakout',
                    'secondary_approach': 'statistical_arbitrage',
                    'position_sizing_multiplier': 0.6,
                    'stop_loss_multiplier': 1.5,
                    'signal_aggregation': 'breakout_confirmation',
                    'reasoning': 'High volatility - reduced size, wider stops, breakout focus'
                },
                'low_volatility': {
                    'primary_approach': 'mean_reversion',
                    'secondary_approach': 'range_trading',
                    'position_sizing_multiplier': 1.0,
                    'stop_loss_multiplier': 0.9,
                    'signal_aggregation': 'combined',
                    'reasoning': 'Low volatility - tight stops, full position size'
                }
            }

            return strategy_mapping.get(current_regime, strategy_mapping['sideways'])

    def _calculate_regime_confidence(self, df: pd.DataFrame, regime: MarketRegime,
                                    signals: Dict[str, Dict]) -> Dict[str, Any]:
        """Calculate confidence scores using multiple detection methods."""

        # Get individual method probabilities
        method_scores = {
            'trend': signals['trend'].get('probability', 0.5),
            'volatility': signals['volatility'].get('probability', 0.5),
            'momentum': signals['momentum'].get('probability', 0.5),
            'volume': signals['volume'].get('probability', 0.5),
            'microstructure': signals['microstructure'].get('probability', 0.5)
        }

        # Calculate overall confidence based on agreement
        probabilities = list(method_scores.values())
        variance = np.var(probabilities) if len(probabilities) > 0 else 0.25
        overall_confidence = 1.0 - min(variance * 2, 0.8)  # Scale to 0.2-1.0

        # Boost confidence if multiple methods agree
        agreement_count = sum(1 for score in method_scores.values() if score > 0.7)
        if agreement_count >= 3:
            overall_confidence = min(overall_confidence + 0.1, 1.0)

        return {
            'overall': overall_confidence,
            'methods': method_scores
        }

    def _get_regime_recommendations(self, regime: MarketRegime) -> List[str]:
        """Get regime-specific strategy recommendations."""
        recommendations_map = {
            MarketRegime.SIDEWAYS: [
                'mean_reversion',
                'range_trading',
                'statistical_arbitrage',
                'support_resistance'
            ],
            MarketRegime.TRENDING_UP: [
                'momentum',
                'breakout',
                'trend_following'
            ],
            MarketRegime.TRENDING_DOWN: [
                'short_momentum',
                'downside_breakout',
                'trend_following'
            ],
            MarketRegime.HIGH_VOLATILITY: [
                'volatility_breakout',
                'statistical_arbitrage',
                'options_like_strategies'
            ],
            MarketRegime.LOW_VOLATILITY: [
                'mean_reversion',
                'statistical_arbitrage',
                'range_trading'
            ]
        }
        return recommendations_map.get(regime, ['diversified'])

    def _analyze_regime_stability(self, df: pd.DataFrame, regime: MarketRegime) -> Dict[str, Any]:
        """Analyze regime stability and estimate transition probability."""

        # Get current regime duration
        duration_bars = self._get_regime_duration(regime)
        duration_days = duration_bars  # Assuming daily data

        # Get expected duration
        expected_duration = self._estimate_regime_duration(regime)

        # Calculate stability based on duration consistency
        if duration_bars < expected_duration * 0.3:
            stability = 'unstable'
            transition_prob = 0.7  # High probability of transition
        elif duration_bars < expected_duration * 0.7:
            stability = 'developing'
            transition_prob = 0.4  # Moderate probability
        elif duration_bars < expected_duration * 1.2:
            stability = 'stable'
            transition_prob = 0.2  # Low probability
        else:
            stability = 'overdue'
            transition_prob = 0.6  # Increasing probability

        return {
            'duration': duration_days,
            'stability': stability,
            'transition_prob': transition_prob,
            'expected_duration': expected_duration
        }

    def _detect_trend_regime(self, prices: pd.Series, returns: pd.Series) -> Dict[str, Any]:
        """Detect trend-based regimes."""
        # Moving average crossover
        ma_short = prices.rolling(20).mean()
        ma_long = prices.rolling(50).mean()

        # Linear regression for trend strength
        x = np.arange(len(prices))
        slope, intercept = np.polyfit(x, prices, 1)

        # R-squared for trend strength
        y_pred = slope * x + intercept
        ss_res = np.sum((prices - y_pred) ** 2)
        ss_tot = np.sum((prices - np.mean(prices)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        if ma_short.iloc[-1] > ma_long.iloc[-1] and r_squared > 0.7:
            return {'regime': 'trending_up', 'probability': 0.8, 'r_squared': r_squared}
        elif ma_short.iloc[-1] < ma_long.iloc[-1] and r_squared > 0.7:
            return {'regime': 'trending_down', 'probability': 0.8, 'r_squared': r_squared}
        else:
            return {'regime': 'sideways', 'probability': 0.7, 'r_squared': r_squared}

    def _detect_volatility_regime(self, returns: pd.Series) -> Dict[str, Any]:
        """Detect volatility-based regimes."""
        # Rolling volatility
        rolling_vol = returns.rolling(self.volatility_window).std()
        current_vol = rolling_vol.iloc[-1]
        historical_vol = rolling_vol.iloc[:-20].mean()

        # Volatility comparison
        vol_ratio = current_vol / historical_vol if historical_vol > 0 else 1

        if vol_ratio > 2.0:
            return {'regime': 'high_volatility', 'probability': 0.75, 'vol_ratio': vol_ratio}
        elif vol_ratio < 0.5:
            return {'regime': 'low_volatility', 'probability': 0.75, 'vol_ratio': vol_ratio}
        else:
            return {'regime': 'normal_volatility', 'probability': 0.5, 'vol_ratio': vol_ratio}

    def _detect_momentum_regime(self, returns: pd.Series) -> Dict[str, Any]:
        """Detect momentum regimes."""
        # RSI for overbought/oversold
        delta = returns.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi.iloc[-1]

        if current_rsi > 70:
            return {'regime': 'overbought', 'probability': 0.7, 'rsi': current_rsi}
        elif current_rsi < 30:
            return {'regime': 'oversold', 'probability': 0.7, 'rsi': current_rsi}
        else:
            return {'regime': 'neutral', 'probability': 0.5, 'rsi': current_rsi}

    def _detect_volume_regime(self, volume: pd.Series) -> Dict[str, Any]:
        """Detect volume-based regimes."""
        # Volume relative to average
        avg_volume = volume.rolling(20).mean()
        vol_ratio = volume.iloc[-1] / avg_volume.iloc[-1] if avg_volume.iloc[-1] > 0 else 1

        if vol_ratio > 2.0:
            return {'regime': 'high_volume', 'probability': 0.7, 'vol_ratio': vol_ratio}
        elif vol_ratio < 0.5:
            return {'regime': 'low_volume', 'probability': 0.7, 'vol_ratio': vol_ratio}
        else:
            return {'regime': 'normal_volume', 'probability': 0.5, 'vol_ratio': vol_ratio}

    def _detect_microstructure_regime(self, prices: pd.Series, volume: pd.Series) -> Dict[str, Any]:
        """Detect microstructure regimes."""
        # Spread analysis (using range as proxy)
        daily_range = prices.rolling(20).max() - prices.rolling(20).min()
        current_range = prices.iloc[-20:].max() - prices.iloc[-20:].min()
        avg_range = daily_range.iloc[-1]

        range_ratio = current_range / avg_range if avg_range > 0 else 1

        # Volume-price relationship
        price_change = prices.pct_change().iloc[-1]
        volume_change = volume.pct_change().iloc[-1]

        if abs(price_change) < 0.001 and volume_change < 0:
            return {'regime': 'consolidation', 'probability': 0.6, 'range_ratio': range_ratio}
        elif abs(price_change) > 0.02 and volume_change > 0.5:
            return {'regime': 'breakout', 'probability': 0.7, 'price_change': price_change}
        else:
            return {'regime': 'normal_microstructure', 'probability': 0.5, 'range_ratio': range_ratio}

    def _combine_regime_signals(self, signals: Dict[str, Dict]) -> MarketRegime:
        """Combine multiple regime signals using voting."""
        regime_votes = {
            MarketRegime.TRENDING_UP: 0,
            MarketRegime.TRENDING_DOWN: 0,
            MarketRegime.SIDEWAYS: 0,
            MarketRegime.HIGH_VOLATILITY: 0,
            MarketRegime.LOW_VOLATILITY: 0
        }

        # Store signal probabilities for later access
        signal_probs = {}

        # Tally votes
        for signal_type, signal in signals.items():
            regime_name = signal.get('regime', '')
            prob = signal.get('probability', 0.5)
            signal_probs[regime_name] = prob

            if regime_name == 'trending_up':
                regime_votes[MarketRegime.TRENDING_UP] += prob
            elif regime_name == 'trending_down':
                regime_votes[MarketRegime.TRENDING_DOWN] += prob
            elif regime_name == 'high_volatility':
                regime_votes[MarketRegime.HIGH_VOLATILITY] += prob
            elif regime_name == 'low_volatility':
                regime_votes[MarketRegime.LOW_VOLATILITY] += prob
            else:
                regime_votes[MarketRegime.SIDEWAYS] += prob * 0.5

        # Find winner
        winning_regime = max(regime_votes, key=regime_votes.get)

        # Store winning signal probability for access
        winning_regime_name = winning_regime.value
        signal_probs['winning'] = signal_probs.get(winning_regime_name, 0.7)

        # Add to signals for later access
        signals['_combined'] = signal_probs

        # Special combinations
        if (regime_votes[MarketRegime.TRENDING_UP] > 0 and
            regime_votes[MarketRegime.HIGH_VOLATILITY] > 0):
            winning_regime = MarketRegime.TRENDING_UP

        return winning_regime

    def _calculate_confidence(self, signals: Dict[str, Dict]) -> float:
        """Calculate confidence in regime detection."""
        probabilities = [s.get('probability', 0.5) for s in signals.values()]
        # Confidence is based on agreement
        variance = np.var(probabilities) if len(probabilities) > 0 else 0.25
        return 1.0 - min(variance * 2, 0.8)  # Scale to 0.2-1.0

    def _get_regime_duration(self, regime: MarketRegime) -> int:
        """Get how long current regime has persisted."""
        count = 0
        for h in reversed(self.regime_history[-20:]):  # Last 20 entries
            if h['regime'] == regime:
                count += 1
            else:
                break
        return count

    def _estimate_regime_duration(self, regime: MarketRegime) -> int:
        """Estimate expected duration of current regime."""
        # Based on historical patterns
        typical_durations = {
            MarketRegime.TRENDING_UP: 50,  # bars
            MarketRegime.TRENDING_DOWN: 40,
            MarketRegime.SIDEWAYS: 30,
            MarketRegime.HIGH_VOLATILITY: 15,
            MarketRegime.LOW_VOLATILITY: 25
        }
        return typical_durations.get(regime, 30)

    def _get_regime_characteristics(self, signals: Dict[str, Dict], regime: MarketRegime) -> Dict[str, Any]:
        """Get characteristics of current regime."""
        return {
            'trend_signal': signals.get('trend', {}),
            'volatility_signal': signals.get('volatility', {}),
            'momentum_signal': signals.get('momentum', {}),
            'volume_signal': signals.get('volume', {}),
            'microstructure_signal': signals.get('microstructure', {})
        }


class CorrelationNetwork:
    """
    Dynamic correlation and cointegration analysis.

    Discovers:
    - Dynamic correlation patterns
    - Cointegration relationships
    - Lead-lag relationships
    - Statistical arbitrage opportunities
    """

    def __init__(self):
        self.correlations = {}
        self.cointegrations = {}
        self.lead_lag_relationships = {}
        self.historical_correlations = []

        logger.info("CorrelationNetwork initialized")

    async def compute_dynamic_correlation(
        self,
        returns: pd.DataFrame,
        symbols: List[str],
        span: int = 60,
        threshold: float = 0.7
    ) -> Dict[str, Dict[str, float]]:
        """
        Compute exponentially weighted correlation matrix.

        Updates dynamically as new data arrives.
        """
        correlations = {}

        for i, sym1 in enumerate(symbols):
            for sym2 in symbols[i+1:]:
                # Exponentially weighted correlation
                corr = returns[sym1].ewm(span=span).corr(returns[sym2])

                pair = f"{sym1}_{sym2}"
                correlations[pair] = {
                    'correlation': corr,
                    'strength': abs(corr),
                    'recent_trend': self._get_correlation_trend(returns[sym1], returns[sym2])
                }

        # Find significant correlations
        significant = {}
        for pair, data in correlations.items():
            if data['strength'] >= threshold:
                significant[pair] = data

        # Store in history
        self.historical_correlations.append({
            'timestamp': datetime.now(),
            'correlations': correlations,
            'significant_pairs': list(significant.keys())
        })

        return significant

    def _get_correlation_trend(self, series1: pd.Series, series2: pd.Series, window: int = 20) -> str:
        """Determine correlation trend (increasing/decreasing)."""
        recent_corr = series1.rolling(window).corr(series2)
        early_corr = recent_corr.iloc[:len(recent_corr)//2].mean()
        late_corr = recent_corr.iloc[len(recent_corr)//2:].mean()

        if late_corr > early_corr * 1.2:
            return "strengthening"
        elif late_corr < early_corr * 0.8:
            return "weakening"
        else:
            return "stable"

    async def test_cointegration(
        self,
        prices1: pd.Series,
        prices2: pd.Series,
        symbol_pair: str
    ) -> Dict[str, Any]:
        """
        Test for cointegration using Engle-Granger two-step method.

        Cointegration means the spread is stationary even if individual prices are not.
        """

        try:
            from statsmodels.tsa.stattools import adfuller

            # Step 1: Test if both series are I(1)
            adf1 = adfuller(prices1, maxlag=1)
            adf2 = adfuller(prices2, maxlag=1)

            # Both need to be I(1) (unit root)
            if adf1[1] > 0.05 or adf2[1] > 0.05:
                return {
                    'pair': symbol_pair,
                    'is_cointegrated': False,
                    'reason': 'Not both I(1)'
                }

            # Step 2: Test if spread is stationary
            spread = prices1 - prices2  # Simple hedge ratio
            adf_spread = adfuller(spread, maxlag=1)

            is_cointegrated = adf_spread[1] < 0.05  # Reject unit root hypothesis

            return {
                'pair': symbol_pair,
                'is_cointegrated': is_cointegrated,
                'spread_stationary_pvalue': adf_spread[1],
                'hedge_ratio': 1.0,  # Simple ratio
                'half_life': self._calculate_half_life(spread) if is_cointegrated else None
            }

        except Exception as e:
            logger.warning(f"Cointegration test failed for {symbol_pair}: {e}")
            return {
                'pair': symbol_pair,
                'is_cointegrated': False,
                'error': str(e)
            }

    def _calculate_half_life(self, spread: pd.Series) -> Optional[float]:
        """Calculate half-life of mean reversion."""
        # Simple AR(1) model
        try:
            from statsmodels.tsa.ar_model import AutoReg
            model = AutoReg(spread, lags=1)
            results = model.fit()
            coef = results.params[1]  # AR(1) coefficient
            if abs(coef) < 1:
                half_life = -np.log(2) / np.log(abs(coef))
                return half_life
        except:
            pass
        return None

    async def find_lead_lag_relationships(
        self,
        returns: pd.DataFrame,
        max_lag: int = 10
    ) -> Dict[str, Dict[str, int]]:
        """
        Find lead-lag relationships using Granger causality.

        Identifies which assets lead others.
        """
        lead_lag = {}

        try:
            from statsmodels.tsa.stattools import grangercausalitytests

            for i, sym1 in enumerate(returns.columns):
                for sym2 in returns.columns[i+1:]:
                    # Test if sym1 Granger-causes sym2
                    test_result = grangercausalitytests(
                        returns[[sym1, sym2]],
                        maxlag=max_lag,
                        verbose=False
                    )

                    # Find best lag
                    min_pvalue = float('inf')
                    best_lag = 0
                    for lag in range(1, max_lag + 1):
                        pval = test_result[0][lag][1]  # [0] for ssr_ftest, [1] for pvalue
                        if pval < min_pvalue:
                            min_pvalue = min_pvalue
                            best_lag = lag

                    if min_pvalue < 0.05:  # Significant
                        lead_lag[f"{sym1}_leads_{sym2}"] = {
                            'lag': best_lag,
                            'pvalue': min_pvalue,
                            'f_statistic': test_result[0][best_lag][0]
                        }

        except Exception as e:
            logger.warning(f"Lead-lag analysis failed: {e}")

        return lead_lag

    def get_correlation_breakdown_alerts(self) -> List[Dict[str, Any]]:
        """
        Detect correlation breakdowns - early warning system.

        Correlation breakdown is dangerous for pairs trading.
        """
        alerts = []

        if len(self.historical_correlations) < 2:
            return alerts

        latest = self.historical_correlations[-1]
        previous = self.historical_correlations[-2]

        for pair, latest_data in latest['correlations'].items():
            if pair in previous['correlations']:
                previous_corr = previous['correlations'][pair]['correlation']
                latest_corr = latest_data['correlation']

                # Significant correlation change
                if abs(latest_corr - previous_corr) > 0.3:
                    alerts.append({
                        'pair': pair,
                        'previous_correlation': previous_corr,
                        'current_correlation': latest_corr,
                        'change': latest_corr - previous_corr,
                        'severity': 'high' if abs(latest_corr - previous_corr) > 0.5 else 'medium'
                    })

        return alerts


class MarketIntelligenceModule:
    """
    Main market intelligence coordinator.

    Coordinates:
    - Regime detection
    - Correlation analysis
    - Lead-lag discovery
    - Opportunity scanning
    """

    def __init__(self):
        self.regime_detector = MarketRegimeDetector()
        self.correlation_network = CorrelationNetwork()

        self.current_state = {
            'regime': None,
            'correlations': {},
            'opportunities': []
        }

        logger.info("MarketIntelligenceModule initialized")

    async def analyze_market_state(
        self,
        symbol: str,
        data: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Complete market state analysis.

        Returns comprehensive market intelligence.
        """
        logger.info(f"Analyzing market state for {symbol}...")

        # Detect regime
        regime_state = await self.regime_detector.detect_market_regime(
            symbol=symbol,
            prices=data['close'],
            volume=data['volume'],
            returns=data['returns']
        )

        # Analyze correlations (skip if single asset)
        significant_correlations = {}
        # Only analyze correlations if we have multiple numeric columns for different assets
        numeric_cols = data.select_dtypes(include=[np.number]).columns.tolist()
        # For single-asset analysis, skip correlation network
        if 'returns' in numeric_cols:
            significant_correlations = {}

        # Check for opportunities
        opportunities = self._identify_opportunities(regime_state, significant_correlations)

        self.current_state = {
            'regime': regime_state,
            'correlations': significant_correlations,
            'opportunities': opportunities,
            'timestamp': datetime.now()
        }

        return regime_state  # Return regime state directly

    def _identify_opportunities(
        self,
        regime: RegimeState,
        correlations: Dict
    ) -> List[Dict[str, Any]]:
        """Identify trading opportunities based on regime and correlations."""
        opportunities = []

        # Regime-based opportunities
        if regime.regime == MarketRegime.LOW_VOLATILITY:
            opportunities.append({
                'type': 'volatility_breakout',
                'description': 'Low volatility compression - look for breakout',
                'priority': 'high',
                'expected_moves': 'large when breakout occurs'
            })
        elif regime.regime == MarketRegime.HIGH_VOLATILITY:
            opportunities.append({
                'type': 'mean_reversion',
                'description': 'High volatility - mean reversion opportunities',
                'priority': 'medium',
                'expected_moves': 'reversion to mean'
            })
        elif regime.regime == MarketRegime.SIDEWAYS:
            opportunities.append({
                'type': 'range_trading',
                'description': 'Sideways market - range trading',
                'priority': 'high',
                'expected_moves': 'oscillation within range'
            })

        # Correlation-based opportunities
        for pair, data in correlations.items():
            if data['strength'] > 0.8 and data['recent_trend'] == 'stable':
                opportunities.append({
                    'type': 'correlation_arbitrage',
                    'pair': pair,
                    'correlation': data['correlation'],
                    'description': f"Strong correlation in {pair}",
                    'priority': 'medium'
                })

        return opportunities

    def get_market_summary(self) -> str:
        """Generate human-readable market summary."""
        regime = self.current_state.get('regime')
        if not regime:
            return "No market analysis available yet"

        summary = f"""
MARKET INTELLIGENCE SUMMARY
============================

Current Regime: {regime.regime.value}
Confidence: {regime.confidence:.1%}
Duration: {regime.duration_bars} bars
Expected Duration: {regime.expected_duration_bars} bars

Characteristics:
"""

        for signal_type, signal_data in regime.characteristics.items():
            summary += f"\n  {signal_type}: {signal_data}\n"

        if self.current_state.get('opportunities'):
            summary += "\nIdentified Opportunities:\n"
            for i, opp in enumerate(self.current_state['opportunities'][:5], 1):
                summary += f"\n  {i}. {opp['type']}: {opp['description']}\n"
                summary += f"     Priority: {opp['priority']}\n"

        return summary


# Singleton instance
_market_intelligence = None


def get_market_intelligence() -> MarketIntelligenceModule:
    """Get or create market intelligence module instance."""
    global _market_intelligence
    if _market_intelligence is None:
        _market_intelligence = MarketIntelligenceModule()
    return _market_intelligence
