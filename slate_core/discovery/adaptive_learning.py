#!/usr/bin/env python3
"""
SLATE Adaptive Learning System

Intelligently balances exploration and exploitation in strategy discovery:
- Exploitation: Focus resources on profitable strategy types/parameters
- Exploration: Maintain sparse coverage of all areas to detect regime changes

Features:
- Performance-based resource allocation
- Minimum exploration budgets
- Regime change detection
- Dynamic allocation adjustment
- Pattern recognition and learning
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class StrategyPerformanceProfile:
    """Performance profile for a strategy type/timeframe combination."""
    strategy_type: str
    timeframe: str
    total_tests: int = 0
    successful_tests: int = 0  # Sharpe > 1.0
    avg_sharpe: float = 0.0
    avg_return: float = 0.0
    avg_win_rate: float = 0.0
    best_sharpe: float = 0.0
    recent_performance: List[float] = field(default_factory=list)  # Last 20 Sharpe ratios
    parameter_ranges: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    last_update: datetime = field(default_factory=datetime.now)

    def success_rate(self) -> float:
        """Calculate success rate (fraction of tests with Sharpe > 1.0)."""
        return self.successful_tests / self.total_tests if self.total_tests > 0 else 0.0

    def recent_trend(self) -> str:
        """Determine if performance is trending up, down, or stable."""
        if len(self.recent_performance) < 10:
            return "insufficient_data"

        recent_avg = np.mean(self.recent_performance[-10:])
        older_avg = np.mean(self.recent_performance[-20:-10]) if len(self.recent_performance) >= 20 else recent_avg

        if recent_avg > older_avg * 1.1:
            return "improving"
        elif recent_avg < older_avg * 0.9:
            return "declining"
        else:
            return "stable"


@dataclass
class ResourceAllocation:
    """Resource allocation for discovery cycles."""
    strategy_type: str
    timeframe: str
    allocation_percent: float  # Percentage of total discovery cycles
    min_allocation: float = 0.05  # Minimum 5% for exploration
    max_allocation: float = 0.50  # Maximum 50% to prevent over-concentration
    allocation_reason: str = ""

    def validate_allocation(self) -> float:
        """Ensure allocation is within bounds."""
        return max(self.min_allocation, min(self.allocation_percent, self.max_allocation))


class AdaptiveLearningEngine:
    """
    Adaptive learning engine for intelligent resource allocation.

    Balances exploration and exploitation:
    - 70-80% exploitation: Focus on profitable areas
    - 20-30% exploration: Sparse coverage of all areas
    """

    def __init__(self,
                 db_path: Optional[str] = None,
                 exploitation_ratio: float = 0.75,
                 min_exploration_budget: float = 0.05):
        """
        Initialize adaptive learning engine.

        Args:
            db_path: Path to discovery database
            exploitation_ratio: Fraction of resources for exploitation (0.7-0.85)
            min_exploration_budget: Minimum allocation for any area (0.03-0.10)
        """
        if db_path is None:
            db_path = Path(__file__).parent.parent / "slate_realistic_discoveries.db"

        self.db_path = str(db_path)
        self.exploitation_ratio = exploitation_ratio
        self.min_exploration_budget = min_exploration_budget

        # Performance tracking
        self.performance_profiles: Dict[Tuple[str, str], StrategyPerformanceProfile] = {}
        self.resource_allocations: Dict[Tuple[str, str], ResourceAllocation] = {}

        # Strategy types and timeframes to track
        self.strategy_types = [
            'momentum', 'mean_reversion', 'breakout', 'trend_following',
            'statistical_arb', 'machine_learning', 'regime_switching',
            'order_flow', 'microstructure', 'multi_timeframe'
        ]

        self.timeframes = ['5s', '1m', '5m', '15m', '1h', '4h']

        # Learning state
        self.last_analysis_time: Optional[datetime] = None
        self.analysis_interval_hours = 1  # Re-analyze every hour
        self.regime_change_detected = False

        logger.info(
            f"AdaptiveLearningEngine initialized: "
            f"exploitation={exploitation_ratio:.2%}, "
            f"min_exploration={min_exploration_budget:.2%}"
        )

    async def analyze_and_learn(self) -> Dict[str, Any]:
        """
        Analyze discovery results and update learning.

        Returns:
            Analysis summary with insights and updated allocations
        """
        logger.info("Starting adaptive learning analysis...")

        # Load recent results from database
        recent_results = await self._load_recent_results()

        if not recent_results:
            logger.warning("No recent results found for analysis")
            return {'status': 'no_data', 'allocations': {}}

        # Update performance profiles
        await self._update_performance_profiles(recent_results)

        # Detect regime changes
        await self._detect_regime_changes()

        # Calculate optimal resource allocation
        allocations = await self._calculate_resource_allocation()

        # Generate insights
        insights = await self._generate_insights()

        self.last_analysis_time = datetime.now()

        logger.info(
            f"Adaptive learning complete: "
            f"{len(recent_results)} results analyzed, "
            f"{len(allocations)} allocation decisions"
        )

        return {
            'status': 'success',
            'analysis_time': self.last_analysis_time.isoformat(),
            'allocations': allocations,
            'insights': insights,
            'performance_summary': self._get_performance_summary()
        }

    async def _load_recent_results(self, days_back: int = 7) -> List[Dict]:
        """Load recent discovery results from database."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get results from last N days
            cutoff_date = (datetime.now() - timedelta(days=days_back)).isoformat()

            query = """
                SELECT
                    strategy_type,
                    timeframe,
                    sharpe_ratio,
                    total_return,
                    win_rate,
                    parameters,
                    timestamp
                FROM discovery_results
                WHERE timestamp > ?
                ORDER BY timestamp DESC
            """

            cursor.execute(query, (cutoff_date,))
            rows = cursor.fetchall()

            results = []
            for row in rows:
                results.append({
                    'strategy_type': row['strategy_type'],
                    'timeframe': row['timeframe'],
                    'sharpe_ratio': row['sharpe_ratio'] or 0.0,
                    'total_return': row['total_return'] or 0.0,
                    'win_rate': row['win_rate'] or 0.0,
                    'parameters': row['parameters'],
                    'timestamp': row['timestamp']
                })

            conn.close()
            logger.info(f"Loaded {len(results)} results from last {days_back} days")
            return results

        except Exception as e:
            logger.error(f"Error loading results from database: {e}")
            return []

    async def _update_performance_profiles(self, results: List[Dict]):
        """Update performance profiles based on recent results."""
        # Group results by strategy_type and timeframe
        grouped = defaultdict(list)
        for result in results:
            key = (result['strategy_type'], result['timeframe'])
            grouped[key].append(result)

        # Update or create profiles
        for key, key_results in grouped.items():
            strategy_type, timeframe = key

            if key not in self.performance_profiles:
                self.performance_profiles[key] = StrategyPerformanceProfile(
                    strategy_type=strategy_type,
                    timeframe=timeframe
                )

            profile = self.performance_profiles[key]

            # Update metrics
            sharpes = [r['sharpe_ratio'] for r in key_results]
            returns = [r['total_return'] for r in key_results]
            win_rates = [r['win_rate'] for r in key_results]

            profile.total_tests += len(key_results)
            profile.successful_tests += sum(1 for s in sharpes if s > 1.0)
            profile.avg_sharpe = np.mean(sharpes)
            profile.avg_return = np.mean(returns)
            profile.avg_win_rate = np.mean(win_rates)
            profile.best_sharpe = max(sharpes)
            profile.recent_performance.extend(sharpes)
            profile.recent_performance = profile.recent_performance[-50:]  # Keep last 50
            profile.last_update = datetime.now()

            # Extract parameter ranges
            await self._extract_parameter_ranges(profile, key_results)

    async def _extract_parameter_ranges(self, profile: StrategyPerformanceProfile, results: List[Dict]):
        """Extract successful parameter ranges from results."""
        successful_results = [r for r in results if r['sharpe_ratio'] > 1.0]

        if not successful_results:
            return

        # Parse parameters and find ranges
        all_params = defaultdict(list)
        for result in successful_results:
            try:
                params = eval(result['parameters']) if isinstance(result['parameters'], str) else result['parameters']
                if isinstance(params, dict):
                    for key, value in params.items():
                        if isinstance(value, (int, float)):
                            all_params[key].append(value)
            except:
                continue

        # Calculate ranges (percentile-based)
        for param_name, values in all_params.items():
            if len(values) >= 5:  # Need at least 5 samples
                p10 = np.percentile(values, 10)
                p90 = np.percentile(values, 90)
                profile.parameter_ranges[param_name] = (p10, p90)

    async def _detect_regime_changes(self):
        """Detect if market regime has changed based on performance shifts."""
        if len(self.performance_profiles) < 5:
            return

        # Check if previously successful areas are now failing
        declining_profiles = []

        for key, profile in self.performance_profiles.items():
            if profile.total_tests >= 20:  # Only check profiles with sufficient data
                trend = profile.recent_trend()
                if trend == "declining" and profile.success_rate() > 0.3:
                    declining_profiles.append((key, profile))

        if len(declining_profiles) >= 3:  # Multiple areas declining = regime change
            self.regime_change_detected = True
            logger.warning(
                f"Regime change detected! {len(declining_profiles)} areas declining. "
                "Increasing exploration budget."
            )
        else:
            self.regime_change_detected = False

    async def _calculate_resource_allocation(self) -> Dict[str, ResourceAllocation]:
        """
        Calculate optimal resource allocation balancing exploration and exploitation.

        Returns:
            Dictionary of (strategy_type, timeframe) -> ResourceAllocation
        """
        allocations = {}

        # Calculate performance scores for each area
        performance_scores = {}

        for key, profile in self.performance_profiles.items():
            # Score combines success rate, average Sharpe, and recent trend
            score = (
                profile.success_rate() * 0.4 +
                min(profile.avg_sharpe / 5.0, 1.0) * 0.3 +
                (1.0 if profile.recent_trend() == "improving" else 0.5) * 0.3
            )
            performance_scores[key] = score

        # Normalize scores
        if performance_scores:
            max_score = max(performance_scores.values())
            if max_score > 0:
                performance_scores = {k: v / max_score for k, v in performance_scores.items()}

        # Allocate resources
        all_combinations = [(st, tf) for st in self.strategy_types for tf in self.timeframes]

        # If regime change detected, increase exploration
        if self.regime_change_detected:
            exploration_ratio = 1.0 - self.exploitation_ratio + 0.15  # Increase exploration
            logger.info(f"Regime change: Increasing exploration to {exploration_ratio:.2%}")
        else:
            exploration_ratio = 1.0 - self.exploitation_ratio

        for key in all_combinations:
            strategy_type, timeframe = key

            if key in performance_scores and performance_scores[key] > 0.1:
                # Exploitation: Allocate based on performance score
                base_allocation = performance_scores[key] * self.exploitation_ratio
                reason = f"exploitation (score: {performance_scores[key]:.2f})"
            else:
                # Exploration: Minimum budget
                base_allocation = self.min_exploration_budget
                reason = "exploration (minimum coverage)"

            # Add bonus for improving trends
            if key in self.performance_profiles:
                if self.performance_profiles[key].recent_trend() == "improving":
                    base_allocation *= 1.2
                    reason += " + improving trend"

            allocations[key] = ResourceAllocation(
                strategy_type=strategy_type,
                timeframe=timeframe,
                allocation_percent=base_allocation,
                min_allocation=self.min_exploration_budget,
                max_allocation=0.50,
                allocation_reason=reason
            )

        # Normalize to ensure total = 100%
        total = sum(a.validate_allocation() for a in allocations.values())
        if total > 0:
            for allocation in allocations.values():
                allocation.allocation_percent = (allocation.validate_allocation() / total) * 100

        self.resource_allocations = allocations

        return allocations

    async def _generate_insights(self) -> Dict[str, Any]:
        """Generate insights from performance analysis."""
        insights = {
            'top_performers': [],
            'emerging_opportunities': [],
            'declining_areas': [],
            'parameter_insights': {},
            'recommendations': []
        }

        # Sort profiles by performance
        sorted_profiles = sorted(
            self.performance_profiles.items(),
            key=lambda x: x[1].avg_sharpe,
            reverse=True
        )

        # Top performers (exploitation targets)
        for key, profile in sorted_profiles[:5]:
            if profile.success_rate() > 0.2:
                insights['top_performers'].append({
                    'strategy_type': profile.strategy_type,
                    'timeframe': profile.timeframe,
                    'avg_sharpe': profile.avg_sharpe,
                    'success_rate': profile.success_rate(),
                    'trend': profile.recent_trend()
                })

        # Emerging opportunities (improving but not yet top)
        for key, profile in sorted_profiles:
            if profile.recent_trend() == "improving" and profile.success_rate() > 0.1:
                insights['emerging_opportunities'].append({
                    'strategy_type': profile.strategy_type,
                    'timeframe': profile.timeframe,
                    'avg_sharpe': profile.avg_sharpe,
                    'trend': 'improving'
                })

        # Declining areas (reduce allocation)
        for key, profile in sorted_profiles:
            if profile.recent_trend() == "declining" and profile.total_tests >= 20:
                insights['declining_areas'].append({
                    'strategy_type': profile.strategy_type,
                    'timeframe': profile.timeframe,
                    'avg_sharpe': profile.avg_sharpe,
                    'trend': 'declining'
                })

        # Parameter insights
        for key, profile in sorted_profiles[:5]:
            if profile.parameter_ranges:
                strategy_timeframe = f"{profile.strategy_type}_{profile.timeframe}"
                insights['parameter_insights'][strategy_timeframe] = profile.parameter_ranges

        # Generate recommendations
        if insights['top_performers']:
            top = insights['top_performers'][0]
            insights['recommendations'].append(
                f"Focus on {top['strategy_type']} @ {top['timeframe']} "
                f"(Sharpe: {top['avg_sharpe']:.2f})"
            )

        if insights['emerging_opportunities']:
            opp = insights['emerging opportunities'][0]
            insights['recommendations'].append(
                f"Watch {opp['strategy_type']} @ {opp['timeframe']} "
                "(improving trend)"
            )

        if self.regime_change_detected:
            insights['recommendations'].append(
                "REGIME CHANGE: Increase exploration across all strategy types"
            )

        return insights

    def _get_performance_summary(self) -> Dict[str, Any]:
        """Get summary of current performance knowledge."""
        summary = {
            'total_areas_tracked': len(self.performance_profiles),
            'areas_with_positive_results': sum(
                1 for p in self.performance_profiles.values() if p.avg_sharpe > 0
            ),
            'areas_with_good_results': sum(
                1 for p in self.performance_profiles.values() if p.avg_sharpe > 1.0
            ),
            'best_overall': None,
            'worst_overall': None
        }

        if self.performance_profiles:
            best = max(self.performance_profiles.items(), key=lambda x: x[1].avg_sharpe)
            worst = min(self.performance_profiles.items(), key=lambda x: x[1].avg_sharpe)

            summary['best_overall'] = {
                'strategy_type': best[1].strategy_type,
                'timeframe': best[1].timeframe,
                'avg_sharpe': best[1].avg_sharpe
            }
            summary['worst_overall'] = {
                'strategy_type': worst[1].strategy_type,
                'timeframe': worst[1].timeframe,
                'avg_sharpe': worst[1].avg_sharpe
            }

        return summary

    def get_allocation_for_cycle(self, total_cycles: int) -> List[Dict[str, Any]]:
        """
        Get strategy allocation for discovery cycles.

        Args:
            total_cycles: Total number of discovery cycles to allocate

        Returns:
            List of (strategy_type, timeframe, count) tuples
        """
        allocation = []

        for key, resource_alloc in self.resource_allocations.items():
            strategy_type, timeframe = key
            count = max(1, int(total_cycles * resource_alloc.allocation_percent / 100))

            allocation.append({
                'strategy_type': strategy_type,
                'timeframe': timeframe,
                'count': count,
                'allocation_percent': resource_alloc.allocation_percent,
                'reason': resource_alloc.allocation_reason
            })

        # Sort by count (descending)
        allocation.sort(key=lambda x: x['count'], reverse=True)

        return allocation

    def get_suggested_parameters(self, strategy_type: str, timeframe: str) -> Optional[Dict[str, Tuple[float, float]]]:
        """
        Get suggested parameter ranges based on historical success.

        Args:
            strategy_type: Strategy type
            timeframe: Timeframe

        Returns:
            Dictionary of parameter_name -> (min_value, max_value) or None
        """
        key = (strategy_type, timeframe)

        if key in self.performance_profiles:
            return self.performance_profiles[key].parameter_ranges

        return None

    def should_increase_exploration(self) -> bool:
        """Check if exploration should be increased due to regime changes."""
        return self.regime_change_detected

    def get_exploitation_targets(self) -> List[Tuple[str, str]]:
        """Get top exploitation targets (highest performing areas)."""
        sorted_profiles = sorted(
            self.performance_profiles.items(),
            key=lambda x: x[1].avg_sharpe,
            reverse=True
        )

        # Return top 20% of areas
        top_n = max(1, len(sorted_profiles) // 5)
        return [key for key, _ in sorted_profiles[:top_n]]


# Global instance
_adaptive_learning_engine: Optional[AdaptiveLearningEngine] = None


def get_adaptive_learning_engine(
    exploitation_ratio: float = 0.75,
    min_exploration_budget: float = 0.05
) -> AdaptiveLearningEngine:
    """Get the global adaptive learning engine instance."""
    global _adaptive_learning_engine
    if _adaptive_learning_engine is None:
        _adaptive_learning_engine = AdaptiveLearningEngine(
            exploitation_ratio=exploitation_ratio,
            min_exploration_budget=min_exploration_budget
        )
    return _adaptive_learning_engine
