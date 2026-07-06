#!/usr/bin/env python3
"""
Regime Transition Detection System

Provides early warning of regime changes and transition predictions
for adaptive regime-switching strategy.

Key Features:
- Early detection of regime transition signals
- Transition probability estimation
- Next regime prediction
- Transition speed estimation
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
import logging
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TransitionInfo:
    """Information about regime transition"""
    transition_probability: float  # 0-1 probability of regime change
    likely_next_regime: str
    transition_speed: str  # fast, medium, slow
    confidence: float  # 0-1 confidence in prediction
    signals: Dict[str, float]  # Individual signal scores
    detected_at: datetime = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'transition_probability': self.transition_probability,
            'likely_next_regime': self.likely_next_regime,
            'transition_speed': self.transition_speed,
            'confidence': self.confidence,
            'signals': self.signals,
            'detected_at': self.detected_at.isoformat() if self.detected_at else None
        }


class RegimeTransitionDetector:
    """
    Detects and predicts regime transitions for adaptive strategy.

    Analyzes multiple indicators to provide early warning of regime changes:
    - Volatility expansion/contraction
    - Trend strength changes
    - Range breakouts
    - Volume anomalies
    - Momentum shifts
    """

    def __init__(self):
        self.regime_history = []
        self.transition_patterns = {}

        # Detection parameters
        self.volatility_lookback = 20
        self.volatility_long_lookback = 60
        self.trend_lookback = 60
        self.volume_lookback = 20
        self.momentum_lookback = 14

        logger.info("RegimeTransitionDetector initialized")

    def detect_transition_signals(self, df: pd.DataFrame,
                                  current_regime: str) -> TransitionInfo:
        """
        Detect early signals of regime transition.

        Args:
            df: Market data DataFrame
            current_regime: Current market regime

        Returns:
            TransitionInfo with transition probability and predictions
        """
        if len(df) < self.volatility_long_lookback:
            # Not enough data for transition detection
            return TransitionInfo(
                transition_probability=0.0,
                likely_next_regime=current_regime,
                transition_speed='slow',
                confidence=0.0,
                signals={},
                detected_at=datetime.now()
            )

        # Analyze individual transition signals
        signals = {
            'volatility_expansion': self._check_volatility_expansion(df),
            'volatility_contraction': self._check_volatility_contraction(df),
            'trend_weakening': self._check_trend_weakening(df),
            'trend_strengthening': self._check_trend_strengthening(df),
            'range_breakout': self._check_range_breakout(df),
            'volume_anomaly': self._check_volume_anomaly(df),
            'momentum_shift': self._check_momentum_shift(df),
            'price_acceleration': self._check_price_acceleration(df)
        }

        # Calculate overall transition probability
        transition_score = self._calculate_transition_score(signals)

        # Predict most likely next regime
        next_regime = self._predict_next_regime(current_regime, signals)

        # Estimate transition speed
        speed = self._estimate_transition_speed(signals)

        # Calculate confidence in prediction
        confidence = self._calculate_prediction_confidence(signals, transition_score)

        return TransitionInfo(
            transition_probability=transition_score,
            likely_next_regime=next_regime,
            transition_speed=speed,
            confidence=confidence,
            signals=signals,
            detected_at=datetime.now()
        )

    def _check_volatility_expansion(self, df: pd.DataFrame) -> float:
        """Check if volatility is expanding (regime change indicator)"""
        if len(df) < self.volatility_long_lookback:
            return 0.0

        # Calculate recent and historical volatility
        recent_vol = df['close'].pct_change().rolling(self.volatility_lookback).std().iloc[-1]
        historical_vol = df['close'].pct_change().rolling(self.volatility_long_lookback).std().iloc[-1]

        if historical_vol == 0 or np.isnan(historical_vol):
            return 0.0

        vol_ratio = recent_vol / historical_vol

        # Significant expansion = potential regime change
        if vol_ratio > 1.5:
            return min(vol_ratio - 1.0, 1.0)  # 0-1 score
        elif vol_ratio > 1.2:
            return 0.3  # Moderate expansion
        else:
            return 0.0

    def _check_volatility_contraction(self, df: pd.DataFrame) -> float:
        """Check if volatility is contracting (transition to stable regime)"""
        if len(df) < self.volatility_long_lookback:
            return 0.0

        recent_vol = df['close'].pct_change().rolling(self.volatility_lookback).std().iloc[-1]
        historical_vol = df['close'].pct_change().rolling(self.volatility_long_lookback).std().iloc[-1]

        if historical_vol == 0 or np.isnan(historical_vol):
            return 0.0

        vol_ratio = recent_vol / historical_vol

        # Significant contraction = potential move to stable regime
        if vol_ratio < 0.5:
            return min(1.0 - vol_ratio, 1.0)
        elif vol_ratio < 0.8:
            return 0.3
        else:
            return 0.0

    def _check_trend_weakening(self, df: pd.DataFrame) -> float:
        """Check if trend is weakening (potential transition to range)"""
        if len(df) < self.trend_lookback:
            return 0.0

        # Calculate trend strength using linear regression R²
        x = np.arange(len(df))

        try:
            slope, intercept = np.polyfit(x, df['close'], 1)
            y_pred = slope * x + intercept
            ss_res = np.sum((df['close'] - y_pred) ** 2)
            ss_tot = np.sum((df['close'] - np.mean(df['close'])) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            # Calculate recent R²
            recent_data = df.iloc[-30:]  # Last 30 bars
            x_recent = np.arange(len(recent_data))
            slope_recent, intercept_recent = np.polyfit(x_recent, recent_data['close'], 1)
            y_pred_recent = slope_recent * x_recent + intercept_recent
            ss_res_recent = np.sum((recent_data['close'] - y_pred_recent) ** 2)
            ss_tot_recent = np.sum((recent_data['close'] - np.mean(recent_data['close'])) ** 2)
            r_squared_recent = 1 - (ss_res_recent / ss_tot_recent) if ss_tot_recent > 0 else 0

            # Weakening trend = decreasing R²
            if r_squared > 0.7 and r_squared_recent < 0.5:
                return 0.8  # High probability of trend weakening
            elif r_squared > 0.6 and r_squared_recent < 0.4:
                return 0.6
            elif r_squared_recent < r_squared * 0.7:
                return 0.4
            else:
                return 0.0

        except Exception as e:
            logger.warning(f"Error calculating trend weakening: {e}")
            return 0.0

    def _check_trend_strengthening(self, df: pd.DataFrame) -> float:
        """Check if trend is strengthening (potential transition to trending)"""
        if len(df) < self.trend_lookback:
            return 0.0

        try:
            # Calculate R² for different periods
            recent_data = df.iloc[-30:]
            x_recent = np.arange(len(recent_data))

            slope_recent, intercept_recent = np.polyfit(x_recent, recent_data['close'], 1)
            y_pred_recent = slope_recent * x_recent + intercept_recent
            ss_res_recent = np.sum((recent_data['close'] - y_pred_recent) ** 2)
            ss_tot_recent = np.sum((recent_data['close'] - np.mean(recent_data['close'])) ** 2)
            r_squared_recent = 1 - (ss_res_recent / ss_tot_recent) if ss_tot_recent > 0 else 0

            older_data = df.iloc[-60:-30]
            x_older = np.arange(len(older_data))

            slope_older, intercept_older = np.polyfit(x_older, older_data['close'], 1)
            y_pred_older = slope_older * x_older + intercept_older
            ss_res_older = np.sum((older_data['close'] - y_pred_older) ** 2)
            ss_tot_older = np.sum((older_data['close'] - np.mean(older_data['close'])) ** 2)
            r_squared_older = 1 - (ss_res_older / ss_tot_older) if ss_tot_older > 0 else 0

            # Strengthening trend = increasing R²
            if r_squared_recent > 0.6 and r_squared_recent > r_squared_older * 1.2:
                return 0.7
            elif r_squared_recent > 0.5 and r_squared_recent > r_squared_older:
                return 0.5
            else:
                return 0.0

        except Exception as e:
            logger.warning(f"Error calculating trend strengthening: {e}")
            return 0.0

    def _check_range_breakout(self, df: pd.DataFrame) -> float:
        """Check for range breakout (potential transition to trending)"""
        if len(df) < 50:
            return 0.0

        # Define recent range
        recent = df.iloc[-20:]
        range_high = recent['high'].max()
        range_low = recent['low'].min()
        range_size = (range_high - range_low) / range_low if range_low > 0 else 0

        current_price = df['close'].iloc[-1]

        # Check for breakout
        if current_price > range_high:
            # Upside breakout
            breakout_strength = (current_price - range_high) / range_size if range_size > 0 else 0
            return min(breakout_strength, 1.0)
        elif current_price < range_low:
            # Downside breakout
            breakout_strength = (range_low - current_price) / range_size if range_size > 0 else 0
            return min(breakout_strength, 1.0)
        else:
            return 0.0

    def _check_volume_anomaly(self, df: pd.DataFrame) -> float:
        """Check for unusual volume (potential regime change)"""
        if len(df) < self.volume_lookback:
            return 0.0

        current_volume = df['volume'].iloc[-1]
        avg_volume = df['volume'].rolling(self.volume_lookback).mean().iloc[-1]

        if avg_volume == 0 or np.isnan(avg_volume):
            return 0.0

        volume_ratio = current_volume / avg_volume

        # Significant volume anomaly
        if volume_ratio > 2.5 or volume_ratio < 0.4:
            return 0.7
        elif volume_ratio > 2.0 or volume_ratio < 0.5:
            return 0.5
        elif volume_ratio > 1.5 or volume_ratio < 0.67:
            return 0.3
        else:
            return 0.0

    def _check_momentum_shift(self, df: pd.DataFrame) -> float:
        """Check for momentum reversal (potential regime change)"""
        if len(df) < self.momentum_lookback * 2:
            return 0.0

        # Calculate RSI for momentum
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(self.momentum_lookback).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.momentum_lookback).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        current_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2]

        # Check for extreme RSI reversal
        if prev_rsi > 70 and current_rsi < 50:
            return 0.8  # Strong overbought reversal
        elif prev_rsi < 30 and current_rsi > 50:
            return 0.8  # Strong oversold reversal
        elif prev_rsi > 65 and current_rsi < 45:
            return 0.5
        elif prev_rsi < 35 and current_rsi > 55:
            return 0.5
        else:
            return 0.0

    def _check_price_acceleration(self, df: pd.DataFrame) -> float:
        """Check for price acceleration (potential regime change)"""
        if len(df) < 10:
            return 0.0

        # Calculate price changes
        price_changes = df['close'].pct_change().iloc[-5:]

        # Check for acceleration
        if len(price_changes) < 5:
            return 0.0

        # Calculate second derivative (acceleration)
        acceleration = price_changes.diff()

        # Significant acceleration = regime change potential
        max_acceleration = acceleration.abs().max()

        if max_acceleration > 0.05:  # 5% acceleration
            return min(max_acceleration, 1.0)
        elif max_acceleration > 0.03:
            return 0.6
        elif max_acceleration > 0.02:
            return 0.3
        else:
            return 0.0

    def _calculate_transition_score(self, signals: Dict[str, float]) -> float:
        """Calculate overall transition probability from individual signals"""
        if not signals:
            return 0.0

        # Get signal values
        signal_values = [v for v in signals.values() if isinstance(v, (int, float))]

        if not signal_values:
            return 0.0

        # Calculate weighted average (some signals more important)
        weights = {
            'volatility_expansion': 1.5,
            'volatility_contraction': 1.2,
            'trend_weakening': 1.3,
            'trend_strengthening': 1.0,
            'range_breakout': 1.4,
            'volume_anomaly': 1.0,
            'momentum_shift': 1.2,
            'price_acceleration': 1.1
        }

        weighted_sum = 0
        total_weight = 0

        for signal_name, signal_value in signals.items():
            if isinstance(signal_value, (int, float)):
                weight = weights.get(signal_name, 1.0)
                weighted_sum += signal_value * weight
                total_weight += weight

        if total_weight == 0:
            return 0.0

        transition_score = weighted_sum / total_weight

        return min(transition_score, 1.0)

    def _predict_next_regime(self, current_regime: str,
                           signals: Dict[str, float]) -> str:
        """Predict most likely next regime based on transition patterns"""

        # Historical transition probabilities (can be learned from data)
        transition_matrix = {
            'sideways': {
                'high_volatility': 0.30,
                'trending_up': 0.25,
                'trending_down': 0.25,
                'sideways': 0.20
            },
            'trending_up': {
                'sideways': 0.40,
                'high_volatility': 0.25,
                'trending_down': 0.20,
                'trending_up': 0.15
            },
            'trending_down': {
                'sideways': 0.40,
                'high_volatility': 0.25,
                'trending_up': 0.20,
                'trending_down': 0.15
            },
            'high_volatility': {
                'sideways': 0.35,
                'trending_up': 0.25,
                'trending_down': 0.25,
                'low_volatility': 0.15
            }
        }

        # Get base probabilities
        regime_transitions = transition_matrix.get(current_regime, {})

        # Adjust based on current signals
        adjusted_transitions = regime_transitions.copy()

        # If volatility expansion, increase volatile regime probability
        if signals.get('volatility_expansion', 0) > 0.5:
            adjusted_transitions['high_volatility'] *= 1.5

        # If volatility contraction, increase stable regime probability
        if signals.get('volatility_contraction', 0) > 0.5:
            adjusted_transitions['sideways'] *= 1.5

        # If trend weakening, increase sideways probability
        if signals.get('trend_weakening', 0) > 0.5:
            if 'trending_up' in current_regime or 'trending_down' in current_regime:
                adjusted_transitions['sideways'] *= 2.0

        # If trend strengthening, increase trending probability
        if signals.get('trend_strengthening', 0) > 0.5:
            if current_regime == 'sideways':
                adjusted_transitions['trending_up'] *= 2.0 if signals.get('range_breakout', 0) > 0 else 1.0

        # Return most likely next regime
        if adjusted_transitions:
            return max(adjusted_transitions, key=adjusted_transitions.get)
        else:
            return current_regime

    def _estimate_transition_speed(self, signals: Dict[str, float]) -> str:
        """Estimate how fast the transition will occur"""
        signal_strength = sum(signals.values()) / len(signals) if signals else 0

        if signal_strength > 0.7:
            return "fast"  # 1-3 bars
        elif signal_strength > 0.4:
            return "medium"  # 3-10 bars
        else:
            return "slow"  # 10+ bars

    def _calculate_prediction_confidence(self, signals: Dict[str, float],
                                       transition_score: float) -> float:
        """Calculate confidence in transition prediction"""
        if not signals:
            return 0.0

        # Confidence based on:
        # 1. Number of strong signals
        # 2. Agreement between signals
        # 3. Overall transition score

        strong_signals = sum(1 for v in signals.values() if v > 0.5)
        total_signals = len(signals)

        # Signal concentration (how many strong signals)
        signal_concentration = strong_signals / total_signals if total_signals > 0 else 0

        # Agreement check (are signals pointing in same direction?)
        # Simplified: if multiple strong signals, higher confidence
        confidence = min(transition_score + signal_concentration * 0.2, 1.0)

        return max(confidence, 0.0)


def get_regime_transition_detector() -> RegimeTransitionDetector:
    """Factory function to get regime transition detector"""
    return RegimeTransitionDetector()