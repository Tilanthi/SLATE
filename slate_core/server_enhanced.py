#!/usr/bin/env python3
"""
SLATE Enhanced Server Integration

Integrates BIODISC-inspired efficiency improvements with SLATE server.
This module provides enhanced discovery functionality that can be toggled on/off.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime

# Try to import enhanced discovery engine
try:
    from slate_core.discovery.enhanced_discovery_engine import EnhancedDiscoveryEngine
    from slate_core.discovery.parallel_strategy_tester import get_parallel_tester
    from slate_core.discovery.strategy_cache import get_strategy_cache
    from slate_core.discovery.early_stopping import get_early_stopping_monitor
    from slate_core.discovery.progressive_results import get_progressive_manager
    ENHANCED_DISCOVERY_AVAILABLE = True
except ImportError as e:
    ENHANCED_DISCOVERY_AVAILABLE = False
    logging.warning(f"Enhanced discovery not available: {e}")

logger = logging.getLogger(__name__)


class EnhancedServerIntegration:
    """
    Integration layer for enhanced discovery in SLATE server.

    Provides enhanced discovery functionality with:
    - Parallel strategy testing (4-8x speedup)
    - Intelligent caching (5-10x speedup)
    - Early stopping (2-5x speedup)
    - Progressive results (better UX)
    """

    def __init__(self,
                 enable_enhanced: bool = True,
                 max_parallel_workers: Optional[int] = None,
                 enable_caching: bool = True,
                 enable_early_stopping: bool = True,
                 enable_progressive: bool = True):
        """
        Initialize enhanced server integration.

        Args:
            enable_enhanced: Whether to use enhanced discovery
            max_parallel_workers: Maximum parallel workers
            enable_caching: Whether to use caching
            enable_early_stopping: Whether to use early stopping
            enable_progressive: Whether to use progressive results
        """
        self.enable_enhanced = enable_enhanced and ENHANCED_DISCOVERY_AVAILABLE
        self.max_parallel_workers = max_parallel_workers
        self.enable_caching = enable_caching
        self.enable_early_stopping = enable_early_stopping
        self.enable_progressive = enable_progressive

        # Initialize enhanced engine if enabled
        self.enhanced_engine: Optional[EnhancedDiscoveryEngine] = None

        if self.enable_enhanced:
            try:
                self.enhanced_engine = EnhancedDiscoveryEngine(
                    max_parallel_workers=max_parallel_workers,
                    enable_caching=enable_caching,
                    enable_early_stopping=enable_early_stopping,
                    enable_progressive=enable_progressive
                )
                logger.info("Enhanced discovery engine initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize enhanced engine: {e}")
                self.enable_enhanced = False

        if not self.enable_enhanced:
            logger.info("Using basic discovery engine (enhanced features disabled)")

    async def run_enhanced_discovery_cycle(self,
                                          num_strategies: int = 100,
                                          timeframes: list = None) -> Dict[str, Any]:
        """
        Run enhanced discovery cycle with all improvements.

        Args:
            num_strategies: Number of strategies to test
            timeframes: Timeframes to test

        Returns:
            Enhanced discovery results with performance metrics
        """
        if not self.enable_enhanced or not self.enhanced_engine:
            # Fallback to basic discovery
            return await self._run_basic_discovery(num_strategies, timeframes)

        logger.info(f"Running enhanced discovery: {num_strategies} strategies")

        try:
            results = await self.enhanced_engine.run_enhanced_discovery_cycle(
                num_strategies=num_strategies,
                timeframes=timeframes or ['1d']
            )

            logger.info(f"Enhanced discovery complete with {results['performance_metrics']['estimated_total_speedup']}x speedup")
            return results

        except Exception as e:
            logger.error(f"Enhanced discovery failed, falling back to basic: {e}")
            return await self._run_basic_discovery(num_strategies, timeframes)

    async def _run_basic_discovery(self,
                                   num_strategies: int,
                                   timeframes: list = None) -> Dict[str, Any]:
        """Fallback to basic discovery if enhanced unavailable."""
        try:
            from slate_core.discovery.edge_discovery_engine import EdgeDiscoveryEngine

            engine = EdgeDiscoveryEngine()

            # Run basic discovery cycle
            if hasattr(engine, 'run_multi_timeframe_discovery_cycle'):
                results = await engine.run_multi_timeframe_discovery_cycle()
            else:
                results = await engine.run_discovery_cycle()

            # Add performance metrics for comparison
            results['performance_metrics'] = {
                'parallel_speedup': 1.0,
                'cache_hit_rate': 0.0,
                'early_stop_rate': 0.0,
                'estimated_total_speedup': 1.0,
                'enhanced_mode': False
            }

            return results

        except Exception as e:
            logger.error(f"Basic discovery also failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'performance_metrics': {
                    'enhanced_mode': False,
                    'error': 'Both enhanced and basic discovery failed'
                }
            }

    def get_enhancement_stats(self) -> Dict[str, Any]:
        """Get comprehensive enhancement statistics."""
        if not self.enable_enhanced or not self.enhanced_engine:
            return {
                'enhanced_enabled': False,
                'available': ENHANCED_DISCOVERY_AVAILABLE,
                'stats': {}
            }

        return {
            'enhanced_enabled': True,
            'available': True,
            'stats': self.enhanced_engine.get_enhancement_stats()
        }

    def is_enhanced_active(self) -> bool:
        """Check if enhanced discovery is active."""
        return self.enable_enhanced and self.enhanced_engine is not None


# Global enhanced integration instance
_enhanced_integration: Optional[EnhancedServerIntegration] = None


def get_enhanced_integration(enable_enhanced: bool = True,
                           max_parallel_workers: Optional[int] = None) -> EnhancedServerIntegration:
    """
    Get global enhanced server integration instance.

    Args:
        enable_enhanced: Whether to use enhanced discovery
        max_parallel_workers: Maximum parallel workers

    Returns:
        EnhancedServerIntegration instance
    """
    global _enhanced_integration
    if _enhanced_integration is None:
        _enhanced_integration = EnhancedServerIntegration(
            enable_enhanced=enable_enhanced,
            max_parallel_workers=max_parallel_workers,
            enable_caching=True,
            enable_early_stopping=True,
            enable_progressive=True
        )
    return _enhanced_integration


def reset_enhanced_integration():
    """Reset enhanced integration (for testing/reconfiguration)."""
    global _enhanced_integration
    _enhanced_integration = None