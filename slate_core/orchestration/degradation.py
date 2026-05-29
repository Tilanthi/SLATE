"""
Graceful Degradation and Fallback System
Provides fallback mechanisms and degraded operation when services fail
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, TypeVar
from dataclasses import dataclass, field
from enum import Enum
import functools

logger = logging.getLogger(__name__)


class DegradationLevel(Enum):
    """System degradation levels."""
    NORMAL = "normal"           # All systems operational
    DEGRADED = "degraded"       # Some systems degraded, alternatives active
    MINIMAL = "minimal"         # Core functionality only
    EMERGENCY = "emergency"     # Critical failures, survival mode


@dataclass
class FallbackResult:
    """Result from a fallback operation."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    fallback_used: Optional[str] = None
    execution_time_ms: float = 0.0
    attempts_made: int = 0


class FallbackStrategy:
    """Base fallback strategy class."""

    def __init__(self, name: str, priority: int = 0):
        self.name = name
        self.priority = priority  # Lower = higher priority
        self.use_count = 0
        self.last_used: Optional[datetime] = None
        self.success_count = 0
        self.failure_count = 0

    async def execute(self, **kwargs) -> FallbackResult:
        """
        Execute the fallback strategy.

        Returns:
        - FallbackResult with outcome
        """
        raise NotImplementedError("Subclasses must implement execute()")

    def get_success_rate(self) -> float:
        """Get success rate for this fallback."""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0

    def is_available(self) -> bool:
        """Check if fallback is available."""
        return True


class CacheFallback(FallbackStrategy):
    """Fallback to cached data."""

    def __init__(self, cache_getter: Callable, ttl_minutes: int = 60):
        super().__init__("cache", priority=1)
        self.cache_getter = cache_getter
        self.ttl_minutes = ttl_minutes

    async def execute(self, key: str, **kwargs) -> FallbackResult:
        """Try to get data from cache."""
        start_time = datetime.utcnow()

        try:
            cached_data = self.cache_getter(key)

            if cached_data is None:
                return FallbackResult(
                    success=False,
                    error="Cache miss",
                    fallback_used=self.name,
                    execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
                )

            # Check cache age
            cache_age = datetime.utcnow() - self.last_used if self.last_used else timedelta(days=1)

            if cache_age > timedelta(minutes=self.ttl_minutes):
                return FallbackResult(
                    success=False,
                    error="Cache expired",
                    fallback_used=self.name,
                    execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
                )

            self.use_count += 1
            self.last_used = datetime.utcnow()
            self.success_count += 1

            return FallbackResult(
                success=True,
                data=cached_data,
                fallback_used=self.name,
                execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                attempts_made=1
            )

        except Exception as e:
            self.failure_count += 1

            return FallbackResult(
                success=False,
                error=str(e),
                fallback_used=self.name,
                execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                attempts_made=1
            )


class DefaultValueFallback(FallbackStrategy):
    """Fallback to default/safe values."""

    def __init__(self, default_value: Any, value_type: str = "unknown"):
        super().__init__("default_value", priority=99)  # Lowest priority
        self.default_value = default_value
        self.value_type = value_type

    async def execute(self, **kwargs) -> FallbackResult:
        """Return default value."""
        start_time = datetime.utcnow()

        self.use_count += 1
        self.last_used = datetime.utcnow()
        self.success_count += 1

        logger.warning(f"Using default value for {self.value_type}: {self.default_value}")

        return FallbackResult(
            success=True,
            data=self.default_value,
            fallback_used=self.name,
            execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
            attempts_made=1
        )


class RetryFallback(FallbackStrategy):
    """Fallback with retry logic."""

    def __init__(
        self,
        operation: Callable,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0
    ):
        super().__init__("retry", priority=10)
        self.operation = operation
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    async def execute(self, **kwargs) -> FallbackResult:
        """Execute operation with retry logic."""
        start_time = datetime.utcnow()
        last_error = None

        for attempt in range(self.max_retries):
            try:
                if asyncio.iscoroutinefunction(self.operation):
                    result = await self.operation(**kwargs)
                else:
                    result = self.operation(**kwargs)

                self.use_count += 1
                self.last_used = datetime.utcnow()
                self.success_count += 1

                return FallbackResult(
                    success=True,
                    data=result,
                    fallback_used=self.name,
                    execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                    attempts_made=attempt + 1
                )

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Retry attempt {attempt + 1} failed: {e}")

                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    await asyncio.sleep(delay)

        self.failure_count += 1

        return FallbackResult(
            success=False,
            error=f"All retries failed: {last_error}",
            fallback_used=self.name,
            execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
            attempts_made=self.max_retries
        )


class GracefulDegradationManager:
    """
    Manages graceful degradation and fallback strategies.

    Features:
    - Multiple fallback strategies per operation
    - Automatic fallback on failure
    - Degradation level tracking
    - Circuit breaker integration
    - Performance monitoring
    """

    def __init__(self):
        self.fallback_chains: Dict[str, List[FallbackStrategy]] = {}
        self.degradation_level = DegradationLevel.NORMAL
        self.circuit_breakers: Dict[str, bool] = {}
        self.performance_history: Dict[str, List[float]] = {}

        # Statistics
        self.total_operations = 0
        self.successful_operations = 0
        self.fallback_activations = 0

    def register_fallback_chain(
        self,
        operation_name: str,
        fallbacks: List[FallbackStrategy]
    ):
        """
        Register fallback chain for an operation.

        Parameters:
        - operation_name: Name of the operation
        - fallbacks: List of fallback strategies in priority order
        """
        # Sort by priority (lower = higher priority)
        sorted_fallbacks = sorted(fallbacks, key=lambda f: f.priority)
        self.fallback_chains[operation_name] = sorted_fallbacks

        logger.info(f"Registered fallback chain for {operation_name} with {len(fallbacks)} strategies")

    async def execute_with_fallback(
        self,
        operation_name: str,
        primary_operation: Callable,
        **kwargs
    ) -> FallbackResult:
        """
        Execute operation with automatic fallback.

        Parameters:
        - operation_name: Name of the operation
        - primary_operation: Primary operation to try first
        - **kwargs: Arguments to pass to operation

        Returns:
        - FallbackResult with outcome
        """
        self.total_operations += 1

        start_time = datetime.utcnow()

        # Check circuit breaker
        if self._is_circuit_open(operation_name):
            logger.warning(f"Circuit breaker open for {operation_name}, skipping to fallbacks")

            # Skip primary, go directly to fallbacks
            primary_result = None
        else:
            # Try primary operation first
            try:
                if asyncio.iscoroutinefunction(primary_operation):
                    result = await primary_operation(**kwargs)
                else:
                    result = primary_operation(**kwargs)

                execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                # Record performance
                self._record_performance(operation_name, execution_time)

                self.successful_operations += 1

                return FallbackResult(
                    success=True,
                    data=result,
                    fallback_used="primary",
                    execution_time_ms=execution_time,
                    attempts_made=1
                )

            except Exception as e:
                logger.warning(f"Primary operation {operation_name} failed: {e}")

                # Check if circuit breaker should open
                self._check_circuit_breaker(operation_name, success=False)

        # Try fallbacks
        fallbacks = self.fallback_chains.get(operation_name, [])

        if not fallbacks:
            return FallbackResult(
                success=False,
                error=f"Operation {operation_name} failed and no fallbacks available",
                execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                attempts_made=0
            )

        self.fallback_activations += 1

        for fallback in fallbacks:
            if not fallback.is_available():
                continue

            logger.info(f"Trying fallback {fallback.name} for {operation_name}")

            result = await fallback.execute(**kwargs)

            if result.success:
                logger.info(f"Fallback {fallback.name} succeeded for {operation_name}")

                self._check_circuit_breaker(operation_name, success=True)

                return result
            else:
                logger.warning(f"Fallback {fallback.name} failed for {operation_name}: {result.error}")

        # All fallbacks failed
        return FallbackResult(
            success=False,
            error=f"All fallbacks failed for {operation_name}",
            execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
            attempts_made=len(fallbacks) + 1
        )

    def _is_circuit_open(self, operation_name: str) -> bool:
        """Check if circuit breaker is open for operation."""
        return self.circuit_breakers.get(operation_name, False)

    def _check_circuit_breaker(self, operation_name: str, success: bool):
        """Update circuit breaker state."""
        if success:
            # Close circuit breaker on success
            if operation_name in self.circuit_breakers:
                del self.circuit_breakers[operation_name]
        else:
            # Track failures - could implement more sophisticated logic here
            failures = getattr(self, f'_failures_{operation_name}', 0) + 1
            setattr(self, f'_failures_{operation_name}', failures)

            # Open circuit breaker after 5 consecutive failures
            if failures >= 5:
                self.circuit_breakers[operation_name] = True
                logger.warning(f"Circuit breaker opened for {operation_name}")

    def _record_performance(self, operation_name: str, execution_time_ms: float):
        """Record operation performance for monitoring."""
        if operation_name not in self.performance_history:
            self.performance_history[operation_name] = []

        self.performance_history[operation_name].append(execution_time_ms)

        # Keep only last 100 measurements
        if len(self.performance_history[operation_name]) > 100:
            self.performance_history[operation_name].pop(0)

    def get_performance_stats(self, operation_name: str) -> Dict:
        """Get performance statistics for an operation."""
        times = self.performance_history.get(operation_name, [])

        if not times:
            return {
                'operation': operation_name,
                'message': 'No performance data available'
            }

        import numpy as np

        return {
            'operation': operation_name,
            'count': len(times),
            'mean_ms': np.mean(times),
            'median_ms': np.median(times),
            'p95_ms': np.percentile(times, 95),
            'p99_ms': np.percentile(times, 99),
            'min_ms': np.min(times),
            'max_ms': np.max(times)
        }

    def get_degradation_status(self) -> Dict:
        """Get current degradation status."""
        success_rate = (
            self.successful_operations / self.total_operations
            if self.total_operations > 0 else 1.0
        )

        # Determine degradation level
        if success_rate >= 0.95:
            self.degradation_level = DegradationLevel.NORMAL
        elif success_rate >= 0.80:
            self.degradation_level = DegradationLevel.DEGRADED
        elif success_rate >= 0.50:
            self.degradation_level = DegradationLevel.MINIMAL
        else:
            self.degradation_level = DegradationLevel.EMERGENCY

        return {
            'degradation_level': self.degradation_level.value,
            'total_operations': self.total_operations,
            'successful_operations': self.successful_operations,
            'fallback_activations': self.fallback_activations,
            'success_rate': success_rate,
            'circuit_breakers_open': len(self.circuit_breakers),
            'active_fallback_chains': len(self.fallback_chains)
        }

    def reset_circuit_breaker(self, operation_name: str):
        """Manually reset circuit breaker for an operation."""
        if operation_name in self.circuit_breakers:
            del self.circuit_breakers[operation_name]
            logger.info(f"Circuit breaker reset for {operation_name}")


def fallback_decorator(operation_name: str):
    """
    Decorator to add fallback behavior to functions.

    Parameters:
    - operation_name: Name of the operation for fallback chain lookup
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            manager = get_degradation_manager()
            return await manager.execute_with_fallback(
                operation_name,
                functools.partial(func, *args, **kwargs),
                **kwargs
            )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, we need to run in async context
            async def _async_execute():
                manager = get_degradation_manager()
                return await manager.execute_with_fallback(
                    operation_name,
                    functools.partial(func, *args, **kwargs),
                    **kwargs
                )

            return asyncio.run(_async_execute())

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Global degradation manager instance
_global_degradation_manager: Optional[GracefulDegradationManager] = None


def get_degradation_manager() -> GracefulDegradationManager:
    """Get the global degradation manager instance."""
    global _global_degradation_manager
    if _global_degradation_manager is None:
        _global_degradation_manager = GracefulDegradationManager()
    return _global_degradation_manager


async def setup_default_fallbacks(data_cache: Optional[Dict] = None):
    """
    Setup default fallback chains for common operations.

    Parameters:
    - data_cache: Optional data cache dict
    """
    manager = get_degradation_manager()

    if data_cache is None:
        data_cache = {}

    # Data fetching fallback chain
    async def fetch_from_cache(symbol: str, interval: str, **kwargs):
        """Fetch data from cache."""
        cache_key = f"{symbol}_{interval}"
        return data_cache.get(cache_key)

    async def fetch_default_data(**kwargs):
        """Return default empty DataFrame."""
        import pandas as pd
        return pd.DataFrame()

    data_fallbacks = [
        CacheFallback(lambda k: data_cache.get(k)),
        DefaultValueFallback(None, "market_data")
    ]

    manager.register_fallback_chain("fetch_market_data", data_fallbacks)

    # API call fallback chain
    async def retry_api_call(**kwargs):
        """Retry API call with default logic."""
        # This would be implemented by the specific API caller
        raise NotImplementedError("API retry logic not implemented")

    api_fallbacks = [
        RetryFallback(retry_api_call, max_retries=3),
        DefaultValueFallback(None, "api_response")
    ]

    manager.register_fallback_chain("api_call", api_fallbacks)

    logger.info("Default fallback chains registered")
