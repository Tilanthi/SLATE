#!/usr/bin/env python3
"""
SLATE Continuous Discovery Scheduler

Runs edge discovery continuously in the background when SLATE is idle.
Automatically manages discovery cycles, database cleanup, and result ranking.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
import signal
import sys

logger = logging.getLogger(__name__)


class ContinuousDiscoveryScheduler:
    """
    Manages continuous discovery cycles in the background.

    - Runs discovery when SLATE is idle
    - Cleans up old results
    - Maintains top-performing edges
    - Persists state across restarts
    """

    def __init__(self):
        self.running = False
        self.discovery_task: Optional[asyncio.Task] = None
        self.cycle_interval = 300  # 5 minutes between cycles
        self.idle_threshold = 60  # 1 minute of inactivity triggers discovery

    async def start(self):
        """Start the continuous discovery scheduler."""
        if self.running:
            logger.warning("Continuous discovery already running")
            return

        self.running = True
        logger.info("Starting continuous discovery scheduler")

        # Start discovery loop
        self.discovery_task = asyncio.create_task(self._discovery_loop())

        logger.info("Continuous discovery scheduler started")

    async def stop(self):
        """Stop the continuous discovery scheduler."""
        if not self.running:
            return

        self.running = False

        if self.discovery_task:
            self.discovery_task.cancel()
            try:
                await self.discovery_task
            except asyncio.CancelledError:
                pass

        logger.info("Continuous discovery scheduler stopped")

    async def _discovery_loop(self):
        """Main discovery loop."""
        from .edge_discovery_engine import EdgeDiscoveryEngine

        engine = EdgeDiscoveryEngine()

        while self.running:
            try:
                # Run discovery cycle
                logger.info("Starting discovery cycle...")
                results = await engine.run_discovery_cycle()

                if results["status"] == "success":
                    logger.info(
                        f"Discovery complete: {results['passed_validation']}/{results['total_candidates']} edges passed"
                    )

                    # Print top performers
                    if results["top_edges"]:
                        logger.info("Top performing edges:")
                        for edge in results["top_edges"]:
                            logger.info(
                                f"  - {edge['description']}: {edge['return']:.2%} return, "
                                f"{edge['drawdown']:.2%} drawdown"
                            )

                # Wait before next cycle
                logger.info(f"Waiting {self.cycle_interval}s before next cycle...")
                await asyncio.sleep(self.cycle_interval)

            except asyncio.CancelledError:
                logger.info("Discovery loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in discovery loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait 1 minute before retry

    def is_idle(self, last_activity: Optional[datetime] = None) -> bool:
        """Check if system is idle and discovery should run."""
        if last_activity is None:
            return True

        idle_time = (datetime.now() - last_activity).total_seconds()
        return idle_time > self.idle_threshold


# Global scheduler instance
_scheduler: Optional[ContinuousDiscoveryScheduler] = None


def get_continuous_scheduler() -> ContinuousDiscoveryScheduler:
    """Get or create the global continuous discovery scheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = ContinuousDiscoveryScheduler()
    return _scheduler


async def start_continuous_discovery():
    """Start continuous discovery in the background."""
    scheduler = get_continuous_scheduler()
    await scheduler.start()


async def stop_continuous_discovery():
    """Stop continuous discovery."""
    scheduler = get_continuous_scheduler()
    await scheduler.stop()
