"""
SLATE Regime Detector

Detects market regimes using Hidden Markov Models and volatility analysis.
Regimes: BULL_VOLATILE, BULL_STABLE, BEAR_VOLATILE, BEAR_STABLE, RANGING, TRANSITION
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime types."""
    BULL_VOLATILE = "bull_volatile"
    BULL_STABLE = "bull_stable"
    BEAR_VOLATILE = "bear_volatile"
    BEAR_STABLE = "bear_stable"
    RANGING = "ranging"
    TRANSITION = "transition"


@dataclass
class RegimeState:
    """Regime state with confidence."""
    regime: MarketRegime
    confidence: float
    volatility: float
    trend: float
    timestamp: datetime


class RegimeDetector:
    """
    Detect market regimes using statistical analysis.

    Uses:
    - Volatility analysis (rolling standard deviation)
    - Trend analysis (moving average slopes)
    - Return distribution analysis
    """

    def __init__(self, lookback_period: int = 20):
        self.lookback_period = lookback_period
        self.price_history: List[float] = []
        self.current_regime: Optional[RegimeState] = None
        self.regime_history: List[RegimeState] = []

        # Volatility thresholds
        self.low_vol_threshold = 0.01  # 1% daily move
        self.high_vol_threshold = 0.03  # 3% daily move

        # Trend thresholds
        self.strong_trend = 0.02  # 2% per period
        self.weak_trend = 0.005  # 0.5% per period

        logger.info("Regime Detector initialized")

    async def detect_regime(self, observation) -> MarketRegime:
        """
        Detect current market regime from observation.

        Uses price and indicator data to classify regime.
        """
        # Get price data
        price = observation.price
        self.price_history.append(price)

        # Keep only recent history
        if len(self.price_history) > self.lookback_period * 2:
            self.price_history = self.price_history[-self.lookback_period * 2:]

        if len(self.price_history) < self.lookback_period:
            return MarketRegime.TRANSITION

        # Calculate metrics
        volatility = self._calculate_volatility()
        trend = self._calculate_trend()

        # Determine regime
        regime = self._classify_regime(volatility, trend)

        # Calculate confidence
        confidence = self._calculate_confidence(volatility, trend)

        # Update state
        self.current_regime = RegimeState(
            regime=regime,
            confidence=confidence,
            volatility=volatility,
            trend=trend,
            timestamp=datetime.now()
        )

        self.regime_history.append(self.current_regime)

        logger.debug(f"Regime detected: {regime.value} (confidence: {confidence:.2f})")

        return regime

    async def get_confidence(self) -> float:
        """Get confidence in current regime detection."""
        if self.current_regime:
            return self.current_regime.confidence
        return 0.0

    def _calculate_volatility(self) -> float:
        """Calculate rolling volatility (standard deviation of returns)."""
        if len(self.price_history) < 2:
            return 0.0

        prices = np.array(self.price_history[-self.lookback_period:])
        returns = np.diff(prices) / prices[:-1]

        return float(np.std(returns))

    def _calculate_trend(self) -> float:
        """Calculate trend strength (linear regression slope)."""
        if len(self.price_history) < self.lookback_period:
            return 0.0

        prices = np.array(self.price_history[-self.lookback_period:])
        x = np.arange(len(prices))

        # Simple linear regression
        slope = np.polyfit(x, prices, 1)[0]

        # Normalize by price
        return float(slope / np.mean(prices))

    def _classify_regime(self, volatility: float, trend: float) -> MarketRegime:
        """Classify regime based on volatility and trend."""
        is_volatile = volatility > self.high_vol_threshold
        is_stable = volatility < self.low_vol_threshold
        is_bull = trend > self.strong_trend
        is_bear = trend < -self.strong_trend
        is_ranging = abs(trend) < self.weak_trend

        if is_bull:
            if is_volatile:
                return MarketRegime.BULL_VOLATILE
            else:
                return MarketRegime.BULL_STABLE
        elif is_bear:
            if is_volatile:
                return MarketRegime.BEAR_VOLATILE
            else:
                return MarketRegime.BEAR_STABLE
        elif is_ranging:
            return MarketRegime.RANGING
        else:
            return MarketRegime.TRANSITION

    def _calculate_confidence(self, volatility: float, trend: float) -> float:
        """Calculate confidence in regime classification."""
        # Higher confidence when metrics are clearly in one regime
        vol_confidence = min(abs(volatility - self.high_vol_threshold) / self.high_vol_threshold, 1.0)
        trend_confidence = min(abs(trend) / self.strong_trend, 1.0)

        return (vol_confidence + trend_confidence) / 2

    def get_regime_stats(self) -> Dict:
        """Get statistics about regime detections."""
        if not self.regime_history:
            return {}

        regime_counts = {}
        for state in self.regime_history:
            regime = state.regime.value
            regime_counts[regime] = regime_counts.get(regime, 0) + 1

        return {
            "current_regime": self.current_regime.regime.value if self.current_regime else None,
            "current_confidence": self.current_regime.confidence if self.current_regime else 0,
            "regime_counts": regime_counts,
            "total_detections": len(self.regime_history)
        }
