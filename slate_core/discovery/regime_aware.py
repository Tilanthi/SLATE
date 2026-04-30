"""
SLATE Regime-Aware Strategy Selection

Selects strategies based on current market regime to ensure
strategies are appropriate for current conditions.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from collections import defaultdict
from enum import Enum
import numpy as np
from datetime import datetime

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
class RegimeCharacteristics:
    """Characteristics of current market regime."""
    regime: MarketRegime
    trend_direction: str  # 'up', 'down', 'sideways'
    volatility_level: str  # 'low', 'medium', 'high'
    volume_level: str  # 'low', 'medium', 'high'
    confidence: float
    expected_duration_hours: float
    timestamp: str


class RegimeDetector:
    """Detect current market regime from price data."""

    def __init__(self):
        self.lookback_periods = {
            'short': 20,   # 20 candles
            'medium': 50,  # 50 candles
            'long': 100    # 100 candles
        }

    def detect_regime(self, data: List[Dict]) -> RegimeCharacteristics:
        """Detect current market regime from price data."""
        if len(data) < 100:
            return RegimeCharacteristics(
                regime=MarketRegime.TRANSITION,
                trend_direction='sideways',
                volatility_level='medium',
                volume_level='medium',
                confidence=0.0,
                expected_duration_hours=1.0,
                timestamp=datetime.now().isoformat()
            )

        # Calculate indicators
        trend = self._calculate_trend(data)
        volatility = self._calculate_volatility(data)
        volume_level = self._calculate_volume_level(data)

        # Determine regime
        regime = self._classify_regime(trend, volatility)

        # Calculate confidence
        confidence = self._calculate_confidence(data, regime)

        return RegimeCharacteristics(
            regime=regime,
            trend_direction=trend['direction'],
            volatility_level=volatility['level'],
            volume_level=volume_level,
            confidence=confidence,
            expected_duration_hours=self._estimate_duration(regime),
            timestamp=datetime.now().isoformat()
        )

    def _calculate_trend(self, data: List[Dict]) -> Dict[str, Any]:
        """Calculate trend direction and strength."""
        closes = [d['close'] for d in data[-50:]]

        # Simple linear regression to determine trend
        x = np.arange(len(closes))
        coeffs = np.polyfit(x, closes, 1)
        slope = coeffs[0]

        # Calculate R² for trend strength
        y_pred = np.polyval(coeffs, x)
        ss_res = np.sum((closes - y_pred) ** 2)
        ss_tot = np.sum((closes - np.mean(closes)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

        # Determine direction
        price_change = (closes[-1] - closes[0]) / closes[0]

        if price_change > 0.02:  # >2% up
            direction = 'up'
        elif price_change < -0.02:  # <2% down
            direction = 'down'
        else:
            direction = 'sideways'

        return {
            'direction': direction,
            'slope': slope,
            'strength': r_squared,
            'price_change': price_change
        }

    def _calculate_volatility(self, data: List[Dict]) -> Dict[str, Any]:
        """Calculate volatility level."""
        closes = [d['close'] for d in data[-50:]]

        returns = np.diff(closes) / closes[:-1]
        volatility = np.std(returns)

        # Normalize volatility (typical crypto volatility range)
        if volatility < 0.01:  # <1% per period
            level = 'low'
        elif volatility < 0.03:  # 1-3% per period
            level = 'medium'
        else:
            level = 'high'

        return {
            'level': level,
            'value': volatility
        }

    def _calculate_volume_level(self, data: List[Dict]) -> str:
        """Calculate volume level."""
        volumes = [d['volume'] for d in data[-50:]]

        avg_volume = np.mean(volumes)
        recent_volume = np.mean(volumes[-10:])

        if recent_volume > avg_volume * 1.2:
            return 'high'
        elif recent_volume < avg_volume * 0.8:
            return 'low'
        else:
            return 'medium'

    def _classify_regime(self, trend: Dict, volatility: Dict) -> MarketRegime:
        """Classify market regime from trend and volatility."""
        direction = trend['direction']
        vol_level = volatility['level']

        if direction == 'up':
            if vol_level == 'high':
                return MarketRegime.BULL_VOLATILE
            else:
                return MarketRegime.BULL_STABLE
        elif direction == 'down':
            if vol_level == 'high':
                return MarketRegime.BEAR_VOLATILE
            else:
                return MarketRegime.BEAR_STABLE
        else:
            return MarketRegime.RANGING

    def _calculate_confidence(self, data: List[Dict], regime: MarketRegime) -> float:
        """Calculate confidence in regime classification."""
        # Based on trend strength and volatility consistency
        closes = [d['close'] for d in data[-50:]]

        # Trend strength
        x = np.arange(len(closes))
        coeffs = np.polyfit(x, closes, 1)
        y_pred = np.polyval(coeffs, x)
        ss_res = np.sum((closes - y_pred) ** 2)
        ss_tot = np.sum((closes - np.mean(closes)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

        # Confidence increases with trend strength
        confidence = min(1.0, r_squared * 2)

        return confidence

    def _estimate_duration(self, regime: MarketRegime) -> float:
        """Estimate how long current regime will last."""
        # Historical average regime durations (in hours)
        durations = {
            MarketRegime.BULL_VOLATILE: 4.0,
            MarketRegime.BULL_STABLE: 12.0,
            MarketRegime.BEAR_VOLATILE: 6.0,
            MarketRegime.BEAR_STABLE: 8.0,
            MarketRegime.RANGING: 16.0,
            MarketRegime.TRANSITION: 2.0
        }

        return durations.get(regime, 6.0)


class RegimeAwareStrategySelector:
    """Select strategies based on current market regime."""

    def __init__(self):
        self.detector = RegimeDetector()

        # Strategy pools for each regime
        self.regime_strategy_pools = {
            MarketRegime.BULL_VOLATILE: ['breakout', 'momentum', 'trend_following'],
            MarketRegime.BULL_STABLE: ['trend_following', 'momentum', 'breakout'],
            MarketRegime.BEAR_VOLATILE: ['mean_reversion', 'statistical_arb', 'multi_timeframe'],
            MarketRegime.BEAR_STABLE: ['mean_reversion', 'statistical_arb'],
            MarketRegime.RANGING: ['mean_reversion', 'range_trading', 'statistical_arb'],
            MarketRegime.TRANSITION: ['cash', 'reduce_size', 'wait']  # Conservative
        }

        # Timeframe preferences by regime
        self.regime_timeframe_preferences = {
            MarketRegime.BULL_VOLATILE: ['1h', '2h', '4h'],  # Longer timeframes for volatility
            MarketRegime.BULL_STABLE: ['30m', '1h', '2h'],
            MarketRegime.BEAR_VOLATILE: ['2h', '4h'],  # Even longer in bear volatility
            MarketRegime.BEAR_STABLE: ['1h', '2h'],
            MarketRegime.RANGING: ['15m', '30m', '1h'],
            MarketRegime.TRANSITION: ['1h', '2h']  # Conservative timeframes
        }

        # Historical performance tracking by regime
        self.regime_performance: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

    async def select_strategies_for_regime(self, current_regime: RegimeCharacteristics,
                                           available_strategies: List[str]) -> List[str]:
        """Select appropriate strategies for current regime."""
        regime = current_regime.regime

        # Get strategy pool for this regime
        strategy_pool = self.regime_strategy_pools.get(regime, ['momentum', 'mean_reversion'])

        # Filter available strategies
        selected = [s for s in strategy_pool if s in available_strategies]

        # If no matches, use default pool
        if not selected:
            selected = ['momentum', 'mean_reversion', 'trend_following']
            logger.warning(f"No strategies available for {regime}, using defaults")

        logger.info(f"Regime {regime}: selected strategies {selected}")
        return selected

    def select_timeframe_for_regime(self, regime: MarketRegime) -> str:
        """Select appropriate timeframe for current regime."""
        timeframes = self.regime_timeframe_preferences.get(regime, ['1h'])

        # Weight toward longer timeframes for stability
        if len(timeframes) > 1:
            # Prefer longer timeframes (later in list)
            import random
            weights = list(range(1, len(timeframes) + 1))
            total_weight = sum(weights)
            norm_weights = [w / total_weight for w in weights]

            r = random.random()
            cumulative = 0.0
            for i, weight in enumerate(norm_weights):
                cumulative += weight
                if r <= cumulative:
                    return timeframes[i]

        return timeframes[-1] if timeframes else '1h'

    def update_regime_performance(self, regime: MarketRegime, strategy_type: str,
                                 sharpe_ratio: float):
        """Update historical performance tracking."""
        key = f"{regime.value}_{strategy_type}"

        # Exponential moving average of performance
        alpha = 0.1  # Learning rate
        current_avg = self.regime_performance[key]['avg_sharpe']
        new_avg = alpha * sharpe_ratio + (1 - alpha) * current_avg

        self.regime_performance[key]['avg_sharpe'] = new_avg
        self.regime_performance[key]['sample_count'] += 1

    def get_regime_performance_summary(self) -> Dict[str, Dict[str, float]]:
        """Get performance summary by regime and strategy type."""
        return dict(self.regime_performance)

    async def adapt_strategy_for_regime(self, strategy: Dict,
                                      regime: RegimeCharacteristics) -> Dict:
        """Adapt strategy parameters for current regime."""
        adapted = strategy.copy()
        params = adapted.get('parameters', {})

        # Adapt parameters based on regime
        if regime.regime == MarketRegime.BULL_VOLATILE:
            # Bull volatile: more sensitive to breakouts
            if adapted['type'] == 'breakout':
                params['period'] = max(5, params.get('period', 20) - 5)
                params['confirmation'] = False  # Faster entry
            elif adapted['type'] == 'momentum':
                params['threshold'] *= 0.8  # More sensitive

        elif regime.regime == MarketRegime.BEAR_VOLATILE:
            # Bear volatile: more conservative
            if adapted['type'] == 'mean_reversion':
                params['std_dev'] *= 0.8  # More sensitive to reversions
            elif adapted['type'] == 'momentum':
                params['threshold'] *= 1.5  # Less sensitive

        elif regime.regime == MarketRegime.RANGING:
            # Ranging: focus on mean reversion
            if adapted['type'] == 'mean_reversion':
                params['period'] = min(50, params.get('period', 20) + 10)

        adapted['parameters'] = params
        adapted['regime_adapted'] = True
        adapted['regime'] = regime.regime.value

        return adapted
