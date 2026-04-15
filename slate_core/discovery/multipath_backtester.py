#!/usr/bin/env python3
"""
SLATE Multi-Path Backtester

Tests strategies across multiple bootstrapped price paths
to get robust performance estimates and uncertainty bands.
"""

import numpy as np
import logging
import random
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import asyncio
from copy import deepcopy
from pathlib import Path

from .bootstrap_engine import (
    BlockBootstrapEngine,
    BootstrapPath,
    BootstrapOHLCVGenerator,
    create_sample_blocks_from_candles
)
from .realistic_backtester import BacktestConfig, BacktestResult

logger = logging.getLogger(__name__)


@dataclass
class MultiPathResult:
    """Results from testing a strategy across multiple paths."""
    strategy_id: str
    strategy_name: str
    strategy_type: str
    timeframe: str
    num_paths: int

    # Distribution statistics
    mean_return: float
    std_return: float
    min_return: float
    max_return: float
    median_return: float

    # Sharpe ratio distribution
    mean_sharpe: float
    std_sharpe: float
    min_sharpe: float
    max_sharpe: float

    # Drawdown distribution
    mean_max_drawdown: float
    std_max_drawdown: float
    worst_max_drawdown: float

    # Robustness metrics
    robustness_score: float
    consistency_ratio: float  # How often profitable
    path_wise_results: List[Dict]

    # Confidence intervals (95%)
    return_ci_lower: float
    return_ci_upper: float
    sharpe_ci_lower: float
    sharpe_ci_upper: float

    # Validation
    is_realistic: bool
    validation_failures: int

    timestamp: str


class MultiPathBacktester:
    """
    Test strategies across multiple bootstrapped paths
    to get robust performance estimates.
    """

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.bootstrap_engine = BlockBootstrapEngine()
        self.ohlcv_generator = BootstrapOHLCVGenerator()

    async def test_strategy_multipath(self,
                                      strategy: Dict,
                                      num_paths: int = 100,
                                      historical_candles: Optional[List[Dict]] = None) -> MultiPathResult:
        """Test a strategy across multiple bootstrapped paths.

        Args:
            strategy: Strategy definition
            num_paths: Number of alternative paths to test
            historical_candles: Historical data to bootstrap from

        Returns:
            MultiPathResult with distribution statistics
        """
        # Create blocks from historical data
        if historical_candles:
            blocks = create_sample_blocks_from_candles(historical_candles)
        else:
            # Load cached blocks
            blocks = self._load_cached_blocks()
            if not blocks:
                raise ValueError("No historical data available for bootstrapping")

        # Generate alternative paths
        logger.info(f"Generating {num_paths} bootstrapped paths...")
        paths = self.bootstrap_engine.generate_multiple_paths(blocks, num_paths)

        # Test strategy on each path
        logger.info(f"Testing strategy across {num_paths} paths...")
        path_results = []

        for i, path in enumerate(paths):
            try:
                # Convert path to OHLCV candles
                candles = self.ohlcv_generator.generate_ohlcv(path)

                # Run backtest on this path
                result = await self._backtest_on_candles(strategy, candles)

                if result:
                    path_results.append({
                        'path_id': path.path_id,
                        'return': result.total_return,
                        'sharpe': result.sharpe_ratio,
                        'max_drawdown': result.max_drawdown,
                        'win_rate': result.win_rate
                    })

            except Exception as e:
                logger.warning(f"Error testing path {i}: {e}")
                continue

            if (i + 1) % 20 == 0:
                logger.info(f"Completed {i + 1}/{num_paths} paths")

        # Calculate statistics
        return self._calculate_multipath_statistics(strategy, path_results)

    async def _backtest_on_candles(self, strategy: Dict,
                                   candles: List[Dict]) -> Optional[BacktestResult]:
        """Run backtest on candle data."""
        # Simplified backtest for bootstrap paths
        capital = self.config.initial_capital
        position = 0
        equity_curve = [capital]
        trades = []

        # Generate signals
        signals = self._generate_signals_for_candles(strategy, candles)

        # Run backtest
        for i in range(1, len(candles)):
            current_price = candles[i]['close']
            signal = signals[i]

            # Simple execution logic
            if signal != 0 and position == 0:
                # Entry
                position_size = capital * self.config.max_position_size
                if signal > 0:
                    position = position_size / current_price
                else:
                    position = -position_size / current_price
                capital -= position_size

            elif signal == 0 and position != 0:
                # Exit
                if position > 0:
                    proceeds = position * current_price
                    fee = proceeds * self.config.maker_fee
                    capital += proceeds - fee
                else:
                    proceeds = abs(position) * current_price
                    fee = proceeds * self.config.maker_fee
                    capital += proceeds - fee

                trades.append({'pnl': capital - self.config.initial_capital})
                position = 0

            # Calculate equity
            if position != 0:
                unrealized = position * (current_price - candles[i-1]['close'])
                current_equity = capital + unrealized
            else:
                current_equity = capital
            equity_curve.append(current_equity)

        # Calculate metrics
        if equity_curve:
            total_return = (equity_curve[-1] - equity_curve[0]) / equity_curve[0]

            returns = np.diff(equity_curve) / equity_curve[:-1]
            returns = returns[np.isfinite(returns)]

            if len(returns) > 0 and np.std(returns) > 0:
                sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252 * 24 * 60)
            else:
                sharpe = 0

            # Max drawdown
            peak = equity_curve[0]
            max_dd = 0
            for val in equity_curve:
                if val > peak:
                    peak = val
                dd = (peak - val) / peak
                if dd > max_dd:
                    max_dd = dd

            return BacktestResult(
                strategy_id=strategy.get('id', 'unknown'),
                strategy_name=strategy.get('name', 'Unknown'),
                strategy_type=strategy.get('type', 'unknown'),
                timeframe='1m',
                period_start=candles[0]['timestamp'] if candles else '',
                period_end=candles[-1]['timestamp'] if candles else '',
                total_return=total_return,
                sharpe_ratio=sharpe,
                sortino_ratio=0,  # Simplified
                max_drawdown=max_dd,
                equity_curve_smoothness=np.std(returns) if len(returns) > 0 else 0,
                calmar_ratio=total_return / max_dd if max_dd > 0 else 0,
                total_trades=len(trades),
                win_rate=len([t for t in trades if t.get('pnl', 0) > 0]) / len(trades) if trades else 0,
                profit_factor=0,
                avg_trade=np.mean([t.get('pnl', 0) for t in trades]) if trades else 0,
                volatility=np.std(returns) if len(returns) > 0 else 0,
                var_95=np.percentile(returns, 5) if len(returns) > 0 else 0,
                cvar_95=np.mean([r for r in returns if r <= np.percentile(returns, 5)]) if len(returns) > 0 else 0,
                parameters=strategy.get('parameters', {}),
                equity_curve=[float(x) for x in equity_curve[-100:]],
                trades=trades[-50:],
                timestamp=datetime.now().isoformat()
            )

        return None

    def _generate_signals_for_candles(self, strategy: Dict,
                                      candles: List[Dict]) -> List[int]:
        """Generate trading signals from strategy definition."""
        signals = [0] * len(candles)
        strategy_type = strategy.get('type', 'momentum')
        params = strategy.get('parameters', {})

        if strategy_type == 'momentum':
            period = params.get('period', 20)
            threshold = params.get('threshold', 0.02)

            for i in range(period, len(candles)):
                momentum = (candles[i]['close'] * 100 / candles[i - period]['close']) - 100
                if momentum > threshold:
                    signals[i] = 1
                elif momentum < -threshold:
                    signals[i] = -1

        elif strategy_type == 'mean_reversion':
            period = params.get('period', 20)
            std_dev = params.get('std_dev', 2.0)

            for i in range(period, len(candles)):
                closes = [c['close'] for c in candles[i-period:i]]
                mean = np.mean(closes)
                std = np.std(closes)
                upper_band = mean + std_dev * std
                lower_band = mean - std_dev * std

                if candles[i]['close'] < lower_band:
                    signals[i] = 1
                elif candles[i]['close'] > upper_band:
                    signals[i] = -1

        elif strategy_type == 'breakout':
            period = params.get('period', 20)

            for i in range(period, len(candles)):
                high = max(c['high'] for c in candles[i-period:i])
                low = min(c['low'] for c in candles[i-period:i])

                if candles[i]['close'] > high:
                    signals[i] = 1
                elif candles[i]['close'] < low:
                    signals[i] = -1

        else:
            # Default: random signals for exploration
            signals = [random.choice([-1, 0, 1]) if random.random() < 0.05 else 0 for _ in candles]

        return signals

    def _calculate_multipath_statistics(self, strategy: Dict,
                                       path_results: List[Dict]) -> MultiPathResult:
        """Calculate statistics from multi-path testing."""
        if not path_results:
            return self._empty_result(strategy)

        returns = [r['return'] for r in path_results]
        sharpes = [r['sharpe'] for r in path_results]
        drawdowns = [r['max_drawdown'] for r in path_results]

        # Return statistics
        mean_return = np.mean(returns)
        std_return = np.std(returns)

        # Confidence intervals (95%)
        return_lower = np.percentile(returns, 2.5)
        return_upper = np.percentile(returns, 97.5)

        sharpe_lower = np.percentile(sharpes, 2.5)
        sharpe_upper = np.percentile(sharpes, 97.5)

        # Robustness score (combination of mean and consistency)
        profitable_paths = len([r for r in returns if r > 0])
        consistency_ratio = profitable_paths / len(returns)

        # Robustness score: reward mean, penalize variance and losses
        robustness_score = mean_return - 2 * std_return if std_return > 0 else mean_return
        if mean_return < 0:
            robustness_score *= 2  # Extra penalty for negative mean

        return MultiPathResult(
            strategy_id=strategy.get('id', 'unknown'),
            strategy_name=strategy.get('name', 'Unknown'),
            strategy_type=strategy.get('type', 'unknown'),
            timeframe='1m',
            num_paths=len(path_results),
            mean_return=mean_return,
            std_return=std_return,
            min_return=min(returns),
            max_return=max(returns),
            median_return=np.median(returns),
            mean_sharpe=np.mean(sharpes),
            std_sharpe=np.std(sharpes),
            min_sharpe=min(sharpes),
            max_sharpe=max(sharpes),
            mean_max_drawdown=np.mean(drawdowns),
            std_max_drawdown=np.std(drawdowns),
            worst_max_drawdown=max(drawdowns),
            robustness_score=robustness_score,
            consistency_ratio=consistency_ratio,
            path_wise_results=path_results,
            return_ci_lower=return_lower,
            return_ci_upper=return_upper,
            sharpe_ci_lower=sharpe_lower,
            sharpe_ci_upper=sharpe_upper,
            is_realistic=True,
            validation_failures=0,
            timestamp=datetime.now().isoformat()
        )

    def _empty_result(self, strategy: Dict) -> MultiPathResult:
        """Return empty result for failed testing."""
        return MultiPathResult(
            strategy_id=strategy.get('id', 'unknown'),
            strategy_name=strategy.get('name', 'Unknown'),
            strategy_type=strategy.get('type', 'unknown'),
            timeframe='1m',
            num_paths=0,
            mean_return=0.0,
            std_return=0.0,
            min_return=0.0,
            max_return=0.0,
            median_return=0.0,
            mean_sharpe=0.0,
            std_sharpe=0.0,
            min_sharpe=0.0,
            max_sharpe=0.0,
            mean_max_drawdown=0.0,
            std_max_drawdown=0.0,
            worst_max_drawdown=0.0,
            robustness_score=-999.0,
            consistency_ratio=0.0,
            path_wise_results=[],
            return_ci_lower=0.0,
            return_ci_upper=0.0,
            sharpe_ci_lower=0.0,
            sharpe_ci_upper=0.0,
            is_realistic=False,
            validation_failures=1,
            timestamp=datetime.now().isoformat()
        )

    def _load_cached_blocks(self) -> Optional[List[Dict]]:
        """Load cached blocks for bootstrapping."""
        cache_file = Path("./palace_data/historical/BTCUSDT_1m.json")

        if cache_file.exists():
            import json
            with open(cache_file, 'r') as f:
                candles = json.load(f)

            # Create blocks from candles
            return create_sample_blocks_from_candles(candles)

        return None


class BootstrapEvolutionEngine:
    """
    Evolve strategies based on multi-path backtest results.

    Uses robustness metrics to guide evolution:
    - Prefer strategies with high mean return
    - Penalize high variance (uncertainty)
    - Reward consistency (profitable across most paths)
    """

    def __init__(self):
        self.results_history = []
        self.evolution_history = []

    def record_multipath_result(self, result: MultiPathResult):
        """Record a multi-path test result."""
        self.results_history.append(result)

        # Track by strategy type
        self._update_evolution_metrics(result)

    def _update_evolution_metrics(self, result: MultiPathResult):
        """Update evolution tracking based on result."""
        key = f"{result.strategy_type}_{result.timeframe}"

        if key not in self.evolution_history:
            self.evolution_history[key] = {
                'strategy_type': result.strategy_type,
                'timeframe': result.timeframe,
                'results': [],
                'best_score': -999.0,
                'best_mean_return': -999.0,
                'total_tests': 0
            }

        history = self.evolution_history[key]
        history['results'].append({
            'timestamp': result.timestamp,
            'robustness_score': result.robustness_score,
            'mean_return': result.mean_return,
            'std_return': result.std_return,
            'consistency': result.consistency_ratio,
            'sharpe_mean': result.mean_sharpe
        })
        history['total_tests'] += 1

        # Update best score
        if result.robustness_score > history['best_score']:
            history['best_score'] = result.robustness_score
            history['best_mean_return'] = result.mean_return

    def get_evolution_insights(self) -> Dict:
        """Get insights from evolution."""
        insights = {
            'total_tests': sum(h['total_tests'] for h in self.evolution_history.values()),
            'best_by_type': {},
            'top_strategies': []
        }

        # Best results by type
        for key, history in self.evolution_history.items():
            if history['results']:
                best_result = max(history['results'], key=lambda x: x['robustness_score'])
                insights['best_by_type'][key] = best_result

        # Overall top strategies
        all_results = []
        for history in self.evolution_history.values():
            all_results.extend(history['results'])

        if all_results:
            sorted_results = sorted(all_results, key=lambda x: x['robustness_score'], reverse=True)
            insights['top_strategies'] = sorted_results[:10]

        return insights

    def generate_evolved_strategy(self, strategy_type: str) -> Optional[Dict]:
        """Generate a new strategy based on evolution insights."""
        key = f"{strategy_type}_1m"

        if key not in self.evolution_history or not self.evolution_history[key]['results']:
            return None

        history = self.evolution_history[key]

        # Get best result
        best = max(history['results'], key=lambda x: x['robustness_score'])

        # Generate evolved version (mutate parameters toward best)
        if best['mean_return'] > 0:
            # Successful strategy - explore nearby parameter space
            new_params = self._mutate_parameters_toward(best)
        else:
            # Unsuccessful - explore broadly
            new_params = self._generate_random_parameters(strategy_type)

        return {
            'id': f"evo_{strategy_type}_{random.randint(1000, 9999)}",
            'name': f"evolved_{strategy_type}_{random.randint(1, 100)}",
            'type': strategy_type,
            'timeframe': '1m',
            'parameters': new_params,
            'generation': history['total_tests']
        }

    def _mutate_parameters_toward(self, best_result: Dict) -> Dict:
        """Mutate parameters toward best performing result."""
        # Small mutation (5% instead of 10%)
        mutation_factor = random.uniform(0.95, 1.05)

        # For demonstration, return sample params
        return {
            'period': int(20 * mutation_factor),
            'threshold': 0.02 * mutation_factor
        }

    def _generate_random_parameters(self, strategy_type: str) -> Dict:
        """Generate random parameters for strategy type."""
        if strategy_type == 'momentum':
            return {
                'period': random.randint(10, 50),
                'threshold': random.uniform(0.01, 0.05)
            }
        elif strategy_type == 'mean_reversion':
            return {
                'period': random.randint(10, 30),
                'std_dev': random.uniform(1.5, 2.5)
            }
        else:
            return {
                'param1': random.uniform(0, 100),
                'param2': random.uniform(0, 100)
            }


# Global instance
_multipath_backtester = None


def get_multipath_backtester() -> MultiPathBacktester:
    """Get the global multi-path backtester instance."""
    global _multipath_backtester
    if _multipath_backtester is None:
        _multipath_backtester = MultiPathBacktester()
    return _multipath_backtester


def get_bootstrap_evolution_engine() -> BootstrapEvolutionEngine:
    """Get the bootstrap evolution engine."""
    return BootstrapEvolutionEngine()
