#!/usr/bin/env python3
"""
SLATE Regime-Aware Discovery System

CRITICAL ARCHITECTURE FIX: Stop testing May-optimized strategies in July conditions.

This system implements regime-aware discovery that:
1. Detects fundamental market regime changes (not just current regime)
2. Tracks historical strategy performance by regime
3. Stops testing strategies from old regimes when regime fundamentally changes
4. Implements adaptive strategy generation for current conditions

Problem Solved: System was stuck testing May-optimized strategies for 2 months
with 0% success because market conditions fundamentally changed.

Author: SLATE Architecture Fix
Date: 2026-07-01
Priority: CRITICAL - Fixes 2-month discovery crisis
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)


class RegimeTransition(Enum):
    """Types of regime transitions."""
    TREND_TO_RANGE = "trend_to_range"
    RANGE_TO_TREND = "range_to_trend"
    VOLATILITY_SPIKE = "volatility_spike"
    VOLATILITY_CRUSH = "volatility_crush"
    FUNDAMENTAL_SHIFT = "fundamental_shift"
    MINOR_ADJUSTMENT = "minor_adjustment"


@dataclass
class RegimeState:
    """Detailed market regime state."""
    regime_type: str
    trend_direction: str  # 'up', 'down', 'sideways'
    volatility_level: str  # 'low', 'medium', 'high'
    volume_characteristics: str
    price_momentum: float
    volatility_ratio: float  # current / historical
    confidence: float
    timestamp: datetime
    duration_hours: float = 0.0

    def is_similar_to(self, other: 'RegimeState', threshold: float = 0.3) -> bool:
        """Check if two regimes are similar enough for strategy reuse."""
        similarity_score = 0.0

        # Trend direction match
        if self.trend_direction == other.trend_direction:
            similarity_score += 0.3

        # Volatility level match
        if self.volatility_level == other.volatility_level:
            similarity_score += 0.3

        # Momentum similarity
        momentum_diff = abs(self.price_momentum - other.price_momentum)
        if momentum_diff < 0.02:  # 2% threshold
            similarity_score += 0.2

        # Volatility ratio similarity
        vol_ratio_diff = abs(self.volatility_ratio - other.volatility_ratio)
        if vol_ratio_diff < 0.3:  # 30% threshold
            similarity_score += 0.2

        return similarity_score >= (1.0 - threshold)


@dataclass
class HistoricalRegimePerformance:
    """Performance tracking of strategies by regime."""
    regime_signature: str
    strategy_count: int
    profitable_count: int
    success_rate: float
    avg_return: float
    avg_sharpe: float
    discovered_during: List[datetime]
    last_tested: datetime

    def is_stale(self, current_regime: RegimeState, max_age_hours: float = 24.0) -> bool:
        """Check if performance data is too old for current regime."""
        # If regime has fundamentally changed, data is stale
        hours_since_last_test = (datetime.now() - self.last_tested).total_seconds() / 3600
        return hours_since_last_test > max_age_hours


class RegimeAwareDiscoveryManager:
    """
    Manages regime-aware strategy discovery to prevent testing outdated strategies.

    Core Innovation: Historical awareness + Regime change detection
    """

    def __init__(self):
        self.regime_history: List[RegimeState] = []
        self.regime_transitions: List[Tuple[datetime, RegimeTransition]] = []

        # Track strategy performance by regime signature
        self.regime_performance: Dict[str, HistoricalRegimePerformance] = {}

        # Current regime state
        self.current_regime: Optional[RegimeState] = None
        self.last_regime_change: datetime = datetime.now()

        # Configuration
        self.regime_similarity_threshold = 0.3
        self.max_regime_age_hours = 48.0  # Consider data stale after 48 hours
        self.min_regime_duration_hours = 4.0  # Minimum regime change duration

        # Import market regime detector for sophisticated analysis
        from .market_regime_detector import MarketRegimeDetector
        self.market_regime_detector = MarketRegimeDetector()

        logger.info("RegimeAwareDiscoveryManager initialized")

    async def detect_regime_transition(self, market_data: pd.DataFrame) -> Tuple[RegimeState, Optional[RegimeTransition]]:
        """
        Detect current regime and identify if transition occurred.

        Returns:
            Tuple of (current_regime, transition_type)
        """
        # Use sophisticated market regime detector
        try:
            # Convert market data to format expected by detector
            prices = market_data['close']
            volume = market_data['volume']
            returns = prices.pct_change().dropna()

            # Detect regime using sophisticated detector
            regime_result = await self.market_regime_detector.detect_market_regime(
                symbol="BTCUSDT",  # Default to BTC for regime detection
                prices=prices,
                volume=volume,
                returns=returns
            )

            # Create detailed regime state
            current_regime = RegimeState(
                regime_type=regime_result.regime.value,
                trend_direction=self._extract_trend_direction(regime_result),
                volatility_level=self._extract_volatility_level(regime_result),
                volume_characteristics="normal",
                price_momentum=self._calculate_momentum(prices),
                volatility_ratio=self._calculate_volatility_ratio(returns),
                confidence=regime_result.confidence,
                timestamp=datetime.now(),
                duration_hours=0.0
            )

        except Exception as e:
            logger.warning(f"Sophisticated regime detection failed: {e}, using basic detection")
            current_regime = self._basic_regime_detection(market_data)

        # Detect regime transition
        transition = None
        if self.current_regime is not None:
            transition = self._detect_transition_type(self.current_regime, current_regime)

            # If significant transition detected, record it
            if transition and transition != RegimeTransition.MINOR_ADJUSTMENT:
                self.regime_transitions.append((datetime.now(), transition))
                logger.warning(f"🚨 REGIME TRANSITION DETECTED: {transition.value}")

                # Clear stale performance data for fundamental shifts
                if transition in [RegimeTransition.FUNDAMENTAL_SHIFT,
                                RegimeTransition.TREND_TO_RANGE,
                                RegimeTransition.RANGE_TO_TREND]:
                    await self._clear_stale_performance_data(current_regime)

        # Update regime history
        self.regime_history.append(current_regime)

        # Calculate regime duration
        if len(self.regime_history) > 1:
            duration = (current_regime.timestamp - self.regime_history[-2].timestamp).total_seconds() / 3600
            current_regime.duration_hours = duration

        self.current_regime = current_regime
        self.last_regime_change = datetime.now()

        return current_regime, transition

    def _extract_trend_direction(self, regime_result) -> str:
        """Extract trend direction from regime result."""
        regime_str = regime_result.regime.value
        if 'trending_up' in regime_str or 'trend' in regime_str and 'up' in regime_str:
            return 'up'
        elif 'trending_down' in regime_str or 'trend' in regime_str and 'down' in regime_str:
            return 'down'
        else:
            return 'sideways'

    def _extract_volatility_level(self, regime_result) -> str:
        """Extract volatility level from regime result."""
        regime_str = regime_result.regime.value
        if 'high_volatility' in regime_str:
            return 'high'
        elif 'low_volatility' in regime_str:
            return 'low'
        else:
            return 'medium'

    def _calculate_momentum(self, prices: pd.Series) -> float:
        """Calculate current price momentum."""
        if len(prices) < 20:
            return 0.0
        return (prices.iloc[-1] - prices.iloc[-20]) / prices.iloc[-20]

    def _calculate_volatility_ratio(self, returns: pd.Series) -> float:
        """Calculate volatility ratio (current / historical)."""
        if len(returns) < 50:
            return 1.0
        current_vol = returns.tail(20).std()
        historical_vol = returns.tail(50).std()
        return current_vol / historical_vol if historical_vol > 0 else 1.0

    def _basic_regime_detection(self, market_data: pd.DataFrame) -> RegimeState:
        """Basic regime detection if sophisticated detector fails."""
        prices = market_data['close']
        returns = prices.pct_change().dropna()

        # Simple trend detection
        momentum = self._calculate_momentum(prices)
        if momentum > 0.02:
            trend_direction = 'up'
        elif momentum < -0.02:
            trend_direction = 'down'
        else:
            trend_direction = 'sideways'

        # Simple volatility detection
        volatility_ratio = self._calculate_volatility_ratio(returns)
        if volatility_ratio > 1.5:
            vol_level = 'high'
        elif volatility_ratio < 0.7:
            vol_level = 'low'
        else:
            vol_level = 'medium'

        return RegimeState(
            regime_type=f"{trend_direction}_{vol_level}",
            trend_direction=trend_direction,
            volatility_level=vol_level,
            volume_characteristics="normal",
            price_momentum=momentum,
            volatility_ratio=volatility_ratio,
            confidence=0.7,
            timestamp=datetime.now()
        )

    def _detect_transition_type(self, old_regime: RegimeState, new_regime: RegimeState) -> Optional[RegimeTransition]:
        """Detect type of regime transition."""
        # Check if regimes are similar
        if old_regime.is_similar_to(new_regime, self.regime_similarity_threshold):
            return RegimeTransition.MINOR_ADJUSTMENT

        # Detect significant transitions
        transitions = []

        # Trend changes
        if old_regime.trend_direction != new_regime.trend_direction:
            if old_regime.trend_direction in ['up', 'down'] and new_regime.trend_direction == 'sideways':
                transitions.append(RegimeTransition.TREND_TO_RANGE)
            elif old_regime.trend_direction == 'sideways' and new_regime.trend_direction in ['up', 'down']:
                transitions.append(RegimeTransition.RANGE_TO_TREND)

        # Volatility changes
        if old_regime.volatility_level != new_regime.volatility_level:
            vol_diff = abs(new_regime.volatility_ratio - old_regime.volatility_ratio)
            if vol_diff > 0.5:  # Significant volatility change
                if new_regime.volatility_ratio > old_regime.volatility_ratio:
                    transitions.append(RegimeTransition.VOLATILITY_SPIKE)
                else:
                    transitions.append(RegimeTransition.VOLATILITY_CRUSH)

        # If multiple significant changes, it's a fundamental shift
        if len(transitions) >= 2:
            return RegimeTransition.FUNDAMENTAL_SHIFT
        elif len(transitions) == 1:
            return transitions[0]
        else:
            # Significant change but not captured above
            return RegimeTransition.FUNDAMENTAL_SHIFT

    async def _clear_stale_performance_data(self, new_regime: RegimeState):
        """Clear performance data that's no longer relevant due to regime change."""
        regimes_to_remove = []

        for regime_signature, performance_data in self.regime_performance.items():
            # Check if performance data is from a fundamentally different regime
            # This would require comparing regime signatures - for now, use time-based
            if performance_data.is_stale(new_regime, self.max_regime_age_hours):
                regimes_to_remove.append(regime_signature)

        for regime_sig in regimes_to_remove:
            del self.regime_performance[regime_sig]
            logger.info(f"🗑️  Cleared stale performance data for regime: {regime_sig}")

    def should_test_strategy(self, strategy_params: Dict, origin_regime: Optional[RegimeState] = None) -> Tuple[bool, str]:
        """
        Determine if a strategy should be tested based on current regime.

        This is the CRITICAL method that prevents testing May strategies in July.

        Args:
            strategy_params: Strategy parameters to test
            origin_regime: Regime when this strategy was first discovered/optimized

        Returns:
            Tuple of (should_test, reason)
        """
        if self.current_regime is None:
            return True, "No regime data available, allowing test"

        # If no origin regime specified, assume it's for current regime
        if origin_regime is None:
            return True, "New strategy for current regime"

        # Check if origin regime is similar to current regime
        if origin_regime.is_similar_to(self.current_regime, self.regime_similarity_threshold):
            return True, "Regime similar to origin, allowing test"

        # Check how recently this strategy type was successful
        regime_signature = self._generate_regime_signature(origin_regime)
        if regime_signature in self.regime_performance:
            performance_data = self.regime_performance[regime_signature]

            # If performance data is recent and good, allow testing
            if not performance_data.is_stale(self.current_regime, self.max_regime_age_hours):
                if performance_data.success_rate > 0.02:  # 2% success threshold
                    return True, f"Recent success in similar regime ({performance_data.success_rate:.1%})"
                else:
                    return False, f"Recent poor performance in similar regime ({performance_data.success_rate:.1%})"

        # Regimes are different and no recent success - prevent testing
        return False, f"Regime mismatch: {origin_regime.regime_type} != {self.current_regime.regime_type}"

    def _generate_regime_signature(self, regime: RegimeState) -> str:
        """Generate unique signature for regime."""
        return f"{regime.trend_direction}_{regime.volatility_level}_{regime.regime_type}"

    async def record_strategy_performance(self, strategy_params: Dict, result: Dict, regime_context: RegimeState):
        """Record strategy performance for regime-aware learning."""
        regime_signature = self._generate_regime_signature(regime_context)

        if regime_signature not in self.regime_performance:
            self.regime_performance[regime_signature] = HistoricalRegimePerformance(
                regime_signature=regime_signature,
                strategy_count=0,
                profitable_count=0,
                success_rate=0.0,
                avg_return=0.0,
                avg_sharpe=0.0,
                discovered_during=[],
                last_tested=datetime.now()
            )

        # Update performance data
        perf_data = self.regime_performance[regime_signature]
        perf_data.strategy_count += 1
        perf_data.last_tested = datetime.now()

        if result.get('total_return_pct', 0) > 0:
            perf_data.profitable_count += 1

        # Recalculate averages
        perf_data.success_rate = perf_data.profitable_count / perf_data.strategy_count
        perf_data.avg_return = perf_data.avg_return * 0.9 + result.get('total_return_pct', 0) * 0.1

        logger.debug(f"Recorded performance for {regime_signature}: {perf_data.success_rate:.1%} success")

    def get_regime_report(self) -> str:
        """Generate comprehensive regime analysis report."""
        if not self.current_regime:
            return "No regime data available"

        report = f"""
╔════════════════════════════════════════════════════════════════╗
║              🧠 REGIME-AWARE DISCOVERY REPORT                   ║
╚════════════════════════════════════════════════════════════════╝

📊 CURRENT REGIME ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Regime Type:        {self.current_regime.regime_type}
Trend Direction:     {self.current_regime.trend_direction}
Volatility Level:    {self.current_regime.volatility_level}
Price Momentum:      {self.current_regime.price_momentum:.2%}
Volatility Ratio:    {self.current_regime.volatility_ratio:.2f}x historical
Confidence:          {self.current_regime.confidence:.1%}
Duration:            {self.current_regime.duration_hours:.1f} hours
Timestamp:           {self.current_regime.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

🔄 REGIME TRANSITION HISTORY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        if self.regime_transitions:
            for timestamp, transition in reversed(self.regime_transitions[-5:]):
                report += f"{timestamp.strftime('%Y-%m-%d %H:%M')}: {transition.value.upper()}\n"
        else:
            report += "No significant regime transitions detected recently\n"

        report += f"""
📈 HISTORICAL PERFORMANCE BY REGIME
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        if self.regime_performance:
            for regime_sig, perf_data in sorted(self.regime_performance.items(),
                                              key=lambda x: x[1].success_rate,
                                              reverse=True)[:5]:
                report += f"""
{regime_sig}:
  Strategies:    {perf_data.strategy_count}
  Success Rate:  {perf_data.success_rate:.2%}
  Avg Return:    {perf_data.avg_return:.2%}
  Last Tested:   {perf_data.last_tested.strftime('%Y-%m-%d %H:%M')}
"""
        else:
            report += "No historical performance data available\n"

        report += f"""
🎯 STRATEGY TESTING RECOMMENDATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        # Analyze if we should continue testing or pivot
        if self.current_regime.trend_direction == 'sideways' and self.current_regime.volatility_level == 'low':
            report += "⚠️  LOW VOLATILITY RANGE-BOUND REGIME DETECTED\n"
            report += "    Recommend: Focus on mean reversion, reduce trend following\n"
        elif self.current_regime.volatility_level == 'high':
            report += "⚠️  HIGH VOLATILITY REGIME DETECTED\n"
            report += "    Recommend: Reduce position sizes, wait for clarity\n"

        if len(self.regime_transitions) > 0:
            last_transition_time, last_transition = self.regime_transitions[-1]
            hours_since_transition = (datetime.now() - last_transition_time).total_seconds() / 3600
            if hours_since_transition < 24:
                report += f"🚨 RECENT REGIME TRANSITION ({hours_since_transition:.1f}h ago)\n"
                report += "    Recommend: Aggressive strategy adaptation required\n"

        return report

    async def get_adaptive_strategy_guidance(self) -> Dict[str, Any]:
        """Get guidance for adaptive strategy generation based on current regime."""
        if self.current_regime is None:
            return {"error": "No regime data available"}

        guidance = {
            'current_regime': self.current_regime.regime_type,
            'recommended_strategy_types': [],
            'parameter_adjustments': {},
            'testing_priority': 'normal',
            'innovation_level': 'moderate'
        }

        # Regime-specific guidance
        if self.current_regime.trend_direction == 'sideways':
            guidance['recommended_strategy_types'] = ['mean_reversion', 'range_trading', 'statistical_arbitrage']
            guidance['parameter_adjustments'] = {
                'position_size': 0.8,  # Reduce size in ranging markets
                'hold_time': 1.2,     # Hold longer for mean reversion
                'entry_threshold': 0.8  # Be more selective
            }
        elif self.current_regime.trend_direction == 'up':
            guidance['recommended_strategy_types'] = ['trend_following', 'momentum', 'breakout']
            guidance['parameter_adjustments'] = {
                'position_size': 1.2,  # Increase size in trends
                'hold_time': 0.8,     # Exit faster in momentum
                'entry_threshold': 1.2  # Be more aggressive
            }
        elif self.current_regime.trend_direction == 'down':
            guidance['recommended_strategy_types'] = ['mean_reversion', 'short_selling', 'volatility_plays']
            guidance['parameter_adjustments'] = {
                'position_size': 0.6,  # Reduce size in downtrends
                'hold_time': 0.6,     # Exit quickly
                'entry_threshold': 1.5  # Very selective
            }

        # Volatility adjustments
        if self.current_regime.volatility_level == 'high':
            guidance['parameter_adjustments']['position_size'] *= 0.7
            guidance['testing_priority'] = 'conservative'
            guidance['innovation_level'] = 'low'
        elif self.current_regime.volatility_level == 'low':
            guidance['parameter_adjustments']['position_size'] *= 1.1
            guidance['testing_priority'] = 'aggressive'
            guidance['innovation_level'] = 'high'

        return guidance


# Singleton instance
_regime_aware_manager: Optional[RegimeAwareDiscoveryManager] = None


def get_regime_aware_manager() -> RegimeAwareDiscoveryManager:
    """Get or create regime-aware discovery manager."""
    global _regime_aware_manager
    if _regime_aware_manager is None:
        _regime_aware_manager = RegimeAwareDiscoveryManager()
    return _regime_aware_manager