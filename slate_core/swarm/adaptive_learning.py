#!/usr/bin/env python3
"""
Adaptive Learning Module for SLATE Swarm Intelligence

This module implements profit-driven adaptive learning where backtest results
guide future exploration, replacing the current agent-success-only approach.

Key Innovation: Instead of marking where agents found patterns, we mark where
strategies actually made money in real backtests with brutal costs.
"""

import sqlite3
import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from collections import defaultdict
from slate_core.config.paths import CORE_ROOT

logger = logging.getLogger(__name__)


@dataclass
class ProfitabilitySignal:
    """Signal representing profitability in parameter space."""
    parameter_signature: str  # Hash of key parameters
    edge_type: str
    avg_profit_usdt: float
    success_rate: float  # Strategies that passed validation / total tested
    sample_size: int
    last_updated: datetime
    regime_context: str

    def __hash__(self):
        return hash((self.parameter_signature, self.edge_type))

    def profitability_score(self) -> float:
        """Calculate overall profitability score."""
        # Weighted combination of profit and success rate
        return (self.avg_profit_usdt * 0.7 + self.success_rate * 100.0 * 0.3)


class AdaptiveLearningEngine:
    """
    Engine that learns from backtest results and guides swarm exploration.

    Core Innovation: Replace agent-success-based pheromones with
    profit-based guidance that actually works with brutal costs.
    """

    def __init__(self, db_path: str = f"{CORE_ROOT}/slate_realistic_discoveries.db"):
        self.db_path = db_path
        self.profitability_memory: Dict[str, ProfitabilitySignal] = {}
        self.edge_type_performance: Dict[str, Dict[str, float]] = defaultdict(lambda: {
            'total_profit': 0.0,
            'total_strategies': 0,
            'profitable_count': 0,
            'avg_profit': 0.0,
            'success_rate': 0.0
        })

        # Adaptive exploration parameters
        self.exploration_focus = {}  # Which parameter spaces to focus on
        self.avoidance_zones = []  # Parameter spaces to avoid

        logger.info("🧠 Adaptive Learning Engine initialized")

    def learn_from_backtests(self, min_samples: int = 5) -> Dict[str, Any]:
        """
        Analyze recent backtest results and update learning.

        Returns: Learning insights and guidance for swarm agents
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get recent backtest results
            cursor.execute("""
                SELECT
                    edge_type,
                    COUNT(*) as total_strategies,
                    SUM(CASE WHEN passed_validation = 1 THEN 1 ELSE 0 END) as passed_count,
                    AVG(total_profit_usdt) as avg_profit,
                    AVG(CASE WHEN total_profit_usdt > 0 THEN 1 ELSE 0 END) as profitable_rate,
                    MAX(total_profit_usdt) as max_profit,
                    MIN(total_profit_usdt) as min_profit
                FROM perpetual_discoveries
                WHERE timestamp > datetime('now', '-24 hours')
                GROUP BY edge_type
                ORDER BY avg_profit DESC
            """)

            edge_performance = cursor.fetchall()

            # Update edge type performance tracking
            for edge_type, total, passed, avg_prof, profit_rate, max_prof, min_prof in edge_performance:
                stats = self.edge_type_performance[edge_type]
                stats['total_strategies'] = total
                stats['total_profit'] = avg_prof * total if avg_prof else 0
                stats['profitable_count'] = int(passed)
                stats['avg_profit'] = avg_prof if avg_prof else 0
                stats['success_rate'] = (passed / total) if total > 0 else 0

            conn.close()

            logger.info(f"🧠 Learned from {len(edge_performance)} edge types")
            return self._generate_guidance()

        except Exception as e:
            logger.error(f"Failed to learn from backtests: {e}")
            return {'status': 'error', 'message': str(e)}

    def _generate_guidance(self) -> Dict[str, Any]:
        """Generate exploration guidance based on learned profitability."""

        # Sort edge types by average profitability
        ranked_edges = sorted(
            self.edge_type_performance.items(),
            key=lambda x: x[1]['avg_profit'],
            reverse=True
        )

        if not ranked_edges:
            return {
                'status': 'success',
                'guidance': 'No data yet - explore uniformly'
            }

        best_edge = ranked_edges[0]
        worst_edge = ranked_edges[-1]

        # Calculate exploration weights
        total_profit = sum(stats['total_profit'] for _, stats in ranked_edges)

        guidance = {
            'status': 'success',
            'exploration_strategy': 'profitability_focused',
            'edge_type_weights': {},
            'parameter_hotspots': [],
            'avoidance_zones': [],
            'insights': []
        }

        # Assign exploration weights based on profitability
        for edge_type, stats in ranked_edges:
            if total_profit != 0 and stats['avg_profit'] != 0:
                weight = max(0.1, stats['avg_profit'] / 100.0)  # Normalize profit
                guidance['edge_type_weights'][edge_type] = weight
            else:
                guidance['edge_type_weights'][edge_type] = 0.1  # Minimum exploration

        # Generate insights
        guidance['insights'] = [
            f"🎯 Most profitable edge: {best_edge[0]} (${best_edge[1]['avg_profit']:.2f} avg)",
            f"⚠️  Least profitable: {worst_edge[0]} (${worst_edge[1]['avg_profit']:.2f} avg)",
            f"📊 Success rates: {', '.join([f'{e[0]}={e[1]['success_rate']:.1%}' for e in ranked_edges[:3]])}"
        ]

        # Identify avoidance zones (edge types with consistent losses)
        for edge_type, stats in ranked_edges:
            if stats['avg_profit'] < -10 and stats['total_strategies'] >= 3:
                guidance['avoidance_zones'].append(edge_type)
                guidance['insights'].append(f"🚫 Avoid zone: {edge_type} (consistent losses)")

        return guidance

    def get_parameter_guidance(self, edge_type: str) -> Dict[str, Any]:
        """
        Get parameter space guidance for a specific edge type.

        Returns: Recommended parameter ranges and avoided values
        """
        if edge_type not in self.edge_type_performance:
            return {
                'status': 'no_data',
                'guidance': 'Explore uniformly - no performance data yet'
            }

        stats = self.edge_type_performance[edge_type]

        if stats['total_strategies'] < 5:
            return {
                'status': 'insufficient_data',
                'guidance': f'Need more samples (only {stats["total_strategies"]} so far)'
            }

        # Analyze profitable vs unprofitable parameters
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    strategy_name,
                    total_profit_usdt,
                    passed_validation
                FROM perpetual_discoveries
                WHERE edge_type = ?
                ORDER BY total_profit_usdt DESC
                LIMIT 20
            """, (edge_type,))

            results = cursor.fetchall()
            conn.close()

            if not results:
                return {
                    'status': 'no_data',
                    'guidance': 'No performance data yet'
                }

            # Extract parameter patterns from strategy names
            profitable_params = []
            unprofitable_params = []

            for name, profit, passed in results:
                # Simple EMA pattern extraction (can be enhanced)
                if 'ema_' in name.lower():
                    try:
                        # Extract EMA periods: momentum_mean_reversion_ema_10_20
                        parts = name.split('ema_')[-1].split('_')
                        if len(parts) >= 2:
                            fast = float(parts[0])
                            slow = float(parts[1])

                            if profit > 0:
                                profitable_params.append({'fast': fast, 'slow': slow, 'profit': profit})
                            else:
                                unprofitable_params.append({'fast': fast, 'slow': slow, 'profit': profit})
                    except:
                        pass

            return {
                'status': 'success',
                'guidance': {
                    'profitable_ranges': self._find_profitable_ranges(profitable_params),
                    'avoided_values': [p['fast'] for p in unprofitable_params[:5]] if unprofitable_params else [],
                    'sample_size': stats['total_strategies'],
                    'success_rate': stats['success_rate'],
                    'avg_profit': stats['avg_profit']
                }
            }

        except Exception as e:
            logger.error(f"Failed to analyze parameters: {e}")
            return {
                'status': 'error',
                'guidance': f'Analysis failed: {str(e)}'
            }

    def _find_profitable_ranges(self, profitable_params: List[Dict]) -> List[Dict]:
        """Find parameter ranges that consistently produce profits."""
        if len(profitable_params) < 2:
            return []

        fast_periods = [p['fast'] for p in profitable_params]
        slow_periods = [p['slow'] for p in profitable_params]

        return [
            {
                'parameter': 'fast_period',
                'min': min(fast_periods),
                'max': max(fast_periods),
                'avg': np.mean(fast_periods)
            },
            {
                'parameter': 'slow_period',
                'min': min(slow_periods),
                'max': max(slow_periods),
                'avg': np.mean(slow_periods)
            }
        ]


# Singleton instance
_adaptive_learning_engine = None

def get_adaptive_learning_engine() -> AdaptiveLearningEngine:
    """Get the singleton adaptive learning engine instance."""
    global _adaptive_learning_engine
    if _adaptive_learning_engine is None:
        _adaptive_learning_engine = AdaptiveLearningEngine()
    return _adaptive_learning_engine
