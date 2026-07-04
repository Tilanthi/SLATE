"""
🐜 SWARM INTELLIGENCE STRATEGY DISCOVERY SYSTEM

Multi-agent collective discovery system with stigmergic learning.
Deploy specialized agents that explore different dimensions of strategy space
and communicate through pheromone-like environmental signals.

Core Innovation: Instead of testing historical patterns, swarm discovers
what works in CURRENT market regime through collective intelligence.
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import random
import uuid
from collections import defaultdict

logger = logging.getLogger(__name__)

class RegimeType(Enum):
    """Market regimes with strategy compatibility."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGE_BOUND = "range_bound"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    UNKNOWN = "unknown"

class PheromoneType(Enum):
    """Types of stigmergic signals."""
    DISCOVERY = "discovery"  # Positive: guides toward promising areas
    AVOIDANCE = "avoidance"  # Negative: warns away from failures
    REGIME = "regime"  # Context: shares market regime intelligence
    INNOVATION = "innovation"  # Creative: encourages novel combinations

@dataclass
class PheromoneSignal:
    """Stigmergic signal left by agents in the environment."""
    pheromone_type: PheromoneType
    location: str  # Parameter space coordinates
    strength: float  # 0.0 to 1.0
    source_agent: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    decay_rate: float = 0.05  # Per hour

    def decay(self, hours_passed: float):
        """Decay pheromone strength over time."""
        decay_factor = np.exp(-self.decay_rate * hours_passed)
        self.strength *= decay_factor

    def is_active(self, threshold: float = 0.01) -> bool:
        """Check if pheromone is still active."""
        return self.strength > threshold

@dataclass
class AgentObservation:
    """Observation from a single agent discovery."""
    agent_id: str
    agent_type: str
    strategy_params: Dict[str, Any]
    result: Dict[str, Any]
    timestamp: datetime
    regime_context: RegimeType

class SwarmIntelligenceCoordinator:
    """
    Central coordinator for swarm intelligence discovery.

    Manages multi-agent exploration, stigmergic communication,
    and collective learning across specialized discovery agents.
    """

    def __init__(self):
        self.agents: Dict[str, 'DiscoveryAgent'] = {}
        self.pheromone_map: List[PheromoneSignal] = []
        self.collective_memory: List[AgentObservation] = []
        self.regime_history: List[RegimeType] = []
        self.discovery_results: List[Dict] = []

        # Performance tracking
        self.total_agent_cycles = 0
        self.collective_success_rate = 0.0
        self.swarm_efficiency_gain = 1.0

        logger.info("Swarm Intelligence Coordinator initialized")

    async def register_agent(self, agent: 'DiscoveryAgent'):
        """Register a new discovery agent in the swarm."""
        self.agents[agent.agent_id] = agent
        logger.info(f"Agent registered: {agent.agent_id} ({agent.agent_type})")

    async def deploy_swarm(self, num_agents: int = 30) -> Dict[str, Any]:
        """
        Deploy a complete swarm of specialized discovery agents.
        """
        logger.info(f"🐜 Deploying swarm of {num_agents} agents...")

        # Agent type distribution
        agent_distribution = {
            'regime_detector': 5,
            'pattern_discoverer': 10,
            'parameter_explorer': 30,
            'cross_timeframe_analyst': 8,
            'experimental_strategist': 10
        }

        deployed_agents = []
        for agent_type, count in agent_distribution.items():
            for i in range(count):
                agent = DiscoveryAgent(
                    agent_id=f"{agent_type}_{i}",
                    agent_type=agent_type,
                    coordinator=self
                )
                await self.register_agent(agent)
                deployed_agents.append(agent)

        logger.info(f"✅ Swarm deployed: {len(deployed_agents)} agents")
        return {
            'status': 'success',
            'agents_deployed': len(deployed_agents),
            'agent_distribution': agent_distribution
        }

    async def run_collective_discovery_cycle(self, market_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Run one collective discovery cycle with all swarm agents.
        """
        logger.info("🧠 Starting collective swarm discovery cycle...")
        cycle_start = datetime.now()

        # Phase 1: Regime Detection
        current_regime = await self._detect_regime_consensus(market_data)
        self.regime_history.append(current_regime)
        logger.info(f"📊 Regime detected: {current_regime.value}")

        # Phase 2: Parallel Agent Exploration
        agent_tasks = []
        for agent in self.agents.values():
            task = agent.explore_and_report(market_data, current_regime)
            agent_tasks.append(task)

        # Run all agents in parallel
        agent_results = await asyncio.gather(*agent_tasks, return_exceptions=True)

        # Phase 3: Collective Intelligence Synthesis
        successful_results = [r for r in agent_results if isinstance(r, dict) and not r.get('error')]
        collective_intelligence = await self._synthesize_collective_intelligence(successful_results)

        # Phase 4: Pheromone Map Updates
        await self._update_pheromone_map(successful_results, current_regime)

        # Phase 5: Emergent Strategy Discovery
        emergent_strategies = await self._discover_emergent_strategies(collective_intelligence)

        cycle_duration = (datetime.now() - cycle_start).total_seconds()

        logger.info(f"✅ Swarm cycle complete: {len(successful_results)} agent results, {cycle_duration:.1f}s")

        return {
            'status': 'success',
            'current_regime': current_regime.value,
            'agents_active': len(self.agents),
            'successful_results': len(successful_results),
            'collective_intelligence': collective_intelligence,
            'emergent_strategies': len(emergent_strategies),
            'cycle_duration_seconds': cycle_duration
        }

    async def _detect_regime_consensus(self, market_data: pd.DataFrame) -> RegimeType:
        """Detect market regime through consensus of regime-detection agents."""
        regime_votes = []

        # Get votes from regime detection agents
        for agent in self.agents.values():
            if agent.agent_type == 'regime_detector':
                regime_assessment = await agent.assess_market_regime(market_data)
                regime_votes.append(regime_assessment)

        # Consensus through majority voting
        if not regime_votes:
            return RegimeType.UNKNOWN

        from collections import Counter
        regime_counts = Counter(regime_votes)
        consensus_regime = regime_counts.most_common(1)[0][0]

        return consensus_regime

    async def _synthesize_collective_intelligence(self, agent_results: List[Dict]) -> Dict[str, Any]:
        """Synthesize collective intelligence from all agent discoveries."""
        collective_intelligence = {
            'successful_patterns': [],
            'parameter_hotspots': [],
            'regime_compatibility': {},
            'cross_agent_correlations': [],
            'quality_distribution': []
        }

        for result in agent_results:
            if result.get('success') and result.get('quality_score', 0) > 0.3:
                collective_intelligence['successful_patterns'].append(result)

        return collective_intelligence

    async def _update_pheromone_map(self, agent_results: List[Dict], current_regime: RegimeType):
        """Update pheromone map based on collective agent discoveries."""
        for result in agent_results:
            if result.get('success'):
                # Leave discovery pheromone for successful strategies
                pheromone = PheromoneSignal(
                    pheromone_type=PheromoneType.DISCOVERY,
                    location=str(result.get('parameters', {})),
                    strength=result.get('quality_score', 0.5),
                    source_agent=result.get('agent_id', 'unknown'),
                    timestamp=datetime.now(),
                    metadata={'regime': current_regime.value}
                )
                self.pheromone_map.append(pheromone)

        # Clean up old pheromones
        current_time = datetime.now()
        active_pheromones = []
        for pheromone in self.pheromone_map:
            hours_passed = (current_time - pheromone.timestamp).total_seconds() / 3600
            pheromone.decay(hours_passed)
            if pheromone.is_active():
                active_pheromones.append(pheromone)

        self.pheromone_map = active_pheromones

    async def _discover_emergent_strategies(self, collective_intelligence: Dict) -> List[Dict]:
        """Discover emergent strategies from collective intelligence."""
        emergent_strategies = []

        # Look for convergent patterns across multiple agent types
        pattern_clusters = self._find_pattern_convergence(collective_intelligence['successful_patterns'])

        # Generate hybrid strategies from convergence hotspots
        for cluster in pattern_clusters:
            if len(cluster) >= 3:  # At least 3 agents found similar patterns
                hybrid_strategy = await self._synthesize_hybrid_strategy(cluster)
                emergent_strategies.append(hybrid_strategy)

        return emergent_strategies

    def _find_pattern_convergence(self, patterns: List[Dict]) -> List[List[Dict]]:
        """Find clusters of similar patterns across different agents."""
        # Simple clustering based on parameter similarity
        clusters = []

        for pattern in patterns:
            placed = False
            for cluster in clusters:
                if self._patterns_similar(cluster[0], pattern):
                    cluster.append(pattern)
                    placed = True
                    break

            if not placed:
                clusters.append([pattern])

        return clusters

    def _patterns_similar(self, pattern1: Dict, pattern2: Dict, threshold: float = 0.3) -> bool:
        """Check if two patterns are similar enough to be in same cluster."""
        params1 = pattern1.get('parameters', {})
        params2 = pattern2.get('parameters', {})

        # Calculate parameter similarity
        param_keys = set(params1.keys()) & set(params2.keys())
        if not param_keys:
            return False

        similarities = []
        for key in param_keys:
            val1, val2 = params1[key], params2[key]
            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                similarity = 1.0 - abs(val1 - val2) / max(abs(val1), abs(val2), 1)
                similarities.append(similarity)

        if not similarities:
            return False

        avg_similarity = np.mean(similarities)
        return avg_similarity >= threshold

    async def _synthesize_hybrid_strategy(self, cluster: List[Dict]) -> Dict:
        """Synthesize a hybrid strategy from convergent patterns."""
        # Average parameters from cluster
        param_sums = defaultdict(list)
        for pattern in cluster:
            for key, value in pattern.get('parameters', {}).items():
                if isinstance(value, (int, float)):
                    param_sums[key].append(value)

        hybrid_params = {}
        for key, values in param_sums.items():
            hybrid_params[key] = np.mean(values)

        return {
            'strategy_type': 'emergent_hybrid',
            'parameters': hybrid_params,
            'cluster_size': len(cluster),
            'agent_diversity': len(set(p.get('agent_type') for p in cluster)),
            'quality_score': np.mean([p.get('quality_score', 0.5) for p in cluster])
        }

class DiscoveryAgent:
    """
    Individual discovery agent with specialized exploration behavior.
    """

    def __init__(self, agent_id: str, agent_type: str, coordinator: SwarmIntelligenceCoordinator):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.coordinator = coordinator
        self.exploration_history = []
        self.success_rate = 0.0

    async def explore_and_report(self, market_data: pd.DataFrame, current_regime: RegimeType) -> Dict[str, Any]:
        """Explore strategy space and report findings."""
        try:
            # Generate strategy based on agent type and current regime
            strategy = await self._generate_regime_aware_strategy(current_regime)

            # Test strategy (simulated - in real implementation, actual backtest)
            result = await self._test_strategy(market_data, strategy)

            # Generate report
            report = {
                'agent_id': self.agent_id,
                'agent_type': self.agent_type,
                'success': result.get('profitable', False),
                'quality_score': result.get('quality_score', 0.0),
                'parameters': strategy,
                'regime_context': current_regime.value,
                'timestamp': datetime.now().isoformat()
            }

            return report

        except Exception as e:
            logger.error(f"Agent {self.agent_id} error: {e}")
            return {
                'agent_id': self.agent_id,
                'error': str(e),
                'success': False
            }

    async def assess_market_regime(self, market_data: pd.DataFrame) -> RegimeType:
        """Assess current market regime (for regime detection agents)."""
        if self.agent_type != 'regime_detector':
            return RegimeType.UNKNOWN

        # Simple regime detection logic (to be enhanced)
        returns = market_data['close'].pct_change().dropna()

        # Detect trend
        avg_return = returns.mean()
        volatility = returns.std()

        if avg_return > 0.001:
            return RegimeType.TRENDING_UP
        elif avg_return < -0.001:
            return RegimeType.TRENDING_DOWN
        elif volatility > 0.03:
            return RegimeType.HIGH_VOLATILITY
        else:
            return RegimeType.RANGE_BOUND

    async def _generate_regime_aware_strategy(self, current_regime: RegimeType) -> Dict[str, Any]:
        """Generate strategy optimized for current regime."""
        # Check pheromone map for guidance
        nearby_pheromones = self._get_nearby_pheromones()

        if nearby_pheromones:
            # Guided exploration based on pheromones
            return self._generate_pheromone_guided_strategy(nearby_pheromones, current_regime)
        else:
            # Baseline exploration for this agent type
            return self._generate_baseline_strategy(current_regime)

    def _get_nearby_pheromones(self) -> List[PheromoneSignal]:
        """Get pheromone signals near agent's current exploration area."""
        # Simplified - in real implementation, use spatial indexing
        return [p for p in self.coordinator.pheromone_map if p.strength > 0.1]

    def _generate_pheromone_guided_strategy(self, pheromones: List[PheromoneSignal], regime: RegimeType) -> Dict[str, Any]:
        """Generate strategy guided by nearby pheromones."""
        # Explore near successful strategies
        base_params = eval(pheromones[0].location)  # Base on successful strategy

        # Add small perturbations for local exploration
        strategy = {}
        for key, value in base_params.items():
            if isinstance(value, (int, float)):
                perturbation = random.uniform(-0.1, 0.1) * value
                strategy[key] = value + perturbation
            else:
                strategy[key] = value

        return strategy

    def _generate_baseline_strategy(self, regime: RegimeType) -> Dict[str, Any]:
        """Generate baseline strategy based on agent type and regime."""
        # Regime-specific parameter generation
        if regime == RegimeType.TRENDING_UP:
            return {
                'fast_period': random.randint(12, 20),
                'slow_period': random.randint(40, 60),
                'signal_threshold': random.uniform(0.4, 0.8),
                'position_size': random.uniform(0.025, 0.035)
            }
        elif regime == RegimeType.HIGH_VOLATILITY:
            return {
                'fast_period': random.randint(8, 15),
                'slow_period': random.randint(30, 50),
                'signal_threshold': random.uniform(0.5, 1.0),
                'position_size': random.uniform(0.02, 0.03)
            }
        else:  # Default/range-bound
            return {
                'fast_period': random.randint(15, 25),
                'slow_period': random.randint(50, 80),
                'signal_threshold': random.uniform(0.3, 0.7),
                'position_size': random.uniform(0.02, 0.04)
            }

    async def _test_strategy(self, market_data: pd.DataFrame, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Test strategy and return results."""
        # Simulated testing - in real implementation, actual backtest
        # For now, return simulated results with some realism

        # Simulate quality based on how "reasonable" parameters are
        quality_score = self._estimate_parameter_quality(strategy)

        # Simulate profitability based on quality
        profitable = quality_score > 0.6 and random.random() < 0.3

        return {
            'profitable': profitable,
            'quality_score': quality_score,
            'expected_return': quality_score * 0.05 if profitable else -0.15,
            'max_drawdown': 0.15 - quality_score * 0.05
        }

    def _estimate_parameter_quality(self, strategy: Dict[str, Any]) -> float:
        """Estimate quality of strategy parameters."""
        quality = 0.5

        # Reward reasonable parameter relationships
        if strategy.get('slow_period', 50) > strategy.get('fast_period', 15):
            quality += 0.2

        # Reward conservative position sizing
        if 0.02 <= strategy.get('position_size', 0.03) <= 0.04:
            quality += 0.2

        # Reward reasonable signal thresholds
        if 0.3 <= strategy.get('signal_threshold', 0.5) <= 1.0:
            quality += 0.1

        return min(quality, 1.0)

# Singleton instance for use across system
_swarm_coordinator: Optional[SwarmIntelligenceCoordinator] = None

def get_swarm_coordinator() -> SwarmIntelligenceCoordinator:
    """Get the singleton swarm coordinator instance."""
    global _swarm_coordinator
    if _swarm_coordinator is None:
        _swarm_coordinator = SwarmIntelligenceCoordinator()
    return _swarm_coordinator