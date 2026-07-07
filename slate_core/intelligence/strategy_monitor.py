#!/usr/bin/env python3
"""
Automated Strategy Performance Monitoring System

Monitors CONDITIONAL strategies over time and automatically upgrades them to DEPLOY quality
when they demonstrate consistent performance.

This makes SLATE truly autonomous - not just discovering strategies, but managing their lifecycle.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
from datetime import datetime, timedelta
import sqlite3 as sqlite

from slate_core.discovery.perpetual_database import PerpetualDatabaseManager

logger = logging.getLogger(__name__)


class StrategyQuality(Enum):
    """Strategy quality levels with clear upgrade criteria."""
    REJECT = "REJECT"              # Failed validation - not deployed
    CONDITIONAL = "CONDITIONAL"    # Deployed with monitoring, requires oversight
    DEPLOY = "DEPLOY"            # Proven strategy - fully autonomous
    RETIRED = "RETIRED"          # Strategy no longer performing


@dataclass
class PerformanceSnapshot:
    """Performance snapshot of a strategy at a point in time."""
    strategy_id: int
    timestamp: datetime
    quality_level: StrategyQuality

    # Performance metrics
    cumulative_profit_usdt: float
    cumulative_return_pct: float
    current_drawdown_pct: float
    sharpe_ratio: float
    win_rate: float
    total_trades: int

    # Consistency metrics
    profit_factor: float
    avg_trade_pnl_usdt: float

    # Market conditions
    market_regime: str
    volatility_level: float

    # Tracking
    days_in_quality: int
    consecutive_losses: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'strategy_id': self.strategy_id,
            'timestamp': self.timestamp.isoformat(),
            'quality_level': self.quality_level.value,
            'cumulative_profit_usdt': self.cumulative_profit_usdt,
            'cumulative_return_pct': self.cumulative_return_pct,
            'current_drawdown_pct': self.current_drawdown_pct,
            'sharpe_ratio': self.sharpe_ratio,
            'win_rate': self.win_rate,
            'total_trades': self.total_trades,
            'profit_factor': self.profit_factor,
            'avg_trade_pnl_usdt': self.avg_trade_pnl_usdt,
            'market_regime': self.market_regime,
            'volatility_level': self.volatility_level,
            'days_in_quality': self.days_in_quality,
            'consecutive_losses': self.consecutive_losses
        }


@dataclass
class StrategyPerformanceHistory:
    """Complete performance history for tracking and evaluation."""
    strategy_id: int
    strategy_name: str

    # Current status
    quality_level: StrategyQuality
    current_snapshot: PerformanceSnapshot

    # Performance tracking
    history: List[PerformanceSnapshot] = field(default_factory=list)

    # Upgrade tracking
    first_deployed_at: Optional[datetime] = None
    last_upgrade_at: Optional[datetime] = None
    upgrade_count: int = 0
    downgrade_count: int = 0

    # Performance metrics over time
    best_sharpe: float = 0.0
    best_total_return: float = -999.0
    worst_drawdown: float = 0.0

    # Stability metrics
    profitable_days: int = 0
    total_days_tracked: int = 0
    consistency_score: float = 0.0

    def get_days_in_current_quality(self) -> int:
        """Get how many days the strategy has been in current quality level."""
        if not self.history:
            return 0
        return len([s for s in self.history if s.quality_level == self.quality_level])


class StrategyMonitoringSystem:
    """
    Automated performance monitoring and upgrade system.

    Monitors CONDITIONAL strategies and upgrades them to DEPLOY when they
    demonstrate consistent profitability and stability.
    """

    def __init__(self):
        self.db_manager = PerpetualDatabaseManager()
        self.db_path = "slate_core/slate_realistic_discoveries.db"

        # Monitoring configuration
        self.evaluation_interval_hours = 24  # Evaluate daily
        self.minimum_evaluation_days = 7        # Minimum days before considering upgrade
        self.performance_window_days = 30       # Lookback window for performance

        # Upgrade criteria (CONDITIONAL → DEPLOY)
        self.upgrade_criteria = {
            'min_days_in_quality': 14,          # Must be CONDITIONAL for 2 weeks
            'min_evaluation_days': 7,           # Must have 7 days of data
            'min_sharpe_ratio': 0.3,           # Sharpe > 0.3
            'min_win_rate': 0.45,                # Win rate > 45%
            'min_return_pct': 5.0,               # At least 5% return
            'max_drawdown_pct': 15.0,             # Drawdown < 15%
            'min_profit_factor': 1.2,           # Profit factor > 1.2
            'min_consistency_score': 0.6,        # Consistency > 60%
            'min_profitable_days': 10,          # At least 10 profitable days
            'max_consecutive_losses': 3         # No more than 3 consecutive losing days
        }

        # Downgrade criteria (DEPLOY → CONDITIONAL)
        self.downgrade_criteria = {
            'max_sharpe_drop': 0.3,           # Sharpe dropped by 0.3
            'max_drawdown_increase': 10.0,      # Drawdown increased by 10%
            'consecutive_losses': 5,              # 5 consecutive losing days
            'win_rate_drop': 0.15,              # Win rate dropped by 15%
            'total_loss_threshold_usdt': 500,     # Lost $500 total
        }

        # Strategy performance histories
        self.strategy_histories: Dict[int, StrategyPerformanceHistory] = {}

        logger.info("Strategy Monitoring System initialized")
        logger.info(f"Upgrade criteria: Sharpe > {self.upgrade_criteria['min_sharpe_ratio']}, Win Rate > {self.upgrade_criteria['min_win_rate']:.0%}")
        logger.info(f"Downgrade criteria: Sharpe drop > {self.downgrade_criteria['max_sharpe_drop']}, Drawdown increase > {self.downgrade_criteria['max_drawdown_increase']}%")

    def get_conditional_strategies(self) -> List[Dict[str, Any]]:
        """Get all CONDITIONAL strategies currently being monitored."""
        try:
            conn = sqlite.connect(self.db_path)
            cursor = conn.cursor()

            # Get CONDITIONAL strategies (strategies that passed validation but need monitoring)
            # Using passed_validation = 1 as CONDITIONAL (deployed with monitoring)
            cursor.execute("""
                SELECT id, strategy_name, total_profit_usdt, total_return_pct,
                       total_trades, sharpe_ratio, max_drawdown_pct, win_rate,
                       profit_factor, timestamp
                FROM perpetual_discoveries
                WHERE passed_validation = 1
                ORDER BY timestamp DESC
            """)

            strategies = []
            for row in cursor.fetchall():
                strategy = {
                    'id': row[0],
                    'name': row[1],
                    'total_profit_usdt': row[2],
                    'total_return_pct': row[3],
                    'total_trades': row[4],
                    'sharpe_ratio': row[5],
                    'max_drawdown_pct': row[6],
                    'win_rate': row[7],
                    'profit_factor': row[8],
                    'timestamp': datetime.fromisoformat(row[9])
                }
                strategies.append(strategy)

            conn.close()
            logger.info(f"Found {len(strategies)} CONDITIONAL strategies to monitor")
            return strategies

        except Exception as e:
            logger.error(f"Error getting CONDITIONAL strategies: {e}")
            return []

    def evaluate_strategy_performance(self, strategy_id: int, days_to_track: int = 30) -> Dict[str, Any]:
        """
        Evaluate strategy performance over a time window.

        Returns comprehensive performance metrics and upgrade recommendation.
        """
        try:
            conn = sqlite.connect(self.db_path)
            cursor = conn.cursor()

            # Get strategy info
            cursor.execute("""
                SELECT strategy_name, total_profit_usdt, total_return_pct,
                       total_trades, sharpe_ratio, max_drawdown_pct, win_rate,
                       profit_factor, edge_type
                FROM perpetual_discoveries
                WHERE id = ?
            """, (strategy_id,))

            row = cursor.fetchone()
            if not row:
                return {'error': 'Strategy not found'}

            strategy_name = row[0]
            total_profit = row[1]
            total_return = row[2]
            total_trades = row[3]
            sharpe = row[4]
            max_dd = row[5]
            win_rate = row[6]
            profit_factor = row[7] if row[7] else 0.0

            # Calculate performance metrics
            metrics = {
                'strategy_id': strategy_id,
                'strategy_name': strategy_name,
                'total_profit_usdt': total_profit,
                'total_return_pct': total_return,
                'sharpe_ratio': sharpe,
                'win_rate': win_rate,
                'total_trades': total_trades,
                'max_drawdown_pct': max_dd,
                'profit_factor': profit_factor,
                'edge_type': row[8]
            }

            # Check upgrade criteria
            upgrade_checks = {
                'sharpe_good': sharpe >= self.upgrade_criteria['min_sharpe_ratio'],
                'win_rate_good': win_rate >= self.upgrade_criteria['min_win_rate'],
                'return_positive': total_return >= self.upgrade_criteria['min_return_pct'],
                'drawdown_acceptable': max_dd <= self.upgrade_criteria['max_drawdown_pct'],
                'profit_factor_good': profit_factor >= self.upgrade_criteria['min_profit_factor'],
                'trades_sufficient': total_trades >= 10
            }

            # Calculate overall upgrade score
            upgrade_score = sum(upgrade_checks.values()) / len(upgrade_checks)

            # Determine recommendation
            if upgrade_score >= 0.8:  # 80% of criteria met
                recommendation = "UPGRADE_TO_DEPLOY"
            elif upgrade_score >= 0.5:  # 50-80% criteria met
                recommendation = "MONITOR_CLOSELY"
            else:
                recommendation = "KEEP_CONDITIONAL"

            metrics['upgrade_score'] = upgrade_score
            metrics['recommendation'] = recommendation
            metrics['upgrade_checks'] = upgrade_checks

            conn.close()
            return metrics

        except Exception as e:
            logger.error(f"Error evaluating strategy {strategy_id}: {e}")
            return {'error': str(e)}

    def upgrade_strategy_to_deploy(self, strategy_id: int) -> bool:
        """
        Upgrade a strategy from CONDITIONAL to DEPLOY quality.

        Returns True if upgrade successful, False otherwise.
        """
        try:
            conn = sqlite.connect(self.db_path)
            cursor = conn.cursor()

            # Update passed_validation to 2 (DEPLOY quality)
            cursor.execute("""
                UPDATE perpetual_discoveries
                SET passed_validation = 2,
                    validation_failures = 'Upgraded from CONDITIONAL based on performance monitoring'
                WHERE id = ?
            """, (strategy_id,))

            conn.commit()
            conn.close()

            logger.info(f"✅ Strategy {strategy_id} upgraded to DEPLOY quality")

            # Update performance history
            if strategy_id in self.strategy_histories:
                history = self.strategy_histories[strategy_id]
                history.quality_level = StrategyQuality.DEPLOY
                history.last_upgrade_at = datetime.now()
                history.upgrade_count += 1
                logger.info(f"Updated performance history for strategy {strategy_id}")

            return True

        except Exception as e:
            logger.error(f"Error upgrading strategy {strategy_id}: {e}")
            return False

    def downgrade_strategy_to_conditional(self, strategy_id: int) -> bool:
        """
        Downgrade a strategy from DEPLOY to CONDITIONAL due to poor performance.

        Returns True if downgrade successful, False otherwise.
        """
        try:
            conn = sqlite.connect(self.db_path)
            cursor = conn.cursor()

            # Update passed_validation back to 1 (CONDITIONAL quality)
            cursor.execute("""
                UPDATE perpetual_discoveries
                SET passed_validation = 1,
                    validation_failures = 'Downgraded from DEPLOY based on performance degradation'
                WHERE id = ?
            """, (strategy_id,))

            conn.commit()
            conn.close()

            logger.warning(f"⚠️  Strategy {strategy_id} downgraded to CONDITIONAL quality")

            # Update performance history
            if strategy_id in self.strategy_histories:
                history = self.strategy_histories[strategy_id]
                history.quality_level = StrategyQuality.CONDITIONAL
                history.last_upgrade_at = datetime.now()
                history.downgrade_count += 1
                logger.info(f"Updated performance history for strategy {strategy_id}")

            return True

        except Exception as e:
            logger.error(f"Error downgrading strategy {strategy_id}: {e}")
            return False

    def get_upgrade_recommendation(self, strategy_id: int) -> Dict[str, Any]:
        """
        Get detailed upgrade recommendation with reasoning.
        """
        evaluation = self.evaluate_strategy_performance(strategy_id)

        if 'error' in evaluation:
            return evaluation

        recommendation = evaluation['recommendation']
        reasoning = []

        if recommendation == "UPGRADE_TO_DEPLOY":
            # Add reasoning
            checks = evaluation.get('upgrade_checks', {})
            passed = [k for k, v in checks.items() if v]
            failed = [k for k, v in checks.items() if not v]

            reasoning.append(f"Strategy meets {len(passed)}/{len(checks)} upgrade criteria")
            reasoning.append(f"Passed: {', '.join(passed)}")
            reasoning.append(f"Failed: {', '.join(failed) if failed else 'none'}")

        elif recommendation == "KEEP_CONDITIONAL":
            reasoning.append("Strategy needs more monitoring time")
            reasoning.append("Must meet 80% of upgrade criteria to upgrade")

        return {
            'recommendation': recommendation,
            'reasoning': reasoning,
            'metrics': evaluation
        }

    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get overall monitoring system status."""
        conditional_strategies = self.get_conditional_strategies()

        # Evaluate each strategy
        evaluations = []
        for strategy in conditional_strategies:
            eval_result = self.evaluate_strategy_performance(strategy['id'])
            if 'error' not in eval_result:
                evaluations.append({
                    'strategy_id': strategy['id'],
                    'strategy_name': strategy['name'],
                    'current_return': eval_result.get('total_return_pct', 0),
                    'sharpe': eval_result.get('sharpe_ratio', 0),
                    'recommendation': eval_result.get('recommendation', 'UNKNOWN')
                })

        return {
            'monitoring_active': True,
            'conditional_strategies_count': len(conditional_strategies),
            'evaluations': evaluations,
            'timestamp': datetime.now().isoformat()
        }


# Singleton instance
_monitoring_system: StrategyMonitoringSystem = None


def get_strategy_monitoring_system() -> StrategyMonitoringSystem:
    """Get the global strategy monitoring system instance."""
    global _monitoring_system
    if _monitoring_system is None:
        _monitoring_system = StrategyMonitoringSystem()
    return _monitoring_system
