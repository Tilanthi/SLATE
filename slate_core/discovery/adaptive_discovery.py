#!/usr/bin/env python3
"""
SLATE Adaptive Discovery System

Integrates adaptive learning with the discovery system for intelligent
resource allocation balancing exploration and exploitation.
"""

import asyncio
import logging
import random
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass

from .adaptive_learning import get_adaptive_learning_engine, AdaptiveLearningEngine
from .realistic_backtester import StrategyGenerator

logger = logging.getLogger(__name__)


@dataclass
class AdaptiveDiscoveryConfig:
    """Configuration for adaptive discovery system."""
    cycles_per_analysis: int = 50  # Run analysis every N cycles
    exploitation_ratio: float = 0.75  # 75% focus on profitable areas
    min_exploration_budget: float = 0.05  # 5% minimum for all areas
    use_learned_parameters: bool = True  # Use successful parameter ranges
    regime_aware: bool = True  # Adjust for regime changes


class AdaptiveStrategyGenerator(StrategyGenerator):
    """
    Enhanced strategy generator that uses adaptive learning.

    Allocates discovery cycles intelligently:
    - Focuses on profitable strategy types/parameters (exploitation)
    - Maintains exploration coverage of all areas
    - Adapts to regime changes
    """

    def __init__(self, config: AdaptiveDiscoveryConfig = None):
        super().__init__()
        self.config = config or AdaptiveDiscoveryConfig()

        # Initialize adaptive learning engine
        self.learning_engine = get_adaptive_learning_engine(
            exploitation_ratio=self.config.exploitation_ratio,
            min_exploration_budget=self.config.min_exploration_budget
        )

        # Tracking
        self.cycles_since_last_analysis = 0
        self.last_analysis_result = None

        logger.info(
            f"AdaptiveStrategyGenerator initialized: "
            f"exploitation={self.config.exploitation_ratio:.2%}, "
            f"min_exploration={self.config.min_exploration_budget:.2%}"
        )

    async def generate_adaptive_strategies(
        self,
        count: int,
        coordinator=None
    ) -> List[Dict]:
        """
        Generate strategies using adaptive resource allocation.

        Args:
            count: Total number of strategies to generate
            coordinator: Optional stigmergic coordinator

        Returns:
            List of strategy dictionaries
        """
        # Check if we need to run learning analysis
        if self.cycles_since_last_analysis >= self.config.cycles_per_analysis:
            await self._run_learning_analysis()
            self.cycles_since_last_analysis = 0

        self.cycles_since_last_analysis += 1

        # Get allocation from learning engine
        allocation = self.learning_engine.get_allocation_for_cycle(count)

        logger.info(
            f"Generating {count} strategies with adaptive allocation: "
            f"{len(allocation)} different areas"
        )

        # Generate strategies according to allocation
        strategies = []

        for alloc in allocation:
            strategy_type = alloc['strategy_type']
            timeframe = alloc['timeframe']
            area_count = alloc['count']

            # Log what we're doing
            logger.info(
                f"  Generating {area_count} {strategy_type} @ {timeframe} "
                f"({alloc['allocation_percent']:.1f}% - {alloc['reason']})"
            )

            # Generate strategies for this area
            for i in range(area_count):
                strategy = await self._generate_strategy_for_area(
                    strategy_type, timeframe, i
                )
                strategies.append(strategy)

        # Fill any gaps if we didn't generate enough
        while len(strategies) < count:
            # Generate random strategy as fallback
            strategy = self.generate_strategy()
            strategies.append(strategy)

        return strategies

    async def _generate_strategy_for_area(
        self,
        strategy_type: str,
        timeframe: str,
        index: int
    ) -> Dict:
        """Generate a strategy for a specific area."""
        # Get suggested parameters from learning
        suggested_params = None
        if self.config.use_learned_parameters:
            suggested_params = self.learning_engine.get_suggested_parameters(
                strategy_type, timeframe
            )

        # Generate parameters
        if suggested_params and random.random() < 0.7:  # 70% use learned ranges
            parameters = self._generate_parameters_from_ranges(
                strategy_type, suggested_params
            )
        else:
            parameters = self._generate_parameters(strategy_type)

        # Create strategy
        strategy = {
            'id': f"str_{random.randint(10000, 99999)}",
            'name': f"{strategy_type}_{timeframe}_{index}",
            'type': strategy_type,
            'timeframe': timeframe,
            'parameters': parameters,
            'source': 'adaptive_discovery'
        }

        return strategy

    def _generate_parameters_from_ranges(
        self,
        strategy_type: str,
        param_ranges: Dict[str, Tuple[float, float]]
    ) -> Dict[str, float]:
        """Generate parameters within successful ranges."""
        parameters = {}

        # Get default parameters first
        default_params = self._generate_parameters(strategy_type)

        # Override with learned ranges where available
        for param_name, (min_val, max_val) in param_ranges.items():
            # Generate value within range (uniform distribution)
            value = random.uniform(min_val, max_val)

            # Round to appropriate precision
            if abs(value) > 100:
                value = round(value, 1)
            elif abs(value) > 10:
                value = round(value, 2)
            else:
                value = round(value, 4)

            parameters[param_name] = value

        # Fill in any missing parameters from defaults
        for key, value in default_params.items():
            if key not in parameters:
                parameters[key] = value

        return parameters

    async def _run_learning_analysis(self):
        """Run the adaptive learning analysis."""
        logger.info("Running adaptive learning analysis...")

        try:
            result = await self.learning_engine.analyze_and_learn()
            self.last_analysis_result = result

            logger.info(
                f"Learning analysis complete: "
                f"{len(result.get('allocations', {}))} areas analyzed"
            )

            # Log insights
            insights = result.get('insights', {})
            if insights.get('top_performers'):
                top = insights['top_performers'][0]
                logger.info(
                    f"  Top performer: {top['strategy_type']} @ {top['timeframe']} "
                    f"(Sharpe: {top['avg_sharpe']:.2f})"
                )

            if insights.get('recommendations'):
                for rec in insights['recommendations']:
                    logger.info(f"  Recommendation: {rec}")

            # Check for regime changes
            if self.learning_engine.should_increase_exploration():
                logger.warning("  Regime change detected - increasing exploration")

        except Exception as e:
            logger.error(f"Error during learning analysis: {e}")

    def get_learning_status(self) -> Dict[str, Any]:
        """Get current learning status and allocation."""
        return {
            'cycles_since_analysis': self.cycles_since_last_analysis,
            'last_analysis': self.last_analysis_result,
            'current_allocation': (
                self.learning_engine.resource_allocations
                if self.learning_engine else {}
            ),
            'exploitation_ratio': self.config.exploitation_ratio,
            'min_exploration_budget': self.config.min_exploration_budget
        }

    async def get_discovery_summary(self) -> Dict[str, Any]:
        """Get summary of discovery activity and learning."""
        summary = {
            'config': {
                'cycles_per_analysis': self.config.cycles_per_analysis,
                'exploitation_ratio': self.config.exploitation_ratio,
                'min_exploration_budget': self.config.min_exploration_budget,
                'use_learned_parameters': self.config.use_learned_parameters,
                'regime_aware': self.config.regime_aware
            },
            'learning_status': self.get_learning_status(),
            'performance_summary': (
                self.learning_engine._get_performance_summary()
                if self.learning_engine else {}
            )
        }

        return summary


class AdaptiveContinuousDiscovery:
    """
    Continuous discovery system with adaptive learning.

    Automatically adjusts resource allocation based on performance
    while maintaining exploration coverage.
    """

    def __init__(self, config: AdaptiveDiscoveryConfig = None):
        self.config = config or AdaptiveDiscoveryConfig()
        self.generator = AdaptiveStrategyGenerator(config)
        self.running = False

        logger.info("AdaptiveContinuousDiscovery initialized")

    async def start_discovery(self, cycles: int = 100):
        """Start adaptive discovery cycles."""
        self.running = True
        logger.info(f"Starting adaptive discovery: {cycles} cycles")

        for cycle in range(cycles):
            if not self.running:
                break

            logger.info(f"Adaptive discovery cycle {cycle + 1}/{cycles}")

            # Generate strategies using adaptive allocation
            strategies = await self.generator.generate_adaptive_strategies(
                count=10,  # Generate 10 strategies per cycle
                coordinator=None
            )

            # Log what we generated
            type_counts = {}
            for s in strategies:
                key = f"{s['type']} @ {s['timeframe']}"
                type_counts[key] = type_counts.get(key, 0) + 1

            logger.info(f"  Generated strategies: {type_counts}")

            # In production, these would be backtested here
            # For now, just simulate the cycle
            await asyncio.sleep(0.1)

        logger.info("Adaptive discovery completed")

    def stop_discovery(self):
        """Stop discovery cycles."""
        self.running = False
        logger.info("Adaptive discovery stopped")

    async def get_status(self) -> Dict[str, Any]:
        """Get current status."""
        return await self.generator.get_discovery_summary()
