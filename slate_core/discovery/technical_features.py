"""
SLATE Technical Feature Engineering

Advanced technical indicators for ML feature engineering:
- Momentum features
- Volatility features
- Volume features
- Market microstructure features
- Cycle features
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TechnicalFeatures:
    """Container for technical features."""
    # Momentum features
    roc_5: float = 0.0  # Rate of change 5 periods
    roc_10: float = 0.0
    roc_20: float = 0.0
    rsi_14: float = 0.0  # Relative Strength Index

    # Volatility features
    atr_ratio: float = 0.0
    volatility_regime: str = 'medium'  # 'low', 'medium', 'high'
    historical_volatility: float = 0.0
    realized_volatility: float = 0.0

    # Volume features
    volume_profile: str = 'normal'  # 'low', 'normal', 'high'
    obv_divergence: float = 0.0
    volume_momentum: float = 0.0

    # Market microstructure
    bid_ask_spread: float = 0.0
    order_flow_imbalance: float = 0.0
    price_impact: float = 0.0

    # Cycle features
    dominant_cycle: float = 0.0
    cycle_phase: float = 0.0  # 0-1, where 0 = cycle bottom, 0.5 = cycle top

    # Trend features
    trend_direction: str = 'neutral'  # 'up', 'down', 'neutral'
    trend_strength: float = 0.0  # 0-1, 1 = strongest trend

    # Support/Resistance
    support_level: float = 0.0
    resistance_level: float = 0.0
    distance_to_support: float = 0.0
    distance_to_resistance: float = 0.0


class FeatureEngineering:
    """Calculate advanced technical indicators for feature engineering."""

    def __init__(self):
        self.feature_cache: Dict[str, TechnicalFeatures] = {}

    def calculate_features(self, data: List[Dict], lookback: int = 50) -> TechnicalFeatures:
        """Calculate all technical features."""
        if len(data) < lookback:
            return TechnicalFeatures()

        closes = np.array([d['close'] for d in data[-lookback:]])
        highs = np.array([d['high'] for d in data[-lookback:]])
        lows = np.array([d['low'] for d in data[-lookback:]])
        volumes = np.array([d['volume'] for d in data[-lookback:]])

        features = TechnicalFeatures()

        # Momentum features
        features.roc_5 = self._rate_of_change(closes, 5)
        features.roc_10 = self._rate_of_change(closes, 10)
        features.roc_20 = self._rate_of_change(closes, 20)
        features.rsi_14 = self._rsi(closes)

        # Volatility features
        features.atr_ratio = self._atr_ratio(highs, lows, closes)
        features.volatility_regime = self._classify_volatility_regime(closes)
        features.historical_volatility = self._historical_volatility(closes)
        features.realized_volatility = self._realized_volatility(closes)

        # Volume features
        features.volume_profile = self._classify_volume_profile(volumes)
        features.obv_divergence = self._obv_divergence(closes, volumes)
        features.volume_momentum = self._volume_momentum(volumes)

        # Market microstructure (simplified)
        features.bid_ask_spread = self._estimate_spread(closes, volumes)
        features.order_flow_imbalance = self._estimate_order_flow_imbalance(closes, volumes)
        features.price_impact = self._estimate_price_impact(volumes)

        # Cycle features
        features.dominant_cycle = self._dominant_cycle(closes)
        features.cycle_phase = self._cycle_phase(closes)

        # Trend features
        features.trend_direction, features.trend_strength = self._trend_analysis(closes)

        # Support/Resistance
        features.support_level, features.resistance_level = self._support_resistance(closes, highs, lows)
        features.distance_to_support = (closes[-1] - features.support_level) / closes[-1]
        features.distance_to_resistance = (features.resistance_level - closes[-1]) / closes[-1]

        return features

    def _rate_of_change(self, prices: np.ndarray, period: int) -> float:
        """Calculate rate of change over period."""
        if len(prices) < period + 1:
            return 0.0

        return (prices[-1] - prices[-period - 1]) / prices[-period - 1]

    def _rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """Calculate Relative Strength Index."""
        if len(prices) < period + 1:
            return 50.0  # Neutral RSI

        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _atr_ratio(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> float:
        """Calculate ATR ratio (current ATR / average ATR)."""
        if len(highs) < 15:
            return 1.0

        # Calculate True Range
        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(
                abs(highs[1:] - closes[:-1]),
                abs(lows[1:] - closes[:-1])
            )
        )

        atr = np.mean(tr[-14:])  # 14-period ATR
        avg_atr = np.mean(tr)  # Average ATR

        if avg_atr == 0:
            return 1.0

        return atr / avg_atr

    def _classify_volatility_regime(self, prices: np.ndarray) -> str:
        """Classify volatility regime."""
        returns = np.diff(prices) / prices[:-1]
        volatility = np.std(returns)

        if volatility < 0.01:  # <1% per period
            return 'low'
        elif volatility < 0.03:  # 1-3% per period
            return 'medium'
        else:
            return 'high'

    def _historical_volatility(self, prices: np.ndarray) -> float:
        """Calculate historical volatility."""
        returns = np.diff(prices) / prices[:-1]
        return np.std(returns) * np.sqrt(252)  # Annualized

    def _realized_volatility(self, prices: np.ndarray) -> float:
        """Calculate realized volatility over lookback period."""
        returns = np.diff(prices) / prices[:-1]
        return np.std(returns)

    def _classify_volume_profile(self, volumes: np.ndarray) -> str:
        """Classify volume profile."""
        avg_volume = np.mean(volumes)
        recent_volume = np.mean(volumes[-10:])

        if recent_volume > avg_volume * 1.3:
            return 'high'
        elif recent_volume < avg_volume * 0.7:
            return 'low'
        else:
            return 'normal'

    def _obv_divergence(self, prices: np.ndarray, volumes: np.ndarray) -> float:
        """Calculate On-Balance Volume divergence."""
        # Simplified OBV
        obv = []
        for i in range(1, len(prices)):
            if prices[i] > prices[i-1]:
                obv.append(volumes[i])
            else:
                obv.append(-volumes[i])

        # Check if OBV diverges from price trend
        price_change = (prices[-1] - prices[0]) / prices[0]
        obv_change = (sum(obv[-10:]) - sum(obv[:10])) / (sum(obv[:10]) + 1)

        # Divergence: price up but OBV down (bearish) or vice versa (bullish)
        divergence = obv_change - price_change

        return divergence

    def _volume_momentum(self, volumes: np.ndarray) -> float:
        """Calculate volume momentum."""
        if len(volumes) < 10:
            return 0.0

        recent_avg = np.mean(volumes[-5:])
        older_avg = np.mean(volumes[-10:-5])

        if older_avg == 0:
            return 0.0

        return (recent_avg - older_avg) / older_avg

    def _estimate_spread(self, closes: np.ndarray, volumes: np.ndarray) -> float:
        """Estimate bid-ask spread based on volatility and volume."""
        returns = np.diff(closes) / closes[:-1]
        volatility = np.std(returns)

        # Spread increases with volatility, decreases with volume
        spread_bps = 5 + volatility * 1000 - np.mean(volumes) / 1e6

        return max(1, spread_bps) / 10000  # Convert to decimal

    def _estimate_order_flow_imbalance(self, closes: np.ndarray, volumes: np.ndarray) -> float:
        """Estimate order flow imbalance."""
        # Simplified: use price change vs volume relationship
        price_changes = np.diff(closes[-20:])
        volume_changes = np.diff(volumes[-20:])

        if len(volume_changes) == 0 or np.std(volume_changes) == 0:
            return 0.0

        # Correlation between price and volume changes
        if len(price_changes) > 0 and len(volume_changes) > 0:
            # Normalize both
            norm_prices = (price_changes - np.mean(price_changes)) / (np.std(price_changes) + 1e-6)
            norm_volumes = (volume_changes - np.mean(volume_changes)) / (np.std(volume_changes) + 1e-6)

            correlation = np.corrcoef(norm_prices, norm_volumes)[0, 1]

            if not np.isnan(correlation):
                return correlation

        return 0.0

    def _estimate_price_impact(self, volumes: np.ndarray) -> float:
        """Estimate price impact of trades."""
        # Simplified: larger volumes = higher impact
        avg_volume = np.mean(volumes)

        if avg_volume == 0:
            return 0.0

        # Impact increases with trade size relative to volume
        # Assume typical trade size is 1% of volume
        trade_size = avg_volume * 0.01

        # Linear impact model (rough approximation)
        impact = (trade_size / avg_volume) ** 0.5

        return impact

    def _dominant_cycle(self, prices: np.ndarray) -> float:
        """Estimate dominant market cycle using autocorrelation."""
        if len(prices) < 50:
            return 0.0

        # Calculate autocorrelations at different lags
        max_lag = min(20, len(prices) // 4)
        autocorrs = []

        for lag in range(2, max_lag + 1):
            # Calculate autocorrelation
            corr = np.corrcoef(prices[:-lag], prices[lag:])[0, 1]
            if not np.isnan(corr):
                autocorrs.append((lag, abs(corr)))

        if not autocorrs:
            return 0.0

        # Find lag with maximum autocorrelation
        best_lag, best_corr = max(autocorrs, key=lambda x: x[1])

        return best_lag if best_corr > 0.3 else 0.0

    def _cycle_phase(self, prices: np.ndarray) -> float:
        """Estimate phase in market cycle (0 = bottom, 1 = top)."""
        if len(prices) < 20:
            return 0.5

        # Use simple momentum to estimate phase
        recent_returns = np.diff(prices[-20:]) / prices[-21:-1]

        # Strong positive momentum = near top
        # Strong negative momentum = near bottom
        avg_momentum = np.mean(recent_returns)

        # Normalize to 0-1 range
        # Assuming typical range of +/- 5% per period
        phase = (avg_momentum + 0.05) / 0.1

        return max(0.0, min(1.0, phase))

    def _trend_analysis(self, prices: np.ndarray) -> tuple:
        """Analyze trend direction and strength."""
        # Linear regression
        x = np.arange(len(prices))
        coeffs = np.polyfit(x, prices, 1)

        # Calculate R² for trend strength
        y_pred = np.polyval(coeffs, x)
        ss_res = np.sum((prices - y_pred) ** 2)
        ss_tot = np.sum((prices - np.mean(prices)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

        # Determine direction
        price_change = (prices[-1] - prices[0]) / prices[0]

        if price_change > 0.02:  # >2% up
            direction = 'up'
        elif price_change < -0.02:  # <2% down
            direction = 'down'
        else:
            direction = 'neutral'

        return direction, r_squared

    def _support_resistance(self, prices: np.ndarray, highs: np.ndarray,
                          lows: np.ndarray) -> tuple:
        """Calculate support and resistance levels."""
        if len(prices) < 20:
            return prices[-1] * 0.95, prices[-1] * 1.05

        # Support: recent local minima
        local_mins = []
        for i in range(2, len(lows) - 2):
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
               lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                local_mins.append(lows[i])

        support = max(local_mins) if local_mins else np.min(lows[-20:]) * 0.98

        # Resistance: recent local maxima
        local_maxs = []
        for i in range(2, len(highs) - 2):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
               highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                local_maxs.append(highs[i])

        resistance = min(local_maxs) if local_maxs else np.max(highs[-20:]) * 1.02

        return support, resistance


class FeatureSelector:
    """Select most relevant features for strategy learning."""

    def __init__(self):
        self.feature_importance: Dict[str, float] = {}

    def select_features(self, features: TechnicalFeatures,
                       strategy_type: str) -> Dict[str, float]:
        """Select most relevant features for given strategy type."""
        # Feature importance by strategy type
        importance_map = {
            'momentum': ['roc_5', 'roc_10', 'roc_20', 'trend_strength', 'cycle_phase'],
            'mean_reversion': ['rsi_14', 'atr_ratio', 'distance_to_support', 'distance_to_resistance'],
            'breakout': ['atr_ratio', 'volatility_regime', 'volume_momentum', 'trend_strength'],
            'trend_following': ['trend_direction', 'trend_strength', 'dominant_cycle', 'cycle_phase'],
            'statistical_arb': ['realized_volatility', 'bid_ask_spread', 'order_flow_imbalance']
        }

        important_fields = importance_map.get(strategy_type, ['roc_10', 'trend_strength'])

        selected = {}
        for field in important_fields:
            value = getattr(features, field, 0.0)
            if isinstance(value, str):
                # Convert categorical to numeric
                if field == 'trend_direction':
                    value = {'up': 1.0, 'down': -1.0, 'neutral': 0.0}.get(value, 0.0)
                elif field == 'volatility_regime':
                    value = {'low': 0.0, 'medium': 0.5, 'high': 1.0}.get(value, 0.5)
                elif field == 'volume_profile':
                    value = {'low': 0.0, 'normal': 0.5, 'high': 1.0}.get(value, 0.5)

            selected[field] = value

        return selected

    def normalize_features(self, features: Dict[str, float]) -> Dict[str, float]:
        """Normalize features to 0-1 range."""
        if not features:
            return {}

        normalized = {}
        for key, value in features.items():
            # Assume reasonable ranges for each feature type
            if 'roc' in key:  # Rate of change
                normalized[key] = max(0.0, min(1.0, (value + 0.1) / 0.2))  # -10% to +10%
            elif 'sharpe' in key or 'strength' in key or 'phase' in key:
                normalized[key] = max(0.0, min(1.0, (value + 1) / 2))  # -1 to +1
            elif 'rsi' in key:
                normalized[key] = value / 100.0  # 0-100 to 0-1
            elif 'distance' in key:
                normalized[key] = max(0.0, min(1.0, abs(value)))  # Distance ratio
            else:
                normalized[key] = max(0.0, min(1.0, value))

        return normalized
