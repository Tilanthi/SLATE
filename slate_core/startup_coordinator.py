#!/usr/bin/env python3
"""
SLATE Startup Coordinator - Automatic Discovery Management

This module ensures SLATE always starts with discovery running automatically,
and manages pausing/resuming based on user activity.

Core Principles:
1. Discovery starts immediately on SLATE startup
2. Discovery runs CONTINUOUSLY unless actively handling user requests
3. User activity automatically pauses discovery ONLY during request execution
4. Discovery resumes IMMEDIATELY after user request completes (no waiting period)
5. System is paper-trading only (never real money)
6. Automatic restart on crashes, hangs, or failures
7. Watchdog protection with health monitoring
"""

import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class SystemState(Enum):
    """System operation states."""
    AUTO_DISCOVERY = "auto_discovery"      # Running continuous discovery
    USER_TASK = "user_task"               # Executing specific user request
    PAUSED = "paused"                     # Temporarily paused
    IDLE = "idle"                         # Waiting to resume


class StartupCoordinator:
    """
    Manages SLATE startup and continuous discovery operations.

    This coordinator ensures:
    - Discovery starts immediately when SLATE launches
    - User requests pause discovery ONLY during execution
    - Discovery resumes IMMEDIATELY after user request completion
    - Discovery runs continuously when no active user tasks
    - All operations maintain realistic transaction costs
    """

    def __init__(self):
        """Initialize the startup coordinator."""
        self.state = SystemState.AUTO_DISCOVERY
        self.last_user_activity = datetime.now()
        self.discovery_engine = None
        self.discovery_task: Optional[asyncio.Task] = None
        self.user_requested_pause = False
        self.startup_complete = False

        # Hang detection and timeout protection
        self.last_cycle_complete_time = datetime.now()
        self.cycle_timeout_seconds = 120  # 2 minutes max per discovery cycle
        self.hang_detection_enabled = True
        self.consecutive_hangs = 0
        self.max_consecutive_hangs = 3

        # Watchdog task tracking
        self.watchdog_task: Optional[asyncio.Task] = None

        # Configuration
        self.idle_timeout_minutes = 0.1  # Resume discovery after 6 seconds of inactivity
        self.discovery_cycle_interval_seconds = 5  # Run discovery every 5 seconds when active
        self.monitoring_interval_hours = 1  # Run strategy monitoring every hour
        self.last_monitoring_time = datetime.now()

        logger.info("Startup Coordinator initialized with hang detection and strategy monitoring")

    def start(self):
        """Start SLATE with automatic closed-loop AI discovery."""
        logger.info("=" * 70)
        logger.info("🧠 SLATE STARTING WITH CONTINUOUS CLOSED-LOOP AI DISCOVERY")
        logger.info("=" * 70)
        logger.info(f"Startup time: {datetime.now().isoformat()}")
        logger.info(f"Initial state: {self.state.value}")
        logger.info("🎯 Discovery runs CONTINUOUSLY when no user tasks active")
        logger.info("⚡ User requests pause discovery ONLY during execution")
        logger.info("🔄 Discovery resumes IMMEDIATELY after request completion")
        logger.info("=" * 70)

        # Initialize closed-loop AI discovery system
        try:
            from .discovery.closed_loop_integration import get_enhanced_discovery_system
            from .discovery.edge_discovery_engine import EdgeDiscoveryEngine

            self.closed_loop_system = get_enhanced_discovery_system()
            self.discovery_engine = EdgeDiscoveryEngine()

            logger.info("✅ Closed-Loop AI Discovery System initialized")
            self.startup_complete = True
        except Exception as e:
            logger.error(f"Failed to initialize closed-loop discovery: {e}", exc_info=True)

    async def start_discovery_loop(self):
        """Start the discovery loop - must be called from async context."""
        if not self.discovery_engine:
            logger.error("Cannot start discovery loop - engine not initialized")
            return

        # Check if discovery is already running
        if self.discovery_task and not self.discovery_task.done():
            logger.info("Discovery loop already running - skipping duplicate start")
            return

        logger.info("Starting discovery loop in background...")
        self.discovery_task = asyncio.create_task(self._discovery_loop())
        logger.info("Discovery loop started successfully")

        # Start watchdog to monitor and auto-restart if needed (only if not already running)
        if self.watchdog_task is None or self.watchdog_task.done():
            logger.info("🐕 Starting discovery watchdog...")
            self.watchdog_task = asyncio.create_task(self.watchdog_check_discovery())
        else:
            logger.info("Watchdog already running - skipping duplicate start")

    def record_user_activity(self):
        """
        Record user activity (API call, query, task request).

        This IMMEDIATELY pauses discovery and resets idle timer.
        Discovery resumes as soon as the request completes.
        """
        self.last_user_activity = datetime.now()
        logger.info(f"🎯 User activity recorded at {self.last_user_activity.isoformat()}")

        if self.state == SystemState.AUTO_DISCOVERY:
            logger.info("🎯 User request detected - IMMEDIATELY pausing discovery")
            self.state = SystemState.USER_TASK
            self.user_requested_pause = True

    async def execute_user_task(self, task_func, *args, **kwargs):
        """
        Execute a specific user task with discovery paused.

        Args:
            task_func: Async function to execute
            *args: Positional arguments for task function
            **kwargs: Keyword arguments for task function

        Returns:
            Result of task function execution
        """
        # Record user activity
        self.record_user_activity()

        # Pause discovery
        previous_state = self.state
        self.state = SystemState.USER_TASK
        logger.info(f"Executing user task: {task_func.__name__}")

        try:
            # Execute user task
            result = await task_func(*args, **kwargs)
            logger.info(f"User task completed: {task_func.__name__}")
            return result

        finally:
            # Task complete, check if we should resume discovery
            await self._check_resume_discovery()

    def _start_discovery_loop(self):
        """Start the continuous discovery loop in background."""
        try:
            # Import discovery engine
            from .discovery.edge_discovery_engine import EdgeDiscoveryEngine

            self.discovery_engine = EdgeDiscoveryEngine()
            logger.info("Discovery engine initialized")

            # Start background task
            self.discovery_task = asyncio.create_task(self._discovery_loop())
            logger.info("Discovery loop started in background")
            self.startup_complete = True

        except Exception as e:
            logger.error(f"Failed to start discovery loop: {e}", exc_info=True)

    async def _discovery_loop(self):
        """Main discovery loop - runs CONTINUOUSLY unless actively handling user tasks."""
        logger.info("🧠 Continuous discovery loop started - will run 24/7 unless handling user tasks")
        consecutive_errors = 0
        max_consecutive_errors = 5

        while True:
            try:
                # IMMEDIATE pause check - only pause if ACTIVELY handling a user request
                if self.state == SystemState.USER_TASK:
                    logger.debug("🎯 Handling user request - discovery paused momentarily")
                    await asyncio.sleep(1)  # Brief check interval
                    await self._check_resume_discovery()
                    continue

                # IMMEDIATE resume check - resume as soon as user task completes
                if self.user_requested_pause:
                    await self._check_resume_discovery()
                    if self.user_requested_pause:  # Still paused after check
                        await asyncio.sleep(1)
                        continue

                # Ensure we're in auto-discovery state
                if self.state != SystemState.AUTO_DISCOVERY:
                    logger.info("🔄 Resuming continuous automatic discovery")
                    self.state = SystemState.AUTO_DISCOVERY

                # CRITICAL: Update global discovery_running flag
                # Import here to avoid circular dependency
                try:
                    import slate_core.server as server_module
                    if hasattr(server_module, 'discovery_running'):
                        server_module.discovery_running = True
                except ImportError:
                    pass  # Server module not available, continue anyway

                # 🧠 RUN CLOSED-LOOP AI DISCOVERY CYCLE
                logger.debug("🧠 Running closed-loop AI discovery cycle...")
                cycle_start_time = datetime.now()

                try:
                    # Load market data for discovery
                    import pandas as pd

                    # Fix 2b: load DAILY bars. The source file is HOURLY despite
                    # its "1d" name; SLATE's documented edge is on the daily
                    # timeframe (sub-daily signals are not profitable), so
                    # resample intraday->daily via the shared evolution loader.
                    from slate_core.discovery.evolution.load_data import load_daily_data
                    df = load_daily_data('sol_data_cache/SOLUSDT_perpetual_1d_12m.csv')

                    logger.info(f"✅ Market data loaded: {len(df)} daily bars")

                    # Filter data for optimal volatility regime (Option 4: Test different market regimes)
                    from slate_core.discovery.market_regime_filter import get_market_regime_filter

                    regime_filter = get_market_regime_filter()

                    # Analyze volatility regimes
                    regime_analysis = regime_filter.analyze_volatility_regimes(df)

                    # Filter for high volatility regime (optimal for adaptive/mean reversion strategies)
                    df_filtered = regime_filter.filter_for_discovery(df, strategy_type='adaptive_regime_switching')

                    logger.info(f"🎯 Using filtered data: {len(df_filtered)} days (high volatility regime)")

                    # Run closed-loop AI discovery cycle on filtered data
                    results = self.closed_loop_system.run_enhanced_discovery_cycle(df_filtered)

                    # Update last cycle complete time for hang detection
                    self.last_cycle_complete_time = datetime.now()
                    cycle_duration = (self.last_cycle_complete_time - cycle_start_time).total_seconds()

                    if results.get('status') == 'success':
                        performance = results.get('performance', {})
                        discovery = results.get('discovery', {})

                        hypotheses = performance.get('hypotheses_generated', 0)
                        strategies = performance.get('strategies_generated', 0)
                        validated = performance.get('total_validated', 0)
                        success_rate = performance.get('overall_success_rate', 0)

                        logger.info(f"✅ Closed-Loop AI cycle: {hypotheses} hypotheses, {strategies} strategies, {validated} validated, {success_rate:.1%} success (duration: {cycle_duration:.1f}s)")

                        # Reset hang counter on successful cycle completion
                        self.consecutive_hangs = 0
                        # Reset error counter on success
                        consecutive_errors = 0
                    else:
                        logger.warning(f"⚠️  Closed-loop discovery issue: {results.get('message', 'Unknown error')}")
                        consecutive_errors += 1

                    # 🎯 PERIODIC STRATEGY MONITORING CYCLE
                    # Run monitoring every hour (separate from discovery cycles)
                    time_since_last_monitoring = (datetime.now() - self.last_monitoring_time).total_seconds()
                    monitoring_interval_seconds = self.monitoring_interval_hours * 3600

                    if time_since_last_monitoring >= monitoring_interval_seconds:
                        logger.info("🎯 Starting periodic strategy monitoring cycle...")
                        await self._run_monitoring_cycle()
                        self.last_monitoring_time = datetime.now()

                except Exception as discovery_error:
                    logger.error(f"❌ Closed-loop discovery execution error: {discovery_error}")
                    consecutive_errors += 1

                # Check for too many consecutive errors
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"❌ Too many consecutive errors ({consecutive_errors}), waiting before retry...")
                    await asyncio.sleep(30)  # Longer pause on repeated errors
                    consecutive_errors = 0  # Reset after waiting

                # Brief pause before next cycle (prevents CPU overload)
                await asyncio.sleep(self.discovery_cycle_interval_seconds)

            except Exception as e:
                logger.error(f"❌ Discovery loop error: {e}", exc_info=True)
                consecutive_errors += 1

                # Set global discovery_running to False on error
                try:
                    import slate_core.server as server_module
                    if hasattr(server_module, 'discovery_running'):
                        server_module.discovery_running = False
                except ImportError:
                    pass

                # Exponential backoff on repeated errors
                wait_time = min(10 * (2 ** min(consecutive_errors, 4)), 60)
                logger.warning(f"⏳ Waiting {wait_time}s before retry (consecutive errors: {consecutive_errors})")
                await asyncio.sleep(wait_time)

    async def _check_resume_discovery(self):
        """IMMEDIATE resume check - resume discovery as soon as user task completes."""
        idle_time = (datetime.now() - self.last_user_activity).total_seconds()
        idle_timeout = self.idle_timeout_minutes * 60

        # IMMEDIATE resume - don't wait for extended idle period
        if idle_time >= idle_timeout and self.user_requested_pause:
            logger.info(f"✅ User task complete - IMMEDIATELY resuming continuous discovery (idle: {idle_time:.1f}s)")
            self.user_requested_pause = False
            self.state = SystemState.AUTO_DISCOVERY
        else:
            logger.debug(f"🎯 User task still active (idle: {idle_time:.1f}s)")

    def get_status(self) -> Dict[str, Any]:
        """Get current system status."""
        idle_time = (datetime.now() - self.last_user_activity).total_seconds()

        # Check if discovery task is still running
        discovery_active = self.discovery_task is not None and not self.discovery_task.done()

        return {
            'state': self.state.value,
            'startup_complete': self.startup_complete,
            'discovery_running': self.state == SystemState.AUTO_DISCOVERY and discovery_active,
            'discovery_task_active': discovery_active,
            'last_user_activity': self.last_user_activity.isoformat(),
            'idle_time_seconds': idle_time,
            'idle_time_minutes': idle_time / 60,
            'resume_in_minutes': max(0, self.idle_timeout_minutes - (idle_time / 60)),
            'user_requested_pause': self.user_requested_pause,
            'configuration': {
                'idle_timeout_minutes': self.idle_timeout_minutes,
                'discovery_cycle_interval_seconds': self.discovery_cycle_interval_seconds
            }
        }

    async def watchdog_check_discovery(self):
        """Watchdog to ensure discovery keeps running - auto-restart if stopped or hung."""
        logger.info("🐕 Watchdog started - monitoring discovery loop health with hang detection")

        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds

                # Check for hang detection
                if self.hang_detection_enabled:
                    time_since_last_cycle = (datetime.now() - self.last_cycle_complete_time).total_seconds()

                    if time_since_last_cycle > self.cycle_timeout_seconds:
                        logger.warning(f"⚠️ Potential hang detected - no cycle completion for {time_since_last_cycle:.0f}s (timeout: {self.cycle_timeout_seconds}s)")
                        self.consecutive_hangs += 1

                        if self.consecutive_hangs >= self.max_consecutive_hangs:
                            logger.error(f"❌ Too many consecutive hangs ({self.consecutive_hangs}) - forcing restart")
                            # Force restart by cancelling current task
                            if self.discovery_task and not self.discovery_task.done():
                                self.discovery_task.cancel()
                                try:
                                    await self.discovery_task
                                except asyncio.CancelledError:
                                    logger.info("✅ Hung discovery task cancelled")
                            # Restart discovery WITHOUT creating new watchdog
                            logger.info("🔄 Restarting discovery after hang")
                            self.discovery_task = asyncio.create_task(self._discovery_loop())
                            self.consecutive_hangs = 0
                        else:
                            logger.warning(f"⚠️ Hang {self.consecutive_hangs}/{self.max_consecutive_hangs} - monitoring")

                # Check if discovery task is still running
                if self.discovery_task is None or self.discovery_task.done():
                    logger.warning("⚠️ Discovery task stopped - attempting auto-restart")

                    # Check if we're not in user task mode
                    if self.state != SystemState.USER_TASK:
                        logger.info("🔄 Auto-restarting continuous discovery")
                        # Cancel existing discovery task if needed
                        if self.discovery_task and not self.discovery_task.done():
                            self.discovery_task.cancel()
                        # Restart discovery WITHOUT creating new watchdog
                        self.discovery_task = asyncio.create_task(self._discovery_loop())
                        logger.info("✅ Discovery restarted successfully")
                    else:
                        logger.debug("🎯 Discovery paused due to user task - will resume when task completes")
                else:
                    # Discovery is running normally
                    logger.debug(f"✅ Discovery healthy (last cycle: {(datetime.now() - self.last_cycle_complete_time).total_seconds():.0f}s ago)")

            except Exception as e:
                logger.error(f"❌ Watchdog error: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait longer on watchdog errors

    async def _run_monitoring_cycle(self):
        """Run strategy monitoring cycle and auto-upgrade qualifying strategies."""
        try:
            from slate_core.intelligence.strategy_monitor import get_strategy_monitoring_system

            logger.info("🎯 Running strategy monitoring and auto-upgrade cycle...")

            monitoring_system = get_strategy_monitoring_system()
            strategies = monitoring_system.get_conditional_strategies()

            logger.info(f"🎯 Monitoring {len(strategies)} CONDITIONAL strategies for potential upgrade")

            if not strategies:
                logger.info("✅ No CONDITIONAL strategies to monitor")
                return

            # Track upgrade results
            results = {
                "evaluated": len(strategies),
                "upgraded": 0,
                "kept_conditional": 0,
                "errors": []
            }

            for strategy in strategies:
                strategy_id = strategy['id']
                strategy_name = strategy.get('name', f'Strategy {strategy_id}')

                try:
                    # Evaluate performance
                    evaluation = monitoring_system.evaluate_strategy_performance(strategy_id)

                    if 'error' in evaluation:
                        results["errors"].append({
                            "strategy_id": strategy_id,
                            "strategy_name": strategy_name,
                            "error": evaluation['error']
                        })
                        continue

                    recommendation = evaluation.get('recommendation')
                    upgrade_score = evaluation.get('upgrade_score', 0)

                    logger.debug(f"Strategy {strategy_id} ({strategy_name}): {recommendation} (score: {upgrade_score:.2f})")

                    # Only upgrade if clearly qualified (UPGRADE_TO_DEPLOY recommendation)
                    if recommendation == "UPGRADE_TO_DEPLOY":
                        upgrade_success = monitoring_system.upgrade_strategy_to_deploy(strategy_id)

                        if upgrade_success:
                            results["upgraded"] += 1
                            logger.info(f"✅ Auto-upgraded strategy {strategy_id} ({strategy_name}) to DEPLOY quality")
                            logger.info(f"   Performance: {evaluation.get('total_return_pct', 0):.1f}% return, {evaluation.get('sharpe_ratio', 0):.2f} Sharpe, {evaluation.get('win_rate', 0):.1%} win rate")
                        else:
                            results["errors"].append({
                                "strategy_id": strategy_id,
                                "strategy_name": strategy_name,
                                "error": "Upgrade failed"
                            })
                    else:
                        results["kept_conditional"] += 1
                        logger.debug(f"Strategy {strategy_id} kept CONDITIONAL: {recommendation}")

                except Exception as e:
                    results["errors"].append({
                        "strategy_id": strategy_id,
                        "strategy_name": strategy_name,
                        "error": str(e)
                    })
                    logger.error(f"Error evaluating strategy {strategy_id}: {e}")

            # Log summary
            logger.info("=" * 60)
            logger.info(f"🎯 MONITORING CYCLE COMPLETE")
            logger.info(f"   Evaluated: {results['evaluated']} strategies")
            logger.info(f"   Upgraded: {results['upgraded']} strategies to DEPLOY")
            logger.info(f"   Kept CONDITIONAL: {results['kept_conditional']} strategies")
            if results['errors']:
                logger.warning(f"   Errors: {len(results['errors'])} strategies had evaluation errors")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"❌ Monitoring cycle error: {e}", exc_info=True)


# Global coordinator instance
_coordinator: Optional[StartupCoordinator] = None


def get_startup_coordinator() -> StartupCoordinator:
    """Get the global startup coordinator instance."""
    global _coordinator
    if _coordinator is None:
        _coordinator = StartupCoordinator()
        _coordinator.start()
    return _coordinator


async def initialize_with_discovery() -> StartupCoordinator:
    """
    Initialize coordinator and start discovery loop.

    This should be called from an async context (like FastAPI startup).
    """
    coordinator = get_startup_coordinator()
    await coordinator.start_discovery_loop()
    return coordinator


def auto_start():
    """
    Auto-start SLATE with CONTINUOUS CLOSED-LOOP AI discovery running.

    This should be called when SLATE starts up to ensure
    discovery begins immediately and runs CONTINUOUSLY 24/7.
    Discovery only pauses during active user request execution.
    """
    coordinator = get_startup_coordinator()
    logger.info("🧠 SLATE auto-started with CONTINUOUS CLOSED-LOOP AI discovery (24/7 operation)")
    return coordinator


def record_user_activity():
    """
    Record user activity for automatic pause/resume.

    Call this whenever the user makes a request.
    """
    coordinator = get_startup_coordinator()
    coordinator.record_user_activity()
    logger.debug("User activity recorded")


async def execute_with_discovery_paused(task_func, *args, **kwargs):
    """
    Execute a task with discovery paused.

    Use this for user-specific tasks that should pause discovery.

    Args:
        task_func: Async function to execute
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Result of task function
    """
    coordinator = get_startup_coordinator()
    return await coordinator.execute_user_task(task_func, *args, **kwargs)


async def execute_user_task(task_func, *args, **kwargs):
    """
    Execute a user task with automatic discovery pause/resume.

    This is a convenience function that uses the coordinator to manage
    discovery state during user task execution.
    """
    coordinator = get_startup_coordinator()
    return await coordinator.execute_user_task(task_func, *args, **kwargs)


def get_system_status() -> Dict[str, Any]:
    """Get current system status."""
    coordinator = get_startup_coordinator()
    return coordinator.get_status()


async def ensure_discovery_running():
    """
    Ensure discovery is running - restart if stopped.

    This function should be called periodically to maintain continuous discovery.
    It checks if the discovery loop has stopped and restarts it if needed.
    """
    coordinator = get_startup_coordinator()

    # Check if discovery task is still active
    if coordinator.discovery_task is None or coordinator.discovery_task.done():
        # Only restart if we're not in user task mode
        if coordinator.state != SystemState.USER_TASK:
            logger.info("🔄 Discovery stopped - auto-restarting continuous discovery")
            await coordinator.start_discovery_loop()
            return True
        else:
            logger.debug("🎯 Discovery paused due to user task")
            return False
    else:
        logger.debug("✅ Discovery running normally")
        return False


def check_and_restart_discovery():
    """
    Synchronous wrapper for checking and restarting discovery.

    This can be called from non-async contexts to trigger a discovery check.
    """
    try:
        # Get event loop and schedule the check
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Schedule the coroutine to run
            asyncio.create_task(ensure_discovery_running())
            return True
        else:
            logger.warning("⚠️ Event loop not running - cannot restart discovery")
            return False
    except Exception as e:
        logger.error(f"❌ Failed to check discovery status: {e}")
        return False


async def force_restart_discovery():
    """
    Force restart discovery regardless of current state.

    This is useful for manual intervention or recovery from severe hangs.
    """
    coordinator = get_startup_coordinator()

    logger.info("🔄 Force restarting discovery...")

    # Cancel existing task if running
    if coordinator.discovery_task and not coordinator.discovery_task.done():
        logger.info("Cancelling existing discovery task...")
        coordinator.discovery_task.cancel()
        try:
            await coordinator.discovery_task
        except asyncio.CancelledError:
            logger.info("✅ Previous discovery task cancelled")

    # Reset state
    coordinator.state = SystemState.AUTO_DISCOVERY
    coordinator.user_requested_pause = False
    coordinator.consecutive_hangs = 0
    coordinator.last_cycle_complete_time = datetime.now()

    # Start fresh discovery loop
    await coordinator.start_discovery_loop()

    logger.info("✅ Discovery force restarted successfully")
    return True