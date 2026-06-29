#!/usr/bin/env python3
"""
SLATE Progressive Results Display System

Inspired by BIODISC's progressive refinement, this system shows discovery
results in real-time as they're found instead of waiting for complete cycles.

Key benefits:
- Faster time-to-first-results
- Better user experience
- Real-time feedback on discovery progress
- Can stop early if satisfied with results
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json

logger = logging.getLogger(__name__)


class ResultPriority(Enum):
    """Priority levels for displaying results."""
    CRITICAL = "critical"     # Immediate display (breakthrough discoveries)
    HIGH = "high"           # Display within 1 second
    NORMAL = "normal"       # Display within 5 seconds
    LOW = "low"            # Display within 30 seconds


@dataclass
class DiscoveryResult:
    """A single discovery result."""
    strategy_name: str
    strategy_type: str
    total_profit_usdt: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    passed_validation: bool
    timestamp: datetime
    computation_time_ms: int
    priority: ResultPriority = ResultPriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'strategy_name': self.strategy_name,
            'strategy_type': self.strategy_type,
            'total_profit_usdt': self.total_profit_usdt,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown_pct': self.max_drawdown_pct,
            'win_rate': self.win_rate,
            'passed_validation': self.passed_validation,
            'timestamp': self.timestamp.isoformat(),
            'computation_time_ms': self.computation_time_ms,
            'priority': self.priority.value,
            'metadata': self.metadata
        }


class ProgressiveResultsManager:
    """
    Manages progressive display of discovery results.

    Shows results as they're discovered rather than waiting for complete cycles.
    """

    def __init__(self,
                 display_callback: Optional[Callable] = None,
                 max_buffer_size: int = 100):
        """
        Initialize progressive results manager.

        Args:
            display_callback: Function to call for displaying results
            max_buffer_size: Maximum results to buffer before forcing display
        """
        self.display_callback = display_callback or self._default_display
        self.max_buffer_size = max_buffer_size

        # Result buffers by priority
        self.critical_buffer: List[DiscoveryResult] = []
        self.high_buffer: List[DiscoveryResult] = []
        self.normal_buffer: List[DiscoveryResult] = []
        self.low_buffer: List[DiscoveryResult] = []

        # Statistics
        self.total_results = 0
        self.displayed_results = 0
        self.buffer_overruns = 0

        # Display loop task
        self.display_task: Optional[asyncio.Task] = None
        self.running = False

        logger.info("ProgressiveResultsManager initialized")

    async def start(self):
        """Start the progressive display system."""
        if self.running:
            return

        self.running = True
        self.display_task = asyncio.create_task(self._display_loop())
        logger.info("Progressive display system started")

    async def stop(self):
        """Stop the progressive display system."""
        if not self.running:
            return

        self.running = False
        if self.display_task:
            self.display_task.cancel()
            try:
                await self.display_task
            except asyncio.CancelledError:
                pass

        # Display any remaining results
        await self.flush_all_buffers()

        logger.info("Progressive display system stopped")

    async def add_result(self, result: DiscoveryResult):
        """
        Add a discovery result for progressive display.

        Args:
            result: Discovery result to display
        """
        self.total_results += 1

        # Route to appropriate buffer based on priority
        if result.priority == ResultPriority.CRITICAL:
            self.critical_buffer.append(result)
            # Display critical results immediately
            await self._display_result(result)
        elif result.priority == ResultPriority.HIGH:
            self.high_buffer.append(result)
        elif result.priority == ResultPriority.NORMAL:
            self.normal_buffer.append(result)
        else:
            self.low_buffer.append(result)

        # Check buffer limits
        await self._check_buffer_limits()

    async def _display_loop(self):
        """Main display loop - shows results based on priority and timing."""
        while self.running:
            try:
                # Display high priority results immediately
                while self.high_buffer:
                    result = self.high_buffer.pop(0)
                    await self._display_result(result)

                # Display normal results periodically
                if self.normal_buffer and len(self.normal_buffer) > 10:
                    # Batch display normal results
                    batch = self.normal_buffer[:10]
                    self.normal_buffer = self.normal_buffer[10:]
                    await self._display_batch(batch)

                # Display low priority results less frequently
                if self.low_buffer and len(self.low_buffer) > 20:
                    batch = self.low_buffer[:20]
                    self.low_buffer = self.low_buffer[20:]
                    await self._display_batch(batch)

                # Small delay before next check
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in display loop: {e}")

    async def _display_result(self, result: DiscoveryResult):
        """Display a single result."""
        try:
            await self.display_callback(result)
            self.displayed_results += 1
        except Exception as e:
            logger.error(f"Error displaying result: {e}")

    async def _display_batch(self, results: List[DiscoveryResult]):
        """Display a batch of results."""
        try:
            # Format as batch summary
            summary = self._format_batch_summary(results)
            await self.display_callback({'batch': True, 'results': summary})
            self.displayed_results += len(results)
        except Exception as e:
            logger.error(f"Error displaying batch: {e}")

    def _format_batch_summary(self, results: List[DiscoveryResult]) -> Dict[str, Any]:
        """Format a batch of results for display."""
        return {
            'count': len(results),
            'profitable': sum(1 for r in results if r.total_profit_usdt > 0),
            'passed_validation': sum(1 for r in results if r.passed_validation),
            'avg_profit_usdt': sum(r.total_profit_usdt for r in results) / len(results),
            'best_strategy': max(results, key=lambda x: x.total_profit_usdt).strategy_name if results else None,
            'best_profit_usdt': max((r.total_profit_usdt for r in results), default=0)
        }

    def _default_display(self, result: Any):
        """Default display callback (can be overridden)."""
        if isinstance(result, DiscoveryResult):
            print(f"🎯 Discovery: {result.strategy_name}")
            print(f"   Profit: ${result.total_profit_usdt:.2f}")
            print(f"   Sharpe: {result.sharpe_ratio:.2f}")
            print(f"   Validation: {'✅' if result.passed_validation else '❌'}")
        elif isinstance(result, dict) and result.get('batch'):
            summary = result['results']
            print(f"📊 Batch: {summary['count']} results, {summary['profitable']} profitable")
            print(f"   Best: {summary['best_strategy']} (${summary['best_profit_usdt']:.2f})")

    async def _check_buffer_limits(self):
        """Check if buffers are exceeding limits and force display if needed."""
        total_buffered = (len(self.critical_buffer) +
                          len(self.high_buffer) +
                          len(self.normal_buffer) +
                          len(self.low_buffer))

        if total_buffered > self.max_buffer_size:
            self.buffer_overruns += 1
            logger.warning(f"Buffer overrun: {total_buffered} results buffered, forcing display")
            await self.flush_all_buffers()

    async def flush_all_buffers(self):
        """Display all buffered results."""
        all_results = []
        all_results.extend(self.critical_buffer)
        all_results.extend(self.high_buffer)
        all_results.extend(self.normal_buffer)
        all_results.extend(self.low_buffer)

        # Clear buffers
        self.critical_buffer.clear()
        self.high_buffer.clear()
        self.normal_buffer.clear()
        self.low_buffer.clear()

        # Display all
        if all_results:
            await self._display_batch(all_results)

    def get_stats(self) -> Dict[str, Any]:
        """Get display statistics."""
        return {
            'total_results': self.total_results,
            'displayed_results': self.displayed_results,
            'pending_results': len(self.critical_buffer) + len(self.high_buffer) +
                              len(self.normal_buffer) + len(self.low_buffer),
            'buffer_overruns': self.buffer_overruns,
            'running': self.running
        }


class RealTimeDiscoveryTracker:
    """
    Tracks discovery progress and provides real-time updates.
    """

    def __init__(self):
        """Initialize real-time discovery tracker."""
        self.start_time = datetime.now()
        self.strategies_tested = 0
        self.profitable_found = 0
        self.validated_found = 0
        self.current_cycle = 0
        self.last_update = datetime.now()

    def update_progress(self,
                       strategies_tested: int,
                       profitable_found: int,
                       validated_found: int):
        """Update discovery progress."""
        self.strategies_tested = strategies_tested
        self.profitable_found = profitable_found
        self.validated_found = validated_found
        self.last_update = datetime.now()

    def get_progress_summary(self) -> Dict[str, Any]:
        """Get current progress summary."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        rate = self.strategies_tested / elapsed if elapsed > 0 else 0

        return {
            'strategies_tested': self.strategies_tested,
            'profitable_found': self.profitable_found,
            'validated_found': self.validated_found,
            'success_rate': self.profitable_found / self.strategies_tested if self.strategies_tested > 0 else 0,
            'strategies_per_second': rate,
            'elapsed_seconds': elapsed,
            'last_update': self.last_update.isoformat()
        }


def create_progressive_manager(display_callback: Optional[Callable] = None) -> ProgressiveResultsManager:
    """Create a progressive results manager."""
    return ProgressiveResultsManager(display_callback=display_callback)


# Global instances
_progressive_manager: Optional[ProgressiveResultsManager] = None
_tracker: Optional[RealTimeDiscoveryTracker] = None


def get_progressive_manager() -> ProgressiveResultsManager:
    """Get global progressive results manager."""
    global _progressive_manager
    if _progressive_manager is None:
        _progressive_manager = create_progressive_manager()
    return _progressive_manager


def get_discovery_tracker() -> RealTimeDiscoveryTracker:
    """Get global discovery tracker."""
    global _tracker
    if _tracker is None:
        _tracker = RealTimeDiscoveryTracker()
    return _tracker