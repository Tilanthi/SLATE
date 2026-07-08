#!/usr/bin/env python3
"""
World-Class Discovery Integration for Server Startup

This module provides the integration layer for starting the world-class
discovery system in the SLATE server, replacing the old broken swarm approach.
"""

import asyncio
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Try to import world-class discovery
try:
    from slate_core.discovery.world_class_discovery import get_world_class_discovery_engine
    WORLD_CLASS_AVAILABLE = True
except ImportError:
    WORLD_CLASS_AVAILABLE = False
    logger.warning("World-class discovery not available")

# Global world-class discovery engine
_world_class_discovery_engine = None
_discovery_running = False


async def start_world_class_discovery_loop():
    """
    Start the world-class discovery loop as a background task.

    This replaces the old swarm-based parameter tuning with proper
    quantitative trading strategies.
    """
    global _world_class_discovery_engine, _discovery_running

    if not WORLD_CLASS_AVAILABLE:
        logger.error("World-class discovery not available - cannot start")
        return

    logger.info("🚀 Starting world-class discovery loop...")

    try:
        _world_class_discovery_engine = get_world_class_discovery_engine()
        _discovery_running = True

        # Run discovery cycles every 5 minutes
        while _discovery_running:
            try:
                logger.info("🧠 Running world-class discovery cycle...")
                result = _world_class_discovery_engine.run_discovery_cycle()

                if result.get('status') == 'success':
                    logger.info(f"✅ World-class discovery cycle completed: "
                               f"{result.get('strategies_validated', 0)} strategies validated")
                else:
                    logger.info(f"⚠️  Discovery cycle: {result.get('status')}")

                # Wait 5 minutes before next cycle
                await asyncio.sleep(300)

            except Exception as e:
                logger.error(f"Error in discovery cycle: {e}")
                await asyncio.sleep(60)  # Wait before retry

        logger.info("World-class discovery loop stopped")

    except Exception as e:
        logger.error(f"Failed to start world-class discovery loop: {e}")
        _discovery_running = False


def get_world_class_discovery_status() -> Dict[str, Any]:
    """Get the current status of world-class discovery"""
    return {
        'discovery_running': _discovery_running,
        'world_class_available': WORLD_CLASS_AVAILABLE,
        'system_type': 'world_class_quantitative' if WORLD_CLASS_AVAILABLE else 'unavailable'
    }


async def start_world_class_discovery_on_startup():
    """
    Start world-class discovery on server startup.

    This function should be called from the server startup event
    to initialize the world-class discovery system.
    """
    if not WORLD_CLASS_AVAILABLE:
        logger.warning("World-class discovery not available - using legacy system")
        return

    logger.info("🌟 Starting World-Class Discovery on Server Startup")
    logger.info("Replacing broken swarm parameter tuning with proper quantitative strategies")

    # Start the world-class discovery loop in background
    asyncio.create_task(start_world_class_discovery_loop())

    logger.info("✅ World-class discovery loop started in background")

    return {
        'status': 'success',
        'message': 'World-class discovery started on server startup',
        'timestamp': '2026-07-04T10:43:00'
    }