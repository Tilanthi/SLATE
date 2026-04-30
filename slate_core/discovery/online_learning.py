"""
SLATE Online Learning System

Real-time parameter adaptation based on recent performance:
- Performance tracking
- Parameter mutation
- Regime-aware adaptation
- Online optimization
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque
import numpy as np
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class PerformanceSnapshot:
    """Snapshot of strategy performance at a point in time."""
    timestamp: datetime
    strategy_id: str
    sharpe_ratio: float
    total_return: float
    win_rate: float
    max_drawdown: float
    recent_returns: List[float]
    market_regime: str
    parameters: Dict[str, Any]


class OnlineLearner:
    """Adapt strategy parameters in real-time based on performance."""

    def __init__(self, learning_rate: float = 0.01, performance_window: int = 100):
        self.learning_rate = learning_rate
        self.performance_window = performance_window

        # Performance tracking
        self.performance_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=performance_window))
        self.parameter_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

        # Adaptation settings
        self.min_sharpe_threshold = 0.5
        self.adaptation_frequency = 20  # Adapt every N trades
        self.max_adaptations_per_day = 10
        self.daily_adaptation_count = 0
        self.last_adaptation_date = None

        # Performance targets by regime
        self.regime_performance_targets: Dict[str, Dict[str, float]] = {
            'bull_volatile': {'sharpe': 2.0, 'win_rate': 0.55},
            'bull_stable': {'sharpe': 1.5, 'win_rate': 0.52},
            'bear_volatile': {'sharpe': 1.0, 'win_rate': 0.50},
            'bear_stable': {'sharpe': 1.2, 'win_rate': 0.50},
            'ranging': {'sharpe': 0.8, 'win_rate': 0.48}
        }

    async def should_adapt(self, strategy_id: str, current_performance: Dict[str, float],
                         market_regime: str) -> bool:
        """Determine if strategy parameters should be adapted."""
        # Check if we've hit adaptation frequency limit
        if self.daily_adaptation_count >= self.max_adaptations_per_day:
            return False

        # Check minimum performance window
        history = self.performance_history[strategy_id]
        if len(history) < 10:
            return False

        # Check if performance is below threshold
        current_sharpe = current_performance.get('sharpe_ratio', 0)
        if current_sharpe > self.min_sharpe_threshold:
            return False  # Performing well, no need to adapt

        # Check if recent performance is declining
        if len(history) >= 20:
            recent_avg = np.mean([h.sharpe_ratio for h in list(history)[-20:]])
            older_avg = np.mean([h.sharpe_ratio for h in list(history)[-40:-20]])

            if recent_avg < older_avg * 0.8:  # 20% decline
                logger.info(f"Strategy {strategy_id} performance declining, adapting parameters")
                return True

        # Check against regime-specific targets
        regime_target = self.regime_performance_targets.get(market_regime, {})
        target_sharpe = regime_target.get('sharpe', 0.5)

        if current_sharpe < target_sharpe * 0.7:  # 30% below target
            logger.info(f"Strategy {strategy_id} below regime target, adapting parameters")
            return True

        return False

    def adapt_parameters(self, strategy: Dict, recent_performance: Dict[str, float],
                       market_regime: str) -> Dict[str, Any]:
        """Adapt strategy parameters based on recent performance."""
        current_params = strategy.get('parameters', {}).copy()
        strategy_type = strategy.get('type', 'momentum')

        # Get recent returns
        recent_returns = recent_performance.get('recent_returns', [])
        if not recent_returns:
            return current_params

        # Calculate performance metrics
        avg_return = np.mean(recent_returns)
        return_std = np.std(recent_returns) if len(recent_returns) > 1 else 0.01
        sharpe_ratio = avg_return / (return_std + 1e-6)

        # Record parameter history
        strategy_id = strategy.get('id', 'unknown')
        self.parameter_history[strategy_id].append({
            'timestamp': datetime.now(),
            'parameters': current_params.copy(),
            'sharpe': sharpe_ratio
        })

        # Adapt based on strategy type and regime
        if strategy_type == 'momentum':
            adapted_params = self._adapt_momentum_parameters(current_params, sharpe_ratio, market_regime)
        elif strategy_type == 'mean_reversion':
            adapted_params = self._adapt_mean_reversion_parameters(current_params, sharpe_ratio, market_regime)
        elif strategy_type == 'breakout':
            adapted_params = self._adapt_breakout_parameters(current_params, sharpe_ratio, market_regime)
        elif strategy_type == 'trend_following':
            adapted_params = self._adapt_trend_following_parameters(current_params, sharpe_ratio, market_regime)
        else:
            # Default adaptation
            adapted_params = self._default_adaptation(current_params, sharpe_ratio, market_regime)

        # Increment adaptation counter
        self.daily_adaptation_count += 1

        logger.info(f"Adapted parameters for {strategy_type} strategy {strategy_id}: "
                   f"Sharpe {sharpe_ratio:.2f} -> adapted parameters")

        return adapted_params

    def _adapt_momentum_parameters(self, params: Dict, sharpe: float, regime: str) -> Dict:
        """Adapt momentum strategy parameters."""
        adapted = params.copy()

        # Adjust threshold based on performance
        current_threshold = params.get('threshold', 0.02)
        current_period = params.get('period', 20)

        if sharpe < 0:
            # Poor performance: make strategy more conservative
            adapted['threshold'] = current_threshold * 1.2  # Higher threshold = fewer signals

            # Adjust period based on regime
            if 'bull' in regime:
                # Bull market: shorter periods for faster response
                adapted['period'] = max(5, current_period - 5)
            elif 'bear' in regime:
                # Bear market: longer periods to avoid false signals
                adapted['period'] = min(50, current_period + 5)
        else:
            # Good performance: can be more aggressive
            adapted['threshold'] = current_threshold * 0.9

        return adapted

    def _adapt_mean_reversion_parameters(self, params: Dict, sharpe: float, regime: str) -> Dict:
        """Adapt mean reversion strategy parameters."""
        adapted = params.copy()

        current_period = params.get('period', 20)
        current_std_dev = params.get('std_dev', 2.0)

        if sharpe < 0:
            # Poor performance: adjust parameters
            if 'rang' in regime:
                # Ranging market: mean reversion should work well
                # Make it more sensitive
                adapted['std_dev'] = current_std_dev * 0.8
            else:
                # Trending market: mean reversion struggles
                # Make it less sensitive to avoid fighting the trend
                adapted['std_dev'] = current_std_dev * 1.2
                adapted['period'] = min(40, current_period + 10)

        return adapted

    def _adapt_breakout_parameters(self, params: Dict, sharpe: float, regime: str) -> Dict:
        """Adapt breakout strategy parameters."""
        adapted = params.copy()

        current_period = params.get('period', 20)

        if sharpe < 0:
            # Poor performance: adjust confirmation
            if adapted.get('confirmation', True):
                # Reduce false breakouts by removing confirmation
                adapted['confirmation'] = False
            else:
                # Increase period to avoid noise
                adapted['period'] = min(50, current_period + 10)
        else:
            # Good performance: can optimize for earlier entries
            adapted['period'] = max(10, current_period - 5)

        return adapted

    def _adapt_trend_following_parameters(self, params: Dict, sharpe: float, regime: str) -> Dict:
        """Adapt trend following parameters."""
        adapted = params.copy()

        fast_period = params.get('fast_period', 10)
        slow_period = params.get('slow_period', 20)

        if sharpe < 0:
            # Poor performance: adjust periods
            if 'bull' in regime:
                # Bull market: shorten fast period for quicker signals
                adapted['fast_period'] = max(5, fast_period - 3)
            elif 'bear' in regime:
                # Bear market: avoid whipsaws
                adapted['fast_period'] = min(15, fast_period + 5)
                adapted['slow_period'] = min(60, slow_period + 10)

        # Ensure fast < slow
        if adapted['fast_period'] >= adapted['slow_period']:
            adapted['slow_period'] = adapted['fast_period'] + 10

        return adapted

    def _default_adaptation(self, params: Dict, sharpe: float, regime: str) -> Dict:
        """Default parameter adaptation."""
        adapted = params.copy()

        # Mutate numeric parameters
        for key, value in adapted.items():
            if isinstance(value, (int, float)):
                # Adaptation magnitude based on performance
                adaptation_magnitude = 0.15 if sharpe < 0 else 0.05

                if sharpe < 0:
                    # Poor performance: larger mutations
                    mutation = np.random.uniform(1 - adaptation_magnitude, 1 + adaptation_magnitude)
                else:
                    # Good performance: smaller refinements
                    mutation = np.random.uniform(0.95, 1.05)

                if isinstance(value, int):
                    adapted[key] = max(1, int(value * mutation))
                else:
                    adapted[key] = value * mutation

        return adapted

    def record_performance(self, strategy_id: str, performance: Dict[str, float],
                          market_regime: str):
        """Record performance snapshot for learning."""
        snapshot = PerformanceSnapshot(
            timestamp=datetime.now(),
            strategy_id=strategy_id,
            sharpe_ratio=performance.get('sharpe_ratio', 0),
            total_return=performance.get('total_return', 0),
            win_rate=performance.get('win_rate', 0),
            max_drawdown=performance.get('max_drawdown', 0),
            recent_returns=performance.get('recent_returns', []),
            market_regime=market_regime,
            parameters=performance.get('parameters', {})
        )

        self.performance_history[strategy_id].append(snapshot)

    def get_performance_trend(self, strategy_id: str) -> Dict[str, float]:
        """Analyze performance trend for a strategy."""
        history = list(self.performance_history[strategy_id])

        if len(history) < 10:
            return {'trend': 'insufficient_data'}

        # Calculate trend
        recent_sharpes = [h.sharpe_ratio for h in history[-10:]]
        older_sharpes = [h.sharpe_ratio for h in history[-20:-10]] if len(history) >= 20 else []

        recent_avg = np.mean(recent_sharpes)
        overall_avg = np.mean([h.sharpe_ratio for h in history])

        trend_direction = 'stable'
        if older_sharpes:
            older_avg = np.mean(older_sharpes)
            if recent_avg > older_avg * 1.1:
                trend_direction = 'improving'
            elif recent_avg < older_avg * 0.9:
                trend_direction = 'declining'

        # Volatility of performance
        perf_volatility = np.std(recent_sharpes) if len(recent_sharpes) > 1 else 0

        return {
            'trend': trend_direction,
            'recent_avg': recent_avg,
            'overall_avg': overall_avg,
            'performance_volatility': perf_volatility,
            'sample_count': len(history)
        }

    def reset_daily_counters(self):
        """Reset daily adaptation counters."""
        self.daily_adaptation_count = 0
        self.last_adaptation_date = datetime.now()
        logger.info("Reset daily online learning counters")


class AdaptiveOptimizer:
    """Online optimizer that continuously improves strategy parameters."""

    def __init__(self):
        self.learner = OnlineLearner(learning_rate=0.02)
        self.last_optimization = None

    async def optimize_and_adapt(self, strategy: Dict,
                               recent_results: List[Dict[str, Any]],
                               market_regime: str) -> Optional[Dict]:
        """Optimize and adapt strategy based on recent results."""
        if not recent_results:
            return None

        # Calculate aggregate performance
        total_trades = sum(r.get('total_trades', 0) for r in recent_results)
        if total_trades < 10:
            return None  # Not enough data

        # Calculate performance metrics
        sharpe_ratios = [r.get('sharpe_ratio', 0) for r in recent_results]
        total_returns = [r.get('total_return', 0) for r in recent_results]
        win_rates = [r.get('win_rate', 0) for r in recent_results]

        aggregated_performance = {
            'sharpe_ratio': np.mean(sharpe_ratios),
            'total_return': np.mean(total_returns),
            'win_rate': np.mean(win_rates),
            'total_trades': total_trades,
            'recent_returns': []
        }

        # Extract recent returns
        for result in recent_results:
            aggregated_performance['recent_returns'].extend(
                result.get('trades', [])[-20:]
            )

        strategy_id = strategy.get('id', 'unknown')

        # Check if adaptation is needed
        should_adapt = await self.learner.should_adapt(
            strategy_id, aggregated_performance, market_regime
        )

        if should_adapt:
            adapted_params = self.learner.adapt_parameters(
                strategy, aggregated_performance, market_regime
            )

            # Update strategy with adapted parameters
            adapted_strategy = strategy.copy()
            adapted_strategy['parameters'] = adapted_params
            adapted_strategy['adaptation_count'] = strategy.get('adaptation_count', 0) + 1

            # Record performance
            self.learner.record_performance(
                strategy_id, aggregated_performance, market_regime
            )

            self.last_optimization = datetime.now()

            return adapted_strategy

        return None

    def get_learning_status(self) -> Dict[str, Any]:
        """Get status of online learning system."""
        return {
            'last_optimization': self.last_optimization.isoformat() if self.last_optimization else None,
            'tracked_strategies': len(self.learner.performance_history),
            'daily_adaptations': self.learner.daily_adaptation_count,
            'max_daily_adaptations': self.learner.max_adaptations_per_day
        }
