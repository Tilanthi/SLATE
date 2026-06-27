"""
SLATE - Strategy Learning & Autonomous Trading Engine

Core module for AI-driven autonomous trading strategy discovery system.
"""

__version__ = "2.0.0"
__author__ = "SLATE Development Team"

# Core imports
from .discovery.edge_discovery_engine import EdgeDiscoveryEngine
from .discovery.discovery_memory import get_discovery_memory

__all__ = [
    'EdgeDiscoveryEngine',
    'get_discovery_memory',
    'create_slate_system',
    'auto_start_discovery'
]


def create_slate_system(auto_discovery: bool = True):
    """
    Create and initialize SLATE system with automatic discovery.

    Args:
        auto_discovery: Whether to automatically start discovery (default: True)

    Returns:
        Initialized EdgeDiscoveryEngine ready for use
    """
    engine = EdgeDiscoveryEngine()

    if auto_discovery:
        import asyncio
        # Start discovery in background
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.create_task(engine.run_multi_timeframe_discovery_cycle())

    return engine


async def auto_start_discovery():
    """
    Auto-start discovery cycle - runs continuously in background.

    This is the main entry point for autonomous discovery operations.
    Discovery runs continuously unless paused by user activity.
    """
    engine = EdgeDiscoveryEngine()

    while True:
        try:
            # Run discovery cycle
            results = await engine.run_multi_timeframe_discovery_cycle()

            # Wait before next cycle
            import asyncio
            await asyncio.sleep(5)

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Discovery cycle error: {e}")
            await asyncio.sleep(10)