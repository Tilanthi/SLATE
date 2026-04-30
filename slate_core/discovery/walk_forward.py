"""
SLATE Walk-Forward Validation System

Implements walk-forward analysis to validate strategies across time
and prevent overfitting by ensuring strategies work in out-of-sample data.
"""

import asyncio
import logging
import random
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
import numpy as np
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardConfig:
    """Configuration for walk-forward validation."""
    train_periods: int = 3  # Number of periods to train on
    test_periods: int = 1   # Number of periods to test on
    min_data_points: int = 1000  # Minimum data points per period
    retrain_frequency: int = 1  # Retrain every N periods


@dataclass
class WalkForwardResult:
    """Results from walk-forward validation."""
    strategy_id: str
    strategy_name: str
    total_periods: int
    train_results: List[Dict[str, float]]
    test_results: List[Dict[str, float]]
    overall_metrics: Dict[str, float]
    stability_score: float
    overfitting_indicator: float
    robust_pass: bool
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class WalkForwardValidator:
    """Validate strategies across time to ensure robustness."""

    def __init__(self, config: WalkForwardConfig = None):
        self.config = config or WalkForwardConfig()

    def validate_walk_forward(self, strategy: Dict, data: List[Dict],
                            period_size: int = 10000) -> WalkForwardResult:
        """Perform walk-forward validation: train on past, test on future."""
        if len(data) < self.config.min_data_points * 2:
            logger.warning(f"Insufficient data for walk-forward: {len(data)} points")
            return self._create_failure_result(strategy, "insufficient_data")

        train_results = []
        test_results = []

        # Walk through data
        i = self.config.train_periods * period_size

        while i + self.config.test_periods * period_size <= len(data):
            # Training period
            train_start = i - self.config.train_periods * period_size
            train_end = i
            train_data = data[train_start:train_end]

            # Test period (out-of-sample)
            test_start = i
            test_end = i + self.config.test_periods * period_size
            test_data = data[test_start:test_end]

            # Optimize on training data
            best_params = self._optimize_strategy_parameters(strategy, train_data)

            # Test on out-of-sample data
            test_result = self._backtest_with_params(strategy, test_data, best_params)
            train_result = self._backtest_with_params(strategy, train_data, best_params)

            if test_result and train_result:
                test_results.append(test_result)
                train_results.append(train_result)

            i += self.config.test_periods * period_size

        if not test_results:
            return self._create_failure_result(strategy, "no_valid_results")

        # Calculate walk-forward metrics
        overall_metrics = self._calculate_walk_forward_metrics(train_results, test_results)
        stability_score = self._calculate_stability_score(test_results)
        overfitting_indicator = self._calculate_overfitting_indicator(train_results, test_results)

        # Determine if strategy passes walk-forward validation
        robust_pass = (
            stability_score > 0.5 and
            overfitting_indicator < 0.3 and
            overall_metrics['avg_test_sharpe'] > -10  # Reasonable performance
        )

        result = WalkForwardResult(
            strategy_id=strategy.get('id', 'unknown'),
            strategy_name=strategy.get('name', 'unknown'),
            total_periods=len(test_results),
            train_results=train_results,
            test_results=test_results,
            overall_metrics=overall_metrics,
            stability_score=stability_score,
            overfitting_indicator=overfitting_indicator,
            robust_pass=robust_pass
        )

        logger.info(f"Walk-forward validation for {strategy['name']}: "
                   f"Pass={robust_pass}, Stability={stability_score:.2f}, "
                   f"Overfitting={overfitting_indicator:.2f}")

        return result

    def _optimize_strategy_parameters(self, strategy: Dict, train_data: List[Dict]) -> Dict[str, Any]:
        """Optimize strategy parameters on training data."""
        base_params = strategy.get('parameters', {})
        strategy_type = strategy.get('type', 'momentum')

        if strategy_type == 'momentum':
            # Optimize period and threshold
            best_sharpe = -float('inf')
            best_params = base_params.copy()

            for period in range(10, 50, 5):
                for threshold in np.linspace(0.01, 0.10, 5):
                    test_params = {**base_params, 'period': period, 'threshold': threshold}
                    result = self._backtest_with_params(strategy, train_data, test_params)

                    if result and result.get('sharpe_ratio', -float('inf')) > best_sharpe:
                        best_sharpe = result['sharpe_ratio']
                        best_params = test_params

            return best_params

        elif strategy_type == 'mean_reversion':
            # Optimize period and std_dev
            best_sharpe = -float('inf')
            best_params = base_params.copy()

            for period in range(10, 40, 5):
                for std_dev in np.linspace(1.0, 3.0, 5):
                    test_params = {**base_params, 'period': period, 'std_dev': std_dev}
                    result = self._backtest_with_params(strategy, train_data, test_params)

                    if result and result.get('sharpe_ratio', -float('inf')) > best_sharpe:
                        best_sharpe = result['sharpe_ratio']
                        best_params = test_params

            return best_params

        else:
            # For other strategy types, return base params with small mutation
            return self._mutate_parameters(base_params)

    def _backtest_with_params(self, strategy: Dict, data: List[Dict],
                             params: Dict[str, Any]) -> Optional[Dict[str, float]]:
        """Backtest strategy with specific parameters."""
        try:
            from .realistic_backtester import RealisticBacktester

            backtester = RealisticBacktester()
            test_strategy = {**strategy, 'parameters': params}

            # Run quick backtest
            signals = backtester._generate_signals(test_strategy, data)

            if not signals or len(signals) < 100:
                return None

            # Calculate basic metrics
            returns = []
            positions = []
            entry_price = 0
            position = 0

            for i in range(1, len(signals)):
                if signals[i] != 0 and position == 0:
                    # Enter position
                    position = signals[i]
                    entry_price = data[i]['close']
                elif position != 0 and (signals[i] == -position or signals[i] == 0):
                    # Exit position
                    exit_price = data[i]['close']
                    if position > 0:
                        ret = (exit_price - entry_price) / entry_price
                    else:
                        ret = (entry_price - exit_price) / entry_price
                    returns.append(ret)
                    position = 0

            if len(returns) < 5:
                return None

            returns_array = np.array(returns)

            return {
                'sharpe_ratio': np.mean(returns_array) / (np.std(returns_array) + 1e-6) * np.sqrt(252),
                'total_return': np.sum(returns_array),
                'max_drawdown': self._calculate_max_drawdown(returns_array),
                'win_rate': sum(1 for r in returns if r > 0) / len(returns)
            }

        except Exception as e:
            logger.warning(f"Backtest failed: {e}")
            return None

    def _calculate_max_drawdown(self, returns: np.ndarray) -> float:
        """Calculate maximum drawdown from returns."""
        cumulative = np.cumprod(1 + np.array(returns))
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        return np.min(drawdown)

    def _calculate_walk_forward_metrics(self, train_results: List[Dict],
                                       test_results: List[Dict]) -> Dict[str, float]:
        """Calculate overall walk-forward performance metrics."""
        train_sharpes = [r.get('sharpe_ratio', 0) for r in train_results]
        test_sharpes = [r.get('sharpe_ratio', 0) for r in test_results]

        return {
            'avg_train_sharpe': np.mean(train_sharpes) if train_sharpes else 0,
            'avg_test_sharpe': np.mean(test_sharpes) if test_sharpes else 0,
            'std_test_sharpe': np.std(test_sharpes) if test_sharpes else 0,
            'best_test_sharpe': max(test_sharpes) if test_sharpes else 0,
            'worst_test_sharpe': min(test_sharpes) if test_sharpes else 0,
            'sharpe_decline': (train_sharpes[0] - test_sharpes[-1]) if train_sharpes and test_sharpes else 0
        }

    def _calculate_stability_score(self, test_results: List[Dict]) -> float:
        """Calculate how stable performance is across test periods."""
        if len(test_results) < 2:
            return 0.0

        test_sharpes = [r.get('sharpe_ratio', 0) for r in test_results]

        # Lower standard deviation = higher stability
        mean_sharpe = np.mean(test_sharpes)
        std_sharpe = np.std(test_sharpes)

        if mean_sharpe == 0:
            return 0.0

        # Coefficient of variation (normalized)
        cv = std_sharpe / (abs(mean_sharpe) + 1e-6)

        # Convert to stability score (lower CV = higher stability)
        stability = max(0, 1 - cv / 2)

        return stability

    def _calculate_overfitting_indicator(self, train_results: List[Dict],
                                       test_results: List[Dict]) -> float:
        """Calculate indicator of overfitting (train >> test performance)."""
        if not train_results or not test_results:
            return 0.0

        train_sharpes = [r.get('sharpe_ratio', 0) for r in train_results]
        test_sharpes = [r.get('sharpe_ratio', 0) for r in test_results]

        avg_train = np.mean(train_sharpes)
        avg_test = np.mean(test_sharpes)

        # Overfitting = train performance much better than test
        if avg_test <= 0:
            return 1.0  # Severe overfitting

        # Ratio of train/test performance
        overfitting_ratio = max(0, avg_train - avg_test) / (abs(avg_test) + 1e-6)

        return min(1.0, overfitting_ratio / 5)  # Normalize to 0-1

    def _mutate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Apply small mutation to parameters."""
        mutated = params.copy()

        for key, value in mutated.items():
            if isinstance(value, (int, float)):
                mutation = random.uniform(0.9, 1.1)
                if isinstance(value, int):
                    mutated[key] = max(1, int(value * mutation))
                else:
                    mutated[key] = value * mutation

        return mutated

    def _create_failure_result(self, strategy: Dict, reason: str) -> WalkForwardResult:
        """Create a failed walk-forward result."""
        return WalkForwardResult(
            strategy_id=strategy.get('id', 'unknown'),
            strategy_name=strategy.get('name', 'unknown'),
            total_periods=0,
            train_results=[],
            test_results=[],
            overall_metrics={'avg_test_sharpe': -999},
            stability_score=0.0,
            overfitting_indicator=1.0,
            robust_pass=False
        )


class AdaptiveWalkForward:
    """Adaptive walk-forward that adjusts parameters based on regime changes."""

    def __init__(self):
        self.validator = WalkForwardValidator()
        self.regime_history: List[Dict] = []

    async def validate_and_adapt(self, strategy: Dict, data: List[Dict],
                                current_regime: str) -> Tuple[WalkForwardResult, Optional[Dict]]:
        """Validate with walk-forward and adapt parameters if needed."""
        result = self.validator.validate_walk_forward(strategy, data)

        # Track regime performance
        self.regime_history.append({
            'regime': current_regime,
            'sharpe': result.overall_metrics.get('avg_test_sharpe', 0),
            'timestamp': datetime.now().isoformat()
        })

        # If failed validation, adapt parameters
        if not result.robust_pass:
            logger.info(f"Strategy {strategy['name']} failed walk-forward, adapting parameters")
            adapted_params = self._adapt_for_regime(strategy, current_regime)
            return result, adapted_params

        return result, None

    def _adapt_for_regime(self, strategy: Dict, regime: str) -> Dict[str, Any]:
        """Adapt strategy parameters for specific regime."""
        base_params = strategy.get('parameters', {})
        strategy_type = strategy.get('type', 'momentum')

        if 'bull' in regime.lower():
            # Bull market: favor momentum strategies
            if strategy_type == 'momentum':
                base_params['threshold'] *= 0.8  # More sensitive
                base_params['period'] = max(5, base_params.get('period', 20) - 5)
        elif 'bear' in regime.lower():
            # Bear market: favor mean reversion, shorter periods
            if strategy_type == 'mean_reversion':
                base_params['period'] = min(30, base_params.get('period', 20) + 5)
            elif strategy_type == 'momentum':
                base_params['threshold'] *= 1.2  # Less sensitive
        elif 'rang' in regime.lower():
            # Ranging market: mean reversion works well
            if strategy_type == 'mean_reversion':
                base_params['std_dev'] *= 0.9  # More sensitive

        return base_params
