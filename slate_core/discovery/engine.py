"""
SLATE Discovery Engine

Orchestrates autonomous strategy discovery cycle.
Uses multiple methods to generate and validate new trading strategies.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field

from .generator import StrategyGenerator
from .evaluator import StrategyEvaluator
from .memory import DiscoveryMemory

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryConfig:
    """Configuration for discovery cycles."""
    methods: List[str] = field(default_factory=lambda: [
        "parameter_variation",
        "signal_combination",
        "regime_specific",
        "ensemble_generation"
    ])
    num_strategies: int = 10
    evaluation_period_days: int = 30
    min_confidence: float = 0.6
    paper_trading_only: bool = True


class DiscoveryEngine:
    """
    Main discovery engine that orchestrates strategy discovery.

    Discovery Methods:
    1. Parameter Variation - Vary parameters of existing strategies
    2. Signal Combination - Combine multiple signals
    3. Regime-Specific - Strategies for different market regimes
    4. Ensemble Generation - Create ensemble strategies
    5. Pattern Recognition - Discover chart patterns
    """

    def __init__(self, config: Optional[DiscoveryConfig] = None):
        self.config = config or DiscoveryConfig()
        self.generator = StrategyGenerator()
        self.evaluator = StrategyEvaluator()
        self.memory = DiscoveryMemory()

        self.active_discoveries: Dict[str, Dict] = {}
        self.discovery_counter = 0

        logger.info("Discovery Engine initialized")

    async def start_discovery_cycle(
        self,
        methods: List[str],
        num_strategies: int = 10,
        evaluation_period: int = 30
    ) -> str:
        """Start a new discovery cycle."""
        self.discovery_counter += 1
        discovery_id = f"discovery_{self.discovery_counter}_{datetime.now().timestamp()}"

        discovery = {
            "id": discovery_id,
            "methods": methods,
            "num_strategies": num_strategies,
            "evaluation_period": evaluation_period,
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "strategies": [],
            "results": {}
        }

        self.active_discoveries[discovery_id] = discovery

        logger.info(f"Starting discovery cycle {discovery_id} with methods: {methods}")

        # Run discovery in background
        asyncio.create_task(self._run_discovery(discovery))

        return discovery_id

    async def _run_discovery(self, discovery: Dict):
        """Execute the discovery process."""
        try:
            # Phase 1: Generate strategies
            logger.info(f"Discovery {discovery['id']}: Generating strategies...")
            generated = await self.generator.generate_strategies(
                methods=discovery['methods'],
                count=discovery['num_strategies']
            )

            discovery['strategies'] = generated

            # Phase 2: Evaluate strategies
            logger.info(f"Discovery {discovery['id']}: Evaluating strategies...")
            evaluation_results = []

            for strategy in generated:
                result = await self.evaluator.evaluate_strategy(
                    strategy=strategy,
                    evaluation_period_days=discovery['evaluation_period']
                )
                evaluation_results.append(result)

            # Phase 3: Rank and filter
            logger.info(f"Discovery {discovery['id']}: Ranking strategies...")
            ranked_strategies = sorted(
                evaluation_results,
                key=lambda x: x.get('score', 0),
                reverse=True
            )

            # Phase 4: Save to memory
            for result in ranked_strategies:
                if result.get('score', 0) >= self.config.min_confidence:
                    await self.memory.save_strategy(result)

            discovery['results'] = {
                "total_evaluated": len(evaluation_results),
                "passed_threshold": len([r for r in evaluation_results if r.get('score', 0) >= self.config.min_confidence]),
                "best_score": ranked_strategies[0].get('score', 0) if ranked_strategies else 0,
                "top_strategies": ranked_strategies[:5]
            }

            discovery['status'] = 'completed'
            discovery['completed_at'] = datetime.now().isoformat()

            logger.info(f"Discovery {discovery['id']}: Completed. {discovery['results']['passed_threshold']} strategies passed")

        except Exception as e:
            logger.error(f"Discovery {discovery['id']} failed: {e}", exc_info=True)
            discovery['status'] = 'failed'
            discovery['error'] = str(e)

    async def list_discoveries(self) -> List[Dict]:
        """List all discovery cycles."""
        return list(self.active_discoveries.values())

    async def get_discovery(self, discovery_id: str) -> Optional[Dict]:
        """Get discovery cycle details."""
        return self.active_discoveries.get(discovery_id)

    async def list_discovered_strategies(self) -> List[Dict]:
        """List all discovered strategies from memory."""
        return await self.memory.list_strategies()

    async def get_summary(self) -> Dict:
        """Get discovery statistics summary."""
        strategies = await self.memory.list_strategies()

        return {
            "total_discoveries": self.discovery_counter,
            "total_strategies": len(strategies),
            "active_discoveries": len([d for d in self.active_discoveries.values() if d['status'] == 'running']),
            "by_method": await self.memory.get_stats_by_method(),
            "by_regime": await self.memory.get_stats_by_regime(),
            "generated_at": datetime.now().isoformat()
        }

    async def get_strategy(self, strategy_id: str) -> Optional[Dict]:
        """Get discovered strategy details."""
        return await self.memory.get_strategy(strategy_id)

    async def validate_strategy(self, strategy_id: str) -> Dict:
        """Validate a discovered strategy."""
        strategy = await self.memory.get_strategy(strategy_id)
        if not strategy:
            return {'valid': False, 'error': 'Strategy not found'}

        # Re-evaluate the strategy
        result = await self.evaluator.evaluate_strategy(
            strategy=strategy,
            evaluation_period_days=7  # Quick validation
        )

        return result

    async def approve_strategy(self, strategy_id: str) -> Dict:
        """Approve a discovered strategy for paper trading."""
        strategy = await self.memory.get_strategy(strategy_id)
        if not strategy:
            raise ValueError(f"Strategy {strategy_id} not found")

        await self.memory.update_strategy_status(strategy_id, "approved")
        logger.info(f"Strategy {strategy_id} approved for paper trading")

        return strategy

    async def reject_strategy(self, strategy_id: str):
        """Reject and remove a discovered strategy."""
        await self.memory.delete_strategy(strategy_id)
        logger.info(f"Strategy {strategy_id} rejected and removed")
