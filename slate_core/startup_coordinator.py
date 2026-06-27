#!/usr/bin/env python3
"""
SLATE Startup Coordinator - Automatic Discovery Management

This module ensures SLATE always starts with discovery running automatically,
and manages pausing/resuming based on user activity.

Core Principles:
1. Discovery starts immediately on SLATE startup
2. Discovery runs continuously unless user requests specific tasks
3. User activity automatically pauses discovery
4. Discovery resumes after 5 minutes of user inactivity
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
    - User requests pause discovery automatically
    - Discovery resumes after user activity stops
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
        self.idle_timeout_minutes = 5
        self.discovery_cycle_interval_seconds = 5

        logger.info("Startup Coordinator initialized")

    def start(self):
        """Start SLATE with automatic discovery."""
        logger.info("=" * 70)
        logger.info("SLATE STARTING WITH AUTOMATIC DISCOVERY")
        logger.info("=" * 70)
        logger.info(f"Startup time: {datetime.now().isoformat()}")
        logger.info(f"Initial state: {self.state.value}")
        logger.info("Discovery will start immediately and run continuously")
        logger.info("User activity will automatically pause discovery")
        logger.info("=" * 70)

        # Initialize discovery engine (but don't start loop yet)
        try:
            from .discovery.edge_discovery_engine import EdgeDiscoveryEngine
            self.discovery_engine = EdgeDiscoveryEngine()
            logger.info("Discovery engine initialized")
            self.startup_complete = True
        except Exception as e:
            logger.error(f"Failed to initialize discovery engine: {e}", exc_info=True)

    async def start_discovery_loop(self):
        """Start the discovery loop - must be called from async context."""
        if not self.discovery_engine:
            logger.error("Cannot start discovery loop - engine not initialized")
            return

        logger.info("Starting discovery loop in background...")
        self.discovery_task = asyncio.create_task(self._discovery_loop())
        logger.info("Discovery loop started successfully")

    def record_user_activity(self):
        """
        Record user activity (API call, query, task request).

        This automatically pauses discovery and resets idle timer.
        Call this whenever the user interacts with SLATE.
        """
        self.last_user_activity = datetime.now()
        logger.info(f"User activity recorded at {self.last_user_activity.isoformat()}")

        if self.state == SystemState.AUTO_DISCOVERY:
            logger.info("User activity detected - pausing automatic discovery")
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
        """Main discovery loop - runs continuously unless paused."""
        logger.info("Discovery loop started - will run continuously")

        while True:
            try:
                # Check if we should be paused
                if self.state == SystemState.USER_TASK or self.user_requested_pause:
                    logger.debug("Discovery paused - waiting for resume condition")
                    await asyncio.sleep(10)
                    await self._check_resume_discovery()
                    continue

                # Check idle time
                idle_time = (datetime.now() - self.last_user_activity).total_seconds()
                if idle_time < (self.idle_timeout_minutes * 60):
                    logger.debug(f"User active ({idle_time:.0f}s idle) - waiting")
                    await asyncio.sleep(10)
                    continue

                # Clear to run discovery
                if self.state != SystemState.AUTO_DISCOVERY:
                    logger.info("Resuming automatic discovery")
                    self.state = SystemState.AUTO_DISCOVERY

                # Run one discovery cycle
                logger.info("Starting discovery cycle...")
                results = await self.discovery_engine.run_multi_timeframe_discovery_cycle()

                # Log results
                total_tests = results.get('total_strategies_tested', 0)
                profitable = results.get('profitable_strategies', 0)
                logger.info(f"Discovery cycle complete: {total_tests} tests, {profitable} profitable")

                # Wait before next cycle
                await asyncio.sleep(self.discovery_cycle_interval_seconds)

            except Exception as e:
                logger.error(f"Discovery loop error: {e}", exc_info=True)
                await asyncio.sleep(30)  # Wait before retry

    async def _check_resume_discovery(self):
        """Check if we should resume discovery after user activity."""
        idle_time = (datetime.now() - self.last_user_activity).total_seconds()
        idle_timeout = self.idle_timeout_minutes * 60

        if idle_time >= idle_timeout and self.user_requested_pause:
            logger.info(f"User idle for {idle_time/60:.1f} minutes - resuming discovery")
            self.user_requested_pause = False
            self.state = SystemState.AUTO_DISCOVERY
        else:
            logger.debug(f"User still active (idle for {idle_time:.0f}s)")

    def get_status(self) -> Dict[str, Any]:
        """Get current system status."""
        idle_time = (datetime.now() - self.last_user_activity).total_seconds()

        return {
            'state': self.state.value,
            'startup_complete': self.startup_complete,
            'discovery_running': self.state == SystemState.AUTO_DISCOVERY,
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
    Auto-start SLATE with discovery running.

    This should be called when SLATE starts up to ensure
    discovery begins immediately and runs continuously.
    """
    coordinator = get_startup_coordinator()
    logger.info("SLATE auto-started with continuous discovery")
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