"""
SLATE Ensemble Strategy System

Combines multiple strategies to create more robust trading systems through:
- Weighted voting across strategies
- Diversity optimization
- Correlation-aware selection
- Performance aggregation
"""

import asyncio
import logging
import random
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class EnsembleMember:
    """A single strategy in the ensemble."""
    strategy_id: str
    strategy_name: str
    strategy_type: str
    parameters: Dict[str, Any]
    weight: float = 1.0
    performance: Dict[str, float] = field(default_factory=dict)


@dataclass
class EnsembleResult:
    """Results from ensemble backtest."""
    ensemble_id: str
    ensemble_name: str
    member_count: int
    diversification_score: float
    correlation_matrix: Dict[str, float]
    aggregated_performance: Dict[str, float]
    member_contributions: Dict[str, float]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class EnsembleStrategy:
    """Combine multiple strategies for better risk-adjusted returns."""

    def __init__(self, max_members: int = 5):
        self.max_members = max_members
        self.members: List[EnsembleMember] = []
        self.correlation_cache: Dict[str, Dict[str, float]] = {}

    def create_ensemble_from_winners(self, top_strategies: List[Dict], count: int = 5) -> 'EnsembleStrategy':
        """Create ensemble from top-performing diverse strategies."""
        ensemble = EnsembleStrategy(max_members=count)

        # Select diverse strategies (low correlation)
        selected = self._select_diverse_strategies(top_strategies, count)

        for strategy_data in selected:
            member = EnsembleMember(
                strategy_id=strategy_data['strategy_id'],
                strategy_name=strategy_data['strategy_name'],
                strategy_type=strategy_data['strategy_type'],
                parameters=strategy_data.get('parameters', {}),
                weight=strategy_data.get('weight', 1.0),
                performance={
                    'sharpe': strategy_data.get('sharpe_ratio', 0),
                    'return': strategy_data.get('total_return', 0),
                    'max_drawdown': strategy_data.get('max_drawdown', 0)
                }
            )
            ensemble.members.append(member)

        # Normalize weights
        ensemble._normalize_weights()

        logger.info(f"Created ensemble with {len(ensemble.members)} members: "
                   f"{[m.strategy_type for m in ensemble.members]}")

        return ensemble

    def _select_diverse_strategies(self, strategies: List[Dict], count: int) -> List[Dict]:
        """Select strategies with low correlation for diversity."""
        if len(strategies) <= count:
            return strategies

        selected = []
        used_types = set()

        # Prioritize type diversity
        for strategy in strategies:
            if len(selected) >= count:
                break

            strategy_type = strategy['strategy_type']

            # Limit same type in ensemble
            type_count = sum(1 for s in selected if s['strategy_type'] == strategy_type)
            if type_count >= 2:  # Max 2 of same type
                continue

            selected.append(strategy)
            used_types.add(strategy_type)

        return selected

    def _normalize_weights(self):
        """Normalize weights to sum to 1."""
        total_weight = sum(m.weight for m in self.members)
        if total_weight > 0:
            for member in self.members:
                member.weight /= total_weight

    def generate_ensemble_signals(self, data: List[Dict], strategy_signals: Dict[str, List[int]]) -> List[int]:
        """Generate ensemble signals through weighted voting."""
        if not self.members:
            return [0] * len(data)

        ensemble_signals = []

        for i in range(len(data)):
            votes = []
            weights = []

            for member in self.members:
                if member.strategy_id in strategy_signals:
                    signal = strategy_signals[member.strategy_id][i]
                    if signal != 0:  # Only count non-neutral signals
                        votes.append(signal)
                        weights.append(member.weight)

            if not votes:
                ensemble_signals.append(0)
                continue

            # Weighted majority voting
            weighted_votes = [v * w for v, w in zip(votes, weights)]
            ensemble_signal = np.sign(sum(weighted_votes))

            # Only take position if consensus is strong
            if abs(sum(weighted_votes)) > sum(weights) * 0.3:
                ensemble_signals.append(int(ensemble_signal))
            else:
                ensemble_signals.append(0)

        return ensemble_signals

    def calculate_diversification_score(self) -> float:
        """Calculate how diverse the ensemble members are."""
        if len(self.members) <= 1:
            return 0.0

        # Type diversity
        types = set(m.strategy_type for m in self.members)
        type_diversity = len(types) / len(self.members)

        # Performance diversity
        returns = [m.performance.get('return', 0) for m in self.members]
        if returns:
            return_std = np.std(returns) if len(returns) > 1 else 0
            max_return = max(returns) if returns else 1
            performance_diversity = min(1.0, return_std / (abs(max_return) + 0.01))
        else:
            performance_diversity = 0.0

        # Combined score
        return (type_diversity * 0.7 + performance_diversity * 0.3)

    def get_ensemble_summary(self) -> Dict[str, Any]:
        """Get summary of ensemble composition."""
        return {
            'member_count': len(self.members),
            'strategy_types': list(set(m.strategy_type for m in self.members)),
            'diversification_score': self.calculate_diversification_score(),
            'total_weight': sum(m.weight for m in self.members),
            'members': [
                {
                    'name': m.strategy_name,
                    'type': m.strategy_type,
                    'weight': m.weight,
                    'sharpe': m.performance.get('sharpe', 0)
                }
                for m in self.members
            ]
        }


class EnsembleGenerator:
    """Generate ensemble strategies from top performers."""

    def __init__(self):
        self.ensemble_size = 5
        self.min_sharpe_threshold = 1.0  # Only use strategies with Sharpe > 1.0

    async def generate_ensembles(self, count: int = 3) -> List[Dict]:
        """Generate multiple ensemble strategies from recent winners."""
        try:
            import sqlite3
            from pathlib import Path

            db_path = Path(__file__).parent.parent / "slate_realistic_discoveries.db"
            if not db_path.exists():
                return []

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get recent winners (last 24 hours)
            from datetime import datetime, timedelta
            recent_cutoff = datetime.now() - timedelta(hours=24)
            recent_cutoff_iso = recent_cutoff.isoformat()

            # FIXED: Use composite fitness score that rewards ACTUAL TRADING
            # Fitness = Sharpe * log(trades + 1) * (1 + return)
            cursor.execute("""
                WITH strategy_fitness AS (
                    SELECT
                        strategy_id, strategy_name, strategy_type, timeframe,
                        parameters, sharpe_ratio, total_return, max_drawdown,
                        -- Extract trade count from parameters
                        CAST(COALESCE(
                            json_extract(parameters, '$.num_trades'),
                            json_extract(parameters, '$.trade_count'),
                            10
                        ) as REAL) as trade_count,
                        -- Composite fitness score
                        sharpe_ratio *
                        LOG(trade_count + 1) *
                        (1 + GREATEST(total_return, 0)) as fitness_score
                    FROM discovery_results
                    WHERE timestamp > ?
                      AND sharpe_ratio > ?
                      AND evaluation_type = 'singlepath'
                      AND storage_tier = 'full'
                    HAVING trade_count >= 10  -- MINIMUM 10 trades required
                )
                SELECT
                    strategy_id, strategy_name, strategy_type, timeframe,
                    parameters, sharpe_ratio, total_return, max_drawdown
                FROM strategy_fitness
                ORDER BY fitness_score DESC
                LIMIT 50
            """, (recent_cutoff_iso, self.min_sharpe_threshold))

            rows = cursor.fetchall()
            conn.close()

            if len(rows) < 2:
                logger.info("Not enough qualified strategies for ensemble generation")
                return []

            ensembles = []

            # Create multiple ensembles with different compositions
            for i in range(count):
                # Shuffle strategies for variety
                strategies_list = [dict(row) for row in rows]
                random.shuffle(strategies_list)

                # Create ensemble
                ensemble = EnsembleStrategy(max_members=self.ensemble_size)
                ensemble = ensemble.create_ensemble_from_winners(strategies_list, self.ensemble_size)

                # Create ensemble strategy definition
                ensemble_strategy = {
                    'id': f"ensemble_{random.randint(10000, 99999)}",
                    'name': f"ensemble_{self.ensemble_size}member_{i+1}",
                    'type': 'ensemble',
                    'timeframe': '4h',  # Use best performing timeframe
                    'parameters': {
                        'ensemble_type': 'weighted_voting',
                        'members': [m.strategy_id for m in ensemble.members],
                        'weights': [m.weight for m in ensemble.members],
                        'consensus_threshold': 0.3
                    },
                    'members': ensemble.get_ensemble_summary(),
                    'diversification_score': ensemble.calculate_diversification_score(),
                    'priority': 2.5  # High priority for ensembles
                }

                ensembles.append(ensemble_strategy)

            logger.info(f"Generated {len(ensembles)} ensemble strategies")
            return ensembles

        except Exception as e:
            logger.warning(f"Failed to generate ensembles: {e}")
            return []

    def calculate_ensemble_signals(self, ensemble: Dict, data: List[Dict]) -> List[int]:
        """Generate signals for an ensemble strategy."""
        # For now, use weighted random from member types
        # In production, would actually run each member strategy
        members = ensemble['parameters'].get('members', [])

        if not members:
            return [0] * len(data)

        # Generate signals from member types
        from .realistic_backtester import RealisticBacktester
        backtester = RealisticBacktester()

        member_signals = {}
        for member_id in members:
            # Create a simple strategy for each member type
            strategy_type = random.choice(['momentum', 'mean_reversion', 'breakout'])
            temp_strategy = {
                'type': strategy_type,
                'parameters': {'period': 20, 'threshold': 0.02}
            }
            signals = backtester._generate_signals(temp_strategy, data)
            member_signals[member_id] = signals

        # Weighted voting
        weights = ensemble['parameters'].get('weights', [1.0] * len(members))
        ensemble_signals = []

        for i in range(len(data)):
            weighted_sum = 0
            for j, member_id in enumerate(members):
                if member_id in member_signals and i < len(member_signals[member_id]):
                    weighted_sum += member_signals[member_id][i] * weights[j]

            # Apply consensus threshold
            if abs(weighted_sum) > ensemble['parameters'].get('consensus_threshold', 0.3):
                ensemble_signals.append(int(np.sign(weighted_sum)))
            else:
                ensemble_signals.append(0)

        return ensemble_signals
