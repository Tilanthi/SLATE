"""
SLATE Multi-Objective Optimization

Optimize strategies for multiple objectives simultaneously:
- Sharpe ratio
- Maximum drawdown
- Win rate
- Profit factor
- Calmar ratio

Uses Pareto optimization to find non-dominated solutions.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ObjectiveResult:
    """Result for a single objective."""
    objective_name: str
    value: float
    weight: float
    is_better_higher: bool  # True if higher is better (e.g., Sharpe), False if lower is better (e.g., drawdown)


@dataclass
class ParetoSolution:
    """A solution on the Pareto frontier."""
    strategy_id: str
    strategy_name: str
    parameters: Dict[str, Any]
    objectives: Dict[str, float]
    dominates_count: int  # How many other solutions this dominates
    dominated_by_count: int  # How many solutions dominate this
    pareto_rank: int  # 0 = non-dominated
    timestamp: str


class MultiObjectiveOptimizer:
    """Optimize for multiple objectives using Pareto optimization."""

    def __init__(self):
        # Define objectives with their properties
        self.objectives = {
            'sharpe_ratio': {'weight': 0.4, 'is_better_higher': True, 'target': 2.0},
            'max_drawdown': {'weight': 0.25, 'is_better_higher': False, 'target': 0.15},
            'win_rate': {'weight': 0.15, 'is_better_higher': True, 'target': 0.55},
            'profit_factor': {'weight': 0.1, 'is_better_higher': True, 'target': 1.5},
            'calmar_ratio': {'weight': 0.1, 'is_better_higher': True, 'target': 0.5}
        }

    def optimize(self, strategies: List[Dict]) -> List[ParetoSolution]:
        """Perform multi-objective optimization on strategy set.

        Returns Pareto-optimal solutions (non-dominated strategies).
        """
        if not strategies:
            return []

        # Calculate objectives for each strategy
        solutions = []

        for strategy in strategies:
            objectives = self._extract_objectives(strategy)
            if objectives:
                solution = ParetoSolution(
                    strategy_id=strategy.get('id', 'unknown'),
                    strategy_name=strategy.get('name', 'unknown'),
                    parameters=strategy.get('parameters', {}),
                    objectives=objectives,
                    dominates_count=0,
                    dominated_by_count=0,
                    pareto_rank=0,
                    timestamp=datetime.now().isoformat()
                )
                solutions.append(solution)

        # Calculate Pareto dominance
        self._calculate_pareto_ranks(solutions)

        # Return only non-dominated solutions (Pareto frontier)
        pareto_frontier = [s for s in solutions if s.pareto_rank == 0]

        logger.info(f"Multi-objective optimization: {len(strategies)} strategies -> "
                   f"{len(pareto_frontier)} Pareto-optimal solutions")

        return pareto_frontier

    def _extract_objectives(self, strategy: Dict) -> Optional[Dict[str, float]]:
        """Extract objective values from strategy result."""
        # These would come from actual backtest results
        # For now, we'll estimate from strategy parameters
        params = strategy.get('parameters', {})
        strategy_type = strategy.get('type', 'momentum')

        # Simulate objective values based on strategy type and parameters
        # In production, these would come from actual backtests
        if strategy_type == 'momentum':
            period = params.get('period', 20)
            threshold = params.get('threshold', 0.02)

            # Simulate: longer periods = lower drawdown but also lower returns
            sharpe = max(-10, min(10, (30 - period) / 5))
            max_dd = max(0.05, min(0.5, period / 100))
            win_rate = max(0.3, min(0.7, 0.5 - threshold * 2))
            profit_factor = max(0.5, min(3.0, win_rate * 2))
            calmar = sharpe / (max_dd + 0.01)

        elif strategy_type == 'mean_reversion':
            period = params.get('period', 20)
            std_dev = params.get('std_dev', 2.0)

            # Simulate: tighter std_dev = fewer trades but better win rate
            sharpe = max(-10, min(10, std_dev - 1) * 2)
            max_dd = max(0.05, min(0.4, 0.3 - std_dev * 0.1))
            win_rate = max(0.35, min(0.65, 0.5 + std_dev * 0.05))
            profit_factor = win_rate * (1 / (1 - win_rate + 0.01))
            calmar = sharpe / (max_dd + 0.01)

        elif strategy_type == 'breakout':
            period = params.get('period', 20)
            confirmation = params.get('confirmation', True)

            # Simulate: confirmation reduces false breakouts
            base_sharpe = 3.0 if confirmation else 1.0
            sharpe = base_sharpe * (20 / period) * np.random.uniform(0.8, 1.2)
            max_dd = max(0.1, min(0.5, period / 50))
            win_rate = max(0.4, min(0.6, 0.5 if confirmation else 0.45))
            profit_factor = win_rate * 1.5
            calmar = sharpe / (max_dd + 0.01)

        else:
            # Default values
            sharpe = 0.0
            max_dd = 0.2
            win_rate = 0.5
            profit_factor = 1.0
            calmar = 0.0

        return {
            'sharpe_ratio': sharpe,
            'max_drawdown': max_dd,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'calmar_ratio': calmar
        }

    def _calculate_pareto_ranks(self, solutions: List[ParetoSolution]):
        """Calculate Pareto ranks for all solutions."""
        for i, solution_i in enumerate(solutions):
            for j, solution_j in enumerate(solutions):
                if i == j:
                    continue

                # Check if solution_i dominates solution_j
                if self._dominates(solution_i, solution_j):
                    solution_j.dominated_by_count += 1
                    solution_i.dominates_count += 1

        # Assign ranks (non-dominated = rank 0)
        max_dominated = max(s.dominated_by_count for s in solutions) if solutions else 0

        for solution in solutions:
            if solution.dominated_by_count == 0:
                solution.pareto_rank = 0
            else:
                # Normalize dominated count to 0-1 range
                solution.pareto_rank = solution.dominated_by_count / max_dominated

    def _dominates(self, solution1: ParetoSolution, solution2: ParetoSolution) -> bool:
        """Check if solution1 dominates solution2 (better or equal in all objectives, strictly better in at least one)."""
        obj1 = solution1.objectives
        obj2 = solution2.objectives

        strictly_better = False

        for obj_name, config in self.objectives.items():
            val1 = obj1.get(obj_name, 0)
            val2 = obj2.get(obj_name, 0)

            if config['is_better_higher']:
                if val1 < val2:
                    return False  # Worse in this objective
                elif val1 > val2:
                    strictly_better = True
            else:  # Lower is better
                if val1 > val2:
                    return False  # Worse in this objective
                elif val1 < val2:
                    strictly_better = True

        return strictly_better

    def calculate_utility_score(self, solution: ParetoSolution) -> float:
        """Calculate weighted utility score for a solution."""
        score = 0.0
        total_weight = 0.0

        for obj_name, config in self.objectives.items():
            value = solution.objectives.get(obj_name, 0)
            weight = config['weight']

            # Normalize value to 0-1 range based on target
            if config['is_better_higher']:
                normalized = min(1.0, value / (config['target'] + 1e-6))
            else:
                normalized = max(0.0, 1.0 - value / (config['target'] + 1e-6))

            score += weight * normalized
            total_weight += weight

        return score / total_weight if total_weight > 0 else 0.0

    def select_best_solution(self, pareto_solutions: List[ParetoSolution],
                           preferences: Optional[Dict[str, float]] = None) -> ParetoSolution:
        """Select best solution from Pareto frontier based on preferences.

        Args:
            pareto_solutions: Non-dominated solutions
            preferences: Optional custom weights for objectives
        """
        if not pareto_solutions:
            raise ValueError("No Pareto-optimal solutions available")

        # Use custom preferences if provided
        if preferences:
            custom_optimizer = MultiObjectiveOptimizer()
            custom_optimizer.objectives.update(preferences)
            return max(pareto_solutions, key=custom_optimizer.calculate_utility_score)

        # Default: select by utility score
        return max(pareto_solutions, key=self.calculate_utility_score)

    def get_pareto_frontier_summary(self, pareto_solutions: List[ParetoSolution]) -> Dict[str, Any]:
        """Get summary statistics of Pareto frontier."""
        if not pareto_solutions:
            return {}

        # Extract objective ranges
        objective_ranges = {}

        for obj_name in self.objectives.keys():
            values = [s.objectives.get(obj_name, 0) for s in pareto_solutions]
            if values:
                objective_ranges[obj_name] = {
                    'min': min(values),
                    'max': max(values),
                    'avg': np.mean(values),
                    'std': np.std(values)
                }

        # Calculate diversity metrics
        diversity_metrics = self._calculate_frontier_diversity(pareto_solutions)

        return {
            'frontier_size': len(pareto_solutions),
            'objective_ranges': objective_ranges,
            'diversity': diversity_metrics,
            'strategy_types': list(set(s.parameters.get('type', 'unknown') for s in pareto_solutions)),
            'timestamp': datetime.now().isoformat()
        }

    def _calculate_frontier_diversity(self, solutions: List[ParetoSolution]) -> Dict[str, float]:
        """Calculate diversity metrics of the Pareto frontier."""
        if len(solutions) <= 1:
            return {'spread': 0.0, 'coverage': 0.0}

        # Spread: average distance between solutions
        distances = []
        for i, sol1 in enumerate(solutions):
            for sol2 in solutions[i+1:]:
                distance = self._solution_distance(sol1, sol2)
                distances.append(distance)

        spread = np.mean(distances) if distances else 0.0

        # Coverage: how much of the objective space is covered
        ranges = {}
        for obj_name in self.objectives.keys():
            values = [s.objectives.get(obj_name, 0) for s in solutions]
            if values:
                ranges[obj_name] = max(values) - min(values)

        coverage = np.mean(list(ranges.values())) if ranges else 0.0

        return {
            'spread': spread,
            'coverage': coverage
        }

    def _solution_distance(self, sol1: ParetoSolution, sol2: ParetoSolution) -> float:
        """Calculate Euclidean distance between two solutions in objective space."""
        distances = []

        for obj_name in self.objectives.keys():
            val1 = sol1.objectives.get(obj_name, 0)
            val2 = sol2.objectives.get(obj_name, 0)

            # Normalize by typical range
            if self.objectives[obj_name]['is_better_higher']:
                range_val = 10.0  # Typical range for Sharpe, etc.
            else:
                range_val = 1.0  # Typical range for ratios

            normalized_dist = abs(val1 - val2) / range_val
            distances.append(normalized_dist)

        return np.sqrt(sum(d**2 for d in distances)) if distances else 0.0


class PreferenceManager:
    """Manage user preferences for multi-objective optimization."""

    def __init__(self):
        # Predefined preference profiles
        self.profiles = {
            'conservative': {
                'sharpe_ratio': {'weight': 0.5, 'is_better_higher': True, 'target': 1.5},
                'max_drawdown': {'weight': 0.3, 'is_better_higher': False, 'target': 0.1},
                'win_rate': {'weight': 0.2, 'is_better_higher': True, 'target': 0.6},
                'profit_factor': {'weight': 0.0, 'is_better_higher': True, 'target': 1.0},
                'calmar_ratio': {'weight': 0.0, 'is_better_higher': True, 'target': 0.3}
            },
            'aggressive': {
                'sharpe_ratio': {'weight': 0.5, 'is_better_higher': True, 'target': 3.0},
                'max_drawdown': {'weight': 0.1, 'is_better_higher': False, 'target': 0.3},
                'win_rate': {'weight': 0.1, 'is_better_higher': True, 'target': 0.45},
                'profit_factor': {'weight': 0.2, 'is_better_higher': True, 'target': 2.0},
                'calmar_ratio': {'weight': 0.1, 'is_better_higher': True, 'target': 0.8}
            },
            'balanced': {
                'sharpe_ratio': {'weight': 0.3, 'is_better_higher': True, 'target': 2.0},
                'max_drawdown': {'weight': 0.25, 'is_better_higher': False, 'target': 0.15},
                'win_rate': {'weight': 0.2, 'is_better_higher': True, 'target': 0.55},
                'profit_factor': {'weight': 0.15, 'is_better_higher': True, 'target': 1.5},
                'calmar_ratio': {'weight': 0.1, 'is_better_higher': True, 'target': 0.5}
            }
        }

    def get_profile(self, profile_name: str) -> Dict[str, Dict]:
        """Get preference profile by name."""
        return self.profiles.get(profile_name, self.profiles['balanced'])

    def create_custom_profile(self, name: str, weights: Dict[str, float]) -> Dict[str, Dict]:
        """Create custom preference profile."""
        # Validate weights sum to approximately 1
        total_weight = sum(weights.values())

        if total_weight == 0:
            raise ValueError("Weights must sum to > 0")

        profile = {}
        for obj_name, config in self.profiles['balanced'].items():
            custom_weight = weights.get(obj_name, 0.0)

            profile[obj_name] = {
                'weight': custom_weight / total_weight,  # Normalize
                'is_better_higher': config['is_better_higher'],
                'target': config['target']
            }

        return profile
