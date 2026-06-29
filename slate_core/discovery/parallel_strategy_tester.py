#!/usr/bin/env python3
"""
SLATE Parallel Strategy Testing System

Inspired by BIODISC's parallel independence testing, this system tests
multiple trading strategies simultaneously instead of sequentially.

Key benefits:
- 4-8x speedup on multi-core systems
- Linear scaling with CPU cores
- Better resource utilization
- Faster discovery cycles
"""

import asyncio
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import multiprocessing as mp
import numpy as np

try:
    from .strategy_cache import get_strategy_cache, StrategyFingerprint, BacktestResult
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    logging.warning("Strategy cache not available - parallel testing will work without caching")

logger = logging.getLogger(__name__)


@dataclass
class StrategyTest:
    """A strategy to be tested."""
    strategy_type: str
    parameters: Dict[str, Any]
    timeframe: str
    data_period: str
    volatility_regime: str = "unknown"
    priority: int = 0  # Higher priority = test first

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'strategy_type': self.strategy_type,
            'parameters': self.parameters,
            'timeframe': self.timeframe,
            'data_period': self.data_period,
            'volatility_regime': self.volatility_regime,
            'priority': self.priority
        }


@dataclass
class StrategyTestResult:
    """Result of a strategy test."""
    strategy: StrategyTest
    success: bool
    result: Optional[Dict[str, Any]]
    error: Optional[str] = None
    computation_time_ms: int = 0
    cached: bool = False


class ParallelStrategyTester:
    """
    Parallel strategy testing system.

    Tests multiple trading strategies simultaneously using multiple CPU cores.
    Inspired by BIODISC's parallel independence testing approach.
    """

    def __init__(self,
                 max_workers: Optional[int] = None,
                 enable_cache: bool = True,
                 timeout_seconds: int = 300):
        """
        Initialize parallel strategy tester.

        Args:
            max_workers: Maximum parallel workers (default: CPU count - 1)
            enable_cache: Whether to use strategy caching
            timeout_seconds: Timeout per strategy test
        """
        self.max_workers = max_workers or max(1, mp.cpu_count() - 1)
        self.enable_cache = enable_cache and CACHE_AVAILABLE
        self.timeout_seconds = timeout_seconds

        # Statistics
        self.total_tests = 0
        self.parallel_tests = 0
        self.cache_hits = 0

        if self.enable_cache:
            self.cache = get_strategy_cache()

        logger.info(f"ParallelStrategyTester initialized: {self.max_workers} workers, cache={self.enable_cache}")

    async def test_strategies_parallel(self,
                                       strategies: List[StrategyTest],
                                       test_function: Callable,
                                       show_progress: bool = True) -> List[StrategyTestResult]:
        """
        Test multiple strategies in parallel.

        Args:
            strategies: List of strategies to test
            test_function: Function to test a single strategy
            show_progress: Whether to show progress

        Returns:
            List of test results
        """
        self.total_tests += len(strategies)
        self.parallel_tests += len(strategies)

        logger.info(f"Testing {len(strategies)} strategies in parallel with {self.max_workers} workers")

        # Check cache first
        if self.enable_cache:
            strategies, cached_results = self._filter_cached_strategies(strategies)
            self.cache_hits += len(cached_results)
            logger.info(f"Cache hits: {len(cached_results)}, remaining: {len(strategies)}")
        else:
            cached_results = []

        if not strategies:
            logger.info("All strategies found in cache")
            return cached_results

        # Test remaining strategies in parallel
        parallel_results = await self._test_parallel(strategies, test_function, show_progress)

        # Cache new results
        if self.enable_cache:
            self._cache_results(parallel_results)

        # Combine cached and parallel results
        all_results = cached_results + parallel_results

        logger.info(f"Parallel testing complete: {len(all_results)} results, {self.cache_hits} from cache")

        return all_results

    def _filter_cached_strategies(self, strategies: List[StrategyTest]) -> tuple[List[StrategyTest], List[StrategyTestResult]]:
        """Filter out strategies that are already cached."""
        uncached_strategies = []
        cached_results = []

        for strategy in strategies:
            fingerprint = self.cache.generate_fingerprint(
                strategy_type=strategy.strategy_type,
                timeframe=strategy.timeframe,
                parameters=strategy.parameters,
                data_period=strategy.data_period,
                volatility_regime=strategy.volatility_regime
            )

            cached_result = self.cache.get(fingerprint)
            if cached_result:
                # Convert cached result to StrategyTestResult
                result = StrategyTestResult(
                    strategy=strategy,
                    success=True,
                    result={
                        'total_profit_usdt': cached_result.total_profit_usdt,
                        'sharpe_ratio': cached_result.sharpe_ratio,
                        'max_drawdown_pct': cached_result.max_drawdown_pct,
                        'win_rate': cached_result.win_rate,
                        'total_return_pct': cached_result.total_return_pct,
                        'passed_validation': cached_result.passed_validation
                    },
                    cached=True,
                    computation_time_ms=cached_result.computation_time_ms
                )
                cached_results.append(result)
            else:
                uncached_strategies.append(strategy)

        return uncached_strategies, cached_results

    async def _test_parallel(self,
                            strategies: List[StrategyTest],
                            test_function: Callable,
                            show_progress: bool) -> List[StrategyTestResult]:
        """Test strategies in parallel using process pool."""
        results = []

        # Sort by priority (higher priority first)
        strategies.sort(key=lambda x: x.priority, reverse=True)

        # Use ProcessPoolExecutor for CPU-bound work
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            futures = {
                executor.submit(self._run_single_test, strategy, test_function): strategy
                for strategy in strategies
            }

            # Collect results as they complete
            if show_progress:
                logger.info(f"Submitted {len(futures)} strategies for parallel testing...")

            for future in as_completed(futures):
                strategy = futures[future]
                try:
                    result = future.result(timeout=self.timeout_seconds)
                    results.append(result)

                    if show_progress and len(results) % 10 == 0:
                        logger.info(f"Progress: {len(results)}/{len(strategies)} strategies tested")

                except Exception as e:
                    logger.error(f"Error testing strategy {strategy.strategy_type}: {e}")
                    results.append(StrategyTestResult(
                        strategy=strategy,
                        success=False,
                        result=None,
                        error=str(e)
                    ))

        return results

    def _run_single_test(self, strategy: StrategyTest, test_function: Callable) -> StrategyTestResult:
        """Run a single strategy test (called in parallel)."""
        import time
        start_time = time.time()

        try:
            # Run the test function
            result = test_function(strategy)

            computation_time = int((time.time() - start_time) * 1000)

            return StrategyTestResult(
                strategy=strategy,
                success=True,
                result=result,
                computation_time_ms=computation_time,
                cached=False
            )

        except Exception as e:
            computation_time = int((time.time() - start_time) * 1000)
            return StrategyTestResult(
                strategy=strategy,
                success=False,
                result=None,
                error=str(e),
                computation_time_ms=computation_time
            )

    def _cache_results(self, results: List[StrategyTestResult]):
        """Cache new test results."""
        if not self.enable_cache:
            return

        for result in results:
            if result.success and result.result:
                fingerprint = self.cache.generate_fingerprint(
                    strategy_type=result.strategy.strategy_type,
                    timeframe=result.strategy.timeframe,
                    parameters=result.strategy.parameters,
                    data_period=result.strategy.data_period,
                    volatility_regime=result.strategy.volatility_regime
                )

                # Create BacktestResult for caching
                backtest_result = BacktestResult(
                    fingerprint=fingerprint,
                    total_profit_usdt=result.result.get('total_profit_usdt', 0),
                    sharpe_ratio=result.result.get('sharpe_ratio', 0),
                    max_drawdown_pct=result.result.get('max_drawdown_pct', 0),
                    win_rate=result.result.get('win_rate', 0),
                    total_return_pct=result.result.get('total_return_pct', 0),
                    passed_validation=result.result.get('passed_validation', False),
                    timestamp=datetime.now(),
                    computation_time_ms=result.computation_time_ms
                )

                self.cache.put(fingerprint, backtest_result)

    def get_stats(self) -> Dict[str, Any]:
        """Get testing statistics."""
        cache_stats = self.cache.get_stats() if self.enable_cache else {}

        return {
            'total_tests': self.total_tests,
            'parallel_tests': self.parallel_tests,
            'cache_hits': self.cache_hits,
            'max_workers': self.max_workers,
            'cache_enabled': self.enable_cache,
            **cache_stats
        }


def create_parallel_tester(max_workers: Optional[int] = None,
                          enable_cache: bool = True) -> ParallelStrategyTester:
    """
    Create a parallel strategy tester.

    Args:
        max_workers: Maximum parallel workers
        enable_cache: Whether to use strategy caching

    Returns:
        ParallelStrategyTester instance
    """
    return ParallelStrategyTester(
        max_workers=max_workers,
        enable_cache=enable_cache
    )


# Global tester instance
_parallel_tester: Optional[ParallelStrategyTester] = None


def get_parallel_tester() -> ParallelStrategyTester:
    """Get global parallel strategy tester instance."""
    global _parallel_tester
    if _parallel_tester is None:
        _parallel_tester = create_parallel_tester()
    return _parallel_tester