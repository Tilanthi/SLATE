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

        # Configuration
        self.idle_timeout_minutes = 0.1  # Resume discovery after 6 seconds of inactivity
        self.discovery_cycle_interval_seconds = 5  # Run discovery every 5 seconds when active

        logger.info("Startup Coordinator initialized")

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

        logger.info("Starting discovery loop in background...")
        self.discovery_task = asyncio.create_task(self._discovery_loop())
        logger.info("Discovery loop started successfully")

        # Start watchdog to monitor and auto-restart if needed
        logger.info("🐕 Starting discovery watchdog...")
        asyncio.create_task(self.watchdog_check_discovery())

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

                try:
                    # Load market data for discovery
                    import pandas as pd

                    # Load JSON data and set timestamp as index
                    df = pd.read_json('sol_data_cache/SOLUSDT_perpetual_1d_12m.csv')
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df.set_index('timestamp', inplace=True)

                    logger.info(f"✅ Market data loaded: {len(df)} days")

                    # Run closed-loop AI discovery cycle
                    results = self.closed_loop_system.run_enhanced_discovery_cycle(df)

                    if results.get('status') == 'success':
                        performance = results.get('performance', {})
                        discovery = results.get('discovery', {})

                        hypotheses = performance.get('hypotheses_generated', 0)
                        strategies = performance.get('strategies_generated', 0)
                        validated = performance.get('total_validated', 0)
                        success_rate = performance.get('overall_success_rate', 0)

                        logger.info(f"✅ Closed-Loop AI cycle: {hypotheses} hypotheses, {strategies} strategies, {validated} validated, {success_rate:.1%} success")

                        # Reset error counter on success
                        consecutive_errors = 0
                    else:
                        logger.warning(f"⚠️  Closed-loop discovery issue: {results.get('message', 'Unknown error')}")
                        consecutive_errors += 1

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
        """Watchdog to ensure discovery keeps running - auto-restart if stopped."""
        logger.info("🐕 Watchdog started - monitoring discovery loop health")

        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds

                # Check if discovery task is still running
                if self.discovery_task is None or self.discovery_task.done():
                    logger.warning("⚠️ Discovery task stopped - attempting auto-restart")

                    # Check if we're not in user task mode
                    if self.state != SystemState.USER_TASK:
                        logger.info("🔄 Auto-restarting continuous discovery")
                        await self.start_discovery_loop()
                    else:
                        logger.debug("🎯 Discovery paused due to user task - will resume when task completes")

            except Exception as e:
                logger.error(f"❌ Watchdog error: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait longer on watchdog errors


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