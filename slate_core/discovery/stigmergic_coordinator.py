"""
SLATE Stigmergic Coordinator

Real-time coordination system for SLATE discovery that implements:
1. Redundancy avoidance: Don't test similar strategies simultaneously
2. Emergent specialization: Focus on promising strategy types
3. Dynamic prioritization: Adapt based on collective discoveries

This transforms SLATE from parallel processing to true collective intelligence.
"""

import asyncio
import logging
import time
import hashlib
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


@dataclass
class ActiveTest:
    """Represents a strategy currently being tested."""
    strategy_id: str
    strategy_type: str
    params_hash: str
    start_time: float
    priority: float = 1.0


@dataclass
class PheromoneTrail:
    """Represents a discovery signal (pheromone) deposited in the environment."""
    strategy_type: str
    signal_strength: float  # Sharpe ratio or similar metric
    parameters_hash: str
    timestamp: float
    discovered_by: str  # Which discovery method found it
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyPerformance:
    """Tracks collective performance by strategy type."""
    strategy_type: str
    total_tests: int = 0
    successful_tests: int = 0
    avg_sharpe: float = 0.0
    best_sharpe: float = 0.0
    recent_results: List[float] = field(default_factory=list)
    success_rate: float = 0.0
    last_updated: float = field(default_factory=time.time)

    def add_result(self, sharpe_ratio: float):
        """Add a new result and update statistics."""
        self.total_tests += 1
        self.recent_results.append(sharpe_ratio)

        # Keep only recent results (last 100)
        if len(self.recent_results) > 100:
            self.recent_results.pop(0)

        # Update success rate (sharpe > 0.5 considered success)
        if sharpe_ratio > 0.5:
            self.successful_tests += 1

        self.success_rate = self.successful_tests / self.total_tests
        self.avg_sharpe = sum(self.recent_results) / len(self.recent_results)
        self.best_sharpe = max(self.best_sharpe, sharpe_ratio)
        self.last_updated = time.time()


class StigmergicCoordinator:
    """
    Coordinates strategy discovery and testing using stigmergic principles.

    Acts as the collective intelligence layer that enables SLATE to behave
    as a coordinated system rather than independent parallel processes.
    """

    def __init__(self):
        # Active testing tracking
        self.active_tests: Dict[str, ActiveTest] = {}
        self.max_concurrent_tests = 20

        # Pheromone trails (signals in the environment)
        self.pheromone_trails: Dict[str, PheromoneTrail] = {}
        self.trail_retention_hours = 24  # Keep trails for 24 hours

        # Performance tracking by strategy type
        self.strategy_performance: Dict[str, StrategyPerformance] = {}

        # Redundancy tracking
        self.parameter_cache: Dict[str, Set[str]] = defaultdict(set)
        self.similarity_threshold = 0.85  # 85% similarity considered redundant

        # Dynamic priorities
        self.strategy_priorities: Dict[str, float] = {}
        self.priority_decay_rate = 0.95  # Decay priority by 5% each hour

        # Specialization tracking
        self.emergent_specializations: Dict[str, float] = {}
        self.last_specialization_update = 0.0

        # Statistics
        self.redundancy_avoided = 0
        self.dynamic_focus_changes = 0
        self.total_coordinations = 0

        logger.info("Stigmergic Coordinator initialized")

    def _hash_parameters(self, parameters: Dict) -> str:
        """Create a hash of parameters for similarity checking."""
        # Sort parameters for consistent hashing
        param_str = json.dumps(parameters, sort_keys=True)
        return hashlib.md5(param_str.encode()).hexdigest()[:8]

    def _calculate_similarity(self, params1: Dict, params2: Dict) -> float:
        """Calculate similarity between two parameter sets."""
        if not params1 or not params2:
            return 0.0

        # Jaccard similarity of parameter keys and values
        keys1 = set(params1.keys())
        keys2 = set(params2.keys())

        if not keys1 or not keys2:
            return 0.0

        # Key similarity
        key_intersection = len(keys1 & keys2)
        key_union = len(keys1 | keys2)
        key_sim = key_intersection / key_union if key_union > 0 else 0

        # Value similarity for common keys
        value_similarities = []
        for key in keys1 & keys2:
            val1 = params1[key]
            val2 = params2[key]
            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                # Normalize and compare
                if val1 == val2:
                    value_similarities.append(1.0)
                else:
                    # Relative difference
                    diff = abs(val1 - val2) / max(abs(val1), abs(val2), 1.0)
                    value_similarities.append(1.0 - diff)
            elif val1 == val2:
                value_similarities.append(1.0)

        value_sim = sum(value_similarities) / len(value_similarities) if value_similarities else 0.5

        # Combined similarity (70% keys, 30% values)
        return 0.7 * key_sim + 0.3 * value_sim

    async def can_test_strategy(self, strategy_id: str, strategy_type: str,
                              parameters: Dict) -> Tuple[bool, str]:
        """
        Check if strategy can be tested (redundancy avoidance).

        Returns (can_test, reason)
        """
        params_hash = self._hash_parameters(parameters)

        # Check if similar strategy is currently being tested
        for active_test in self.active_tests.values():
            if active_test.strategy_type == strategy_type:
                # Check parameter cache for similarity
                for cached_hash in self.parameter_cache.get(strategy_type, set()):
                    if cached_hash == params_hash:
                        return False, f"Currently testing {strategy_type} with identical parameters"

                    # Calculate similarity if not already cached
                    cached_params = self._get_cached_parameters(strategy_type, cached_hash)
                    if cached_params:
                        similarity = self._calculate_similarity(parameters, cached_params)
                        if similarity > self.similarity_threshold:
                            self.redundancy_avoided += 1
                            return False, f"Too similar ({similarity:.1%}) to currently testing {strategy_type}"

        # Check capacity
        if len(self.active_tests) >= self.max_concurrent_tests:
            return False, f"At maximum capacity ({self.max_concurrent_tests} concurrent tests)"

        # Check dynamic priority (avoid low-priority strategies)
        priority = self.strategy_priorities.get(strategy_type, 1.0)
        if priority < 0.1:  # Very low priority
            # But allow it if not much else is being tested
            if len(self.active_tests) > self.max_concurrent_tests * 0.8:
                return False, f"Strategy type {strategy_type} has low priority ({priority:.2f})"

        return True, "OK"

    def _get_cached_parameters(self, strategy_type: str, params_hash: str) -> Optional[Dict]:
        """Get cached parameters for a strategy type."""
        # In a real implementation, this would cache parameters
        # For now, return None to indicate not cached
        return None

    async def register_testing_start(self, strategy_id: str, strategy_type: str,
                                    parameters: Dict, priority: float = 1.0) -> bool:
        """
        Register that we're starting to test a strategy.

        Returns True if allowed, False otherwise.
        """
        can_test, reason = await self.can_test_strategy(strategy_id, strategy_type, parameters)

        if not can_test:
            logger.info(f"Blocked {strategy_id}: {reason}")
            return False

        # Register the active test
        params_hash = self._hash_parameters(parameters)
        active_test = ActiveTest(
            strategy_id=strategy_id,
            strategy_type=strategy_type,
            params_hash=params_hash,
            start_time=time.time(),
            priority=priority
        )

        self.active_tests[strategy_id] = active_test
        self.parameter_cache[strategy_type].add(params_hash)
        self.total_coordinations += 1

        logger.debug(f"Registered testing: {strategy_id} ({strategy_type})")
        return True

    async def register_testing_complete(self, strategy_id: str, result: Dict[str, Any]):
        """
        Register that testing is complete and deposit pheromone trail.
        """
        if strategy_id not in self.active_tests:
            logger.warning(f"Unknown strategy_id: {strategy_id}")
            return

        active_test = self.active_tests[strategy_id]

        # Remove from active tests
        del self.active_tests[strategy_id]

        # Update performance tracking
        strategy_type = active_test.strategy_type
        if strategy_type not in self.strategy_performance:
            self.strategy_performance[strategy_type] = StrategyPerformance(strategy_type=strategy_type)

        self.strategy_performance[strategy_type].add_result(result.get('sharpe_ratio', 0))

        # Deposit pheromone trail
        pheromone = PheromoneTrail(
            strategy_type=strategy_type,
            signal_strength=result.get('sharpe_ratio', 0),
            parameters_hash=active_test.params_hash,
            timestamp=time.time(),
            discovered_by='realistic_discovery',
            metadata={
                'strategy_id': strategy_id,
                'total_return': result.get('total_return', 0),
                'max_drawdown': result.get('max_drawdown', 0)
            }
        )

        self.pheromone_trails[strategy_id] = pheromone

        logger.info(f"Completed testing: {strategy_id} (Sharpe={pheromone.signal_strength:.2f})")

    def get_pheromone_trails(self, strategy_type: Optional[str] = None,
                           hours: int = 1, limit: int = 10) -> List[PheromoneTrail]:
        """Get recent pheromone trails (signals) from the environment."""
        cutoff_time = time.time() - (hours * 3600)

        trails = []
        for trail in self.pheromone_trails.values():
            if trail.timestamp < cutoff_time:
                continue  # Skip old trails

            if strategy_type and trail.strategy_type != strategy_type:
                continue  # Skip if not the requested type

            trails.append(trail)

        # Sort by signal strength (strongest first)
        trails.sort(key=lambda t: t.signal_strength, reverse=True)

        return trails[:limit]

    def calculate_emergent_specialization(self) -> Dict[str, float]:
        """
        Calculate emergent specialization based on collective discoveries.

        Returns priority multipliers for each strategy type.
        """
        # Get recent pheromone trails (last hour)
        recent_trails = self.get_pheromone_trails(hours=1, limit=100)

        if not recent_trails:
            return self.emergent_specializations

        # Group by strategy type
        type_signals = defaultdict(list)
        for trail in recent_trails:
            type_signals[trail.strategy_type].append(trail.signal_strength)

        # Calculate specialization scores
        specializations = {}

        for strategy_type, signals in type_signals.items():
            if len(signals) < 3:
                # Not enough data
                continue

            # Calculate signal strength statistics
            avg_signal = sum(signals) / len(signals)
            max_signal = max(signals)
            signal_consistency = 1.0 - (max(signals) - min(signals)) / max_signal if max(signals) > 0 else 0.5

            # Calculate trend (improving or declining)
            recent_signals = signals[-10:]  # Last 10 signals
            if len(recent_signals) >= 5:
                recent_avg = sum(recent_signals) / len(recent_signals)
                trend = (recent_avg - avg_signal) / max(1.0, abs(avg_signal))
            else:
                trend = 0

            # Combined specialization score
            # High average + consistency + positive trend = high specialization
            specialization = (avg_signal * 0.5 + signal_consistency * 0.3 + max(0, trend) * 0.2)

            specializations[strategy_type] = max(0.1, min(2.0, specialization))

        self.emergent_specializations = specializations
        self.last_specialization_update = time.time()

        logger.info(f"Emergent specializations updated: {specializations}")

        return specializations

    def update_dynamic_priorities(self) -> Dict[str, float]:
        """
        Update dynamic priorities based on emergent specialization and recent failures.
        """
        # Get emergent specializations
        specializations = self.calculate_emergent_specialization()

        # Get recent failures (last hour)
        recent_failures = self._get_recent_failures(hours=1)

        # Calculate priorities for each strategy type
        priorities = {}

        all_types = set(self.strategy_priorities.keys()) | set(specializations.keys())

        for strategy_type in all_types:
            base_priority = self.strategy_priorities.get(strategy_type, 1.0)

            # Apply specialization multiplier (boost successful areas)
            specialization_multiplier = specializations.get(strategy_type, 1.0)

            # Apply failure penalty (reduce failing areas)
            failure_count = recent_failures.get(strategy_type, 0)
            failure_penalty = max(0.3, 1.0 - (failure_count * 0.1))

            # Calculate final priority
            priority = base_priority * specialization_multiplier * failure_penalty

            # Apply decay to old priorities
            current_priority = self.strategy_priorities.get(strategy_type, 1.0)
            new_priority = current_priority * self.priority_decay_rate + priority * (1 - self.priority_decay_rate)

            # Clamp to reasonable range
            new_priority = max(0.1, min(3.0, new_priority))

            priorities[strategy_type] = new_priority

        self.strategy_priorities = priorities
        self.dynamic_focus_changes += 1

        logger.info(f"Dynamic priorities updated: {priorities}")

        return priorities

    def _get_recent_failures(self, hours: int = 1) -> Dict[str, int]:
        """Get recent failures by strategy type."""
        cutoff_time = time.time() - (hours * 3600)

        failures = defaultdict(int)

        # Check pheromone trails for failures
        for trail in self.pheromone_trails.values():
            if trail.timestamp < cutoff_time:
                continue

            # Consider Sharpe < -5 as a failure
            if trail.signal_strength < -5:
                failures[trail.strategy_type] += 1

        return dict(failures)

    def get_strategy_priority(self, strategy_type: str) -> float:
        """Get current priority for a strategy type."""
        # Update priorities if stale
        if time.time() - self.last_specialization_update > 300:  # 5 minutes
            self.update_dynamic_priorities()

        return self.strategy_priorities.get(strategy_type, 1.0)

    def get_coordination_stats(self) -> Dict[str, Any]:
        """Get statistics about coordination effectiveness."""
        # Calculate diversity of what's being tested
        active_types = set(test.strategy_type for test in self.active_tests.values())

        # Calculate average priority of active tests
        avg_priority = 0
        if self.active_tests:
            avg_priority = sum(test.priority for test in self.active_tests.values()) / len(self.active_tests)

        # Calculate success rate from performance tracking
        overall_success_rate = 0
        if self.strategy_performance:
            success_rates = [p.success_rate for p in self.strategy_performance.values()]
            if success_rates:
                overall_success_rate = sum(success_rates) / len(success_rates)

        return {
            "active_tests": len(self.active_tests),
            "max_capacity": self.max_concurrent_tests,
            "utilization": len(self.active_tests) / self.max_concurrent_tests,
            "active_strategy_types": list(active_types),
            "average_priority": avg_priority,
            "redundancy_avoided_count": self.redundancy_avoided,
            "dynamic_focus_changes_count": self.dynamic_focus_changes,
            "total_coordinations": self.total_coordinations,
            "overall_success_rate": overall_success_rate,
            "emergent_specializations": self.emergent_specializations,
            "strategy_priorities": self.strategy_priorities,
            "pheromone_trails_count": len(self.pheromone_trails),
            "strategy_performance_count": len(self.strategy_performance)
        }

    def cleanup_old_pheromones(self, hours: int = 24):
        """Clean up old pheromone trails to prevent memory bloat."""
        cutoff_time = time.time() - (hours * 3600)

        old_trails = [tid for tid, trail in self.pheromone_trails.items()
                      if trail.timestamp < cutoff_time]

        for trail_id in old_trails:
            del self.pheromone_trails[trail_id]

        logger.info(f"Cleaned up {len(old_trails)} old pheromone trails (older than {hours} hours)")


# Global instance
_stigmergic_coordinator = None


def get_stigmergic_coordinator() -> StigmergicCoordinator:
    """Get the global stigmergic coordinator instance."""
    global _stigmergic_coordinator
    if _stigmergic_coordinator is None:
        _stigmergic_coordinator = StigmergicCoordinator()
    return _stigmergic_coordinator