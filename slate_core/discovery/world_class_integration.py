#!/usr/bin/env python3
"""
World-Class Strategy Integration

Integrates the new world-class strategy discovery system with SLATE's infrastructure.
Replaces the broken parameter-tuning approach with proper quantitative strategies.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from slate_core.discovery.world_class_discovery import get_world_class_discovery_engine
from slate_core.discovery.world_class_strategies import MarketRegime

logger = logging.getLogger(__name__)


class WorldClassStrategyIntegration:
    """
    Integration layer for world-class strategy discovery.

    Replaces the old swarm-based parameter tuning with proper
    quantitative trading strategies based on proven principles.
    """

    def __init__(self):
        self.discovery_engine = get_world_class_discovery_engine()
        self.is_initialized = False
        self.discovery_running = False
        self.cycle_count = 0

    async def initialize(self) -> Dict[str, Any]:
        """Initialize the world-class strategy integration"""
        try:
            logger.info("🚀 Initializing World-Class Strategy Integration...")
            logger.info("Replacing broken parameter-tuning with proper quantitative strategies")

            self.is_initialized = True

            return {
                'status': 'success',
                'message': 'World-class strategy integration initialized',
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to initialize world-class integration: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }

    async def run_world_class_discovery_cycle(self) -> Dict[str, Any]:
        """
        Run a world-class discovery cycle with proper validation.
        """
        if not self.is_initialized:
            return {
                'status': 'error',
                'message': 'World-class integration not initialized'
            }

        logger.info("🧠 Running world-class strategy discovery cycle...")

        try:
            self.discovery_running = True
            self.cycle_count += 1

            # Run discovery cycle
            result = self.discovery_engine.run_discovery_cycle()

            self.discovery_running = False

            logger.info(f"✅ World-class discovery cycle {self.cycle_count} complete")

            return {
                'status': 'success',
                'cycle_number': self.cycle_count,
                'discovery_result': result,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"World-class discovery cycle failed: {e}")
            self.discovery_running = False

            return {
                'status': 'error',
                'message': str(e)
            }

    def get_status(self) -> Dict[str, Any]:
        """Get current integration status"""
        return {
            'initialized': self.is_initialized,
            'discovery_running': self.discovery_running,
            'cycle_count': self.cycle_count,
            'approach': 'world_class_quantitative_strategies',
            'principles': [
                'Market regime awareness',
                'Proper risk management',
                'Multiple strategy classes',
                'Proven edge in crypto markets',
                'Robust validation standards'
            ]
        }


# Global instance
_world_class_integration: Optional[WorldClassStrategyIntegration] = None


def get_world_class_integration() -> WorldClassStrategyIntegration:
    """Get the global world-class integration instance"""
    global _world_class_integration
    if _world_class_integration is None:
        _world_class_integration = WorldClassStrategyIntegration()
    return _world_class_integration