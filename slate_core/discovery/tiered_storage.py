"""
Tiered Storage System for SLATE Discovery

Dramatically reduces database size by storing only what's needed for evolution:
- Tier 1: Full detail for recent 100 + best 100 by Sharpe (for analysis & dashboard)
- Tier 2: Summary stats only for older records (for evolution)

Reduces storage from ~40KB/record to ~1KB/record for archived records.
"""

import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class TieredDiscoveryStorage:
    """Efficient tiered storage for discovery results."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "slate_realistic_discoveries.db"

        self.db_path = str(db_path)
        self._init_database()

    def _init_database(self):
        """Initialize database schema with optimized storage."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Main results table with full detail
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discovery_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id TEXT NOT NULL,
                strategy_name TEXT NOT NULL,
                strategy_type TEXT NOT NULL,
                timeframe TEXT NOT NULL,

                -- Evaluation metadata
                evaluation_type TEXT NOT NULL,
                num_paths INTEGER DEFAULT 1,
                timestamp TEXT NOT NULL,
                discovery_cycle INTEGER,

                -- Performance metrics (essential for evolution)
                total_return REAL,
                sharpe_ratio REAL,
                sortino_ratio REAL,
                max_drawdown REAL,
                equity_smoothness REAL,
                calmar_ratio REAL,
                win_rate REAL,
                profit_factor REAL,
                avg_trade REAL,
                volatility REAL,
                var_95 REAL,
                cvar_95 REAL,

                -- Multi-path specific metrics
                mean_return REAL,
                std_return REAL,
                min_return REAL,
                max_return REAL,
                median_return REAL,
                mean_sharpe REAL,
                std_sharpe REAL,
                min_sharpe REAL,
                max_sharpe REAL,
                mean_max_drawdown REAL,
                std_max_drawdown REAL,
                worst_max_drawdown REAL,

                -- Robustness metrics
                robustness_score REAL,
                consistency_ratio REAL,

                -- Confidence intervals
                return_ci_lower REAL,
                return_ci_upper REAL,
                sharpe_ci_lower REAL,
                sharpe_ci_upper REAL,

                -- Strategy parameters (ESSENTIAL for evolution!)
                parameters TEXT,

                -- Detailed data (large fields - can be archived)
                equity_curve TEXT,
                trades TEXT,
                path_wise_results TEXT,

                -- Storage tier management
                storage_tier TEXT DEFAULT 'full',  -- 'full' or 'archived'
                archived_at TEXT,

                -- Validation
                is_realistic INTEGER DEFAULT 1,
                validation_failures INTEGER DEFAULT 0,

                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Indexes for efficient queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_storage_tier
            ON discovery_results(storage_tier, timestamp DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sharpe_tier
            ON discovery_results(sharpe_ratio DESC, storage_tier)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_strategy_type
            ON discovery_results(strategy_type, timestamp DESC)
        """)

        conn.commit()
        conn.close()

        logger.info(f"Tiered storage initialized at {self.db_path}")

    def save_result(self, result: Dict, discovery_cycle: int) -> int:
        """Save a result with full detail initially."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Extract parameters first
            parameters = result.get('parameters', {})
            if not parameters:
                # Try to extract from strategy dict if available
                # This is a fallback for compatibility
                parameters = {}

            # Convert complex objects to JSON
            parameters_json = json.dumps(parameters)
            equity_curve_json = json.dumps(result.get('equity_curve', []))
            trades_json = json.dumps(result.get('trades', []))
            path_wise_json = json.dumps(result.get('path_wise_results', []))

            cursor.execute("""
                INSERT INTO discovery_results (
                    strategy_id, strategy_name, strategy_type, timeframe,
                    evaluation_type, num_paths, timestamp, discovery_cycle,

                    -- Performance metrics
                    total_return, sharpe_ratio, sortino_ratio, max_drawdown,
                    equity_smoothness, calmar_ratio, win_rate, profit_factor,
                    avg_trade, volatility, var_95, cvar_95,

                    -- Multi-path metrics
                    mean_return, std_return, min_return, max_return, median_return,
                    mean_sharpe, std_sharpe, min_sharpe, max_sharpe,
                    mean_max_drawdown, std_max_drawdown, worst_max_drawdown,

                    -- Robustness metrics
                    robustness_score, consistency_ratio,

                    -- Confidence intervals
                    return_ci_lower, return_ci_upper,
                    sharpe_ci_lower, sharpe_ci_upper,

                    -- Additional data
                    parameters, equity_curve, trades, path_wise_results,

                    -- Validation
                    is_realistic, validation_failures
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.get('strategy_id'),
                result.get('strategy_name'),
                result.get('strategy_type'),
                result.get('timeframe', '1m'),

                result.get('evaluation_type', 'singlepath'),
                result.get('num_paths', 1),
                result.get('timestamp', datetime.now().isoformat()),
                discovery_cycle,

                # Performance
                result.get('total_return'),
                result.get('sharpe_ratio'),
                result.get('sortino_ratio'),
                result.get('max_drawdown'),
                result.get('equity_curve_smoothness'),
                result.get('calmar_ratio'),
                result.get('win_rate'),
                result.get('profit_factor'),
                result.get('avg_trade'),
                result.get('volatility'),
                result.get('var_95'),
                result.get('cvar_95'),

                # Multi-path
                result.get('mean_return'),
                result.get('std_return'),
                result.get('min_return'),
                result.get('max_return'),
                result.get('median_return'),
                result.get('mean_sharpe'),
                result.get('std_sharpe'),
                result.get('min_sharpe'),
                result.get('max_sharpe'),
                result.get('mean_max_drawdown'),
                result.get('std_max_drawdown'),
                result.get('worst_max_drawdown'),

                # Robustness
                result.get('robustness_score'),
                result.get('consistency_ratio'),

                # Confidence intervals
                result.get('return_ci_lower'),
                result.get('return_ci_upper'),
                result.get('sharpe_ci_lower'),
                result.get('sharpe_ci_upper'),

                # Additional data
                parameters_json,
                equity_curve_json,
                trades_json,
                path_wise_json,

                # Validation
                1,  # is_realistic
                0   # validation_failures
            ))

            row_id = cursor.lastrowid
            conn.commit()
            return row_id

        except Exception as e:
            logger.error(f"Failed to save result: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def archive_old_results(self,
                          keep_recent: int = 100,
                          keep_best: int = 100,
                          max_age_days: int = 7) -> Dict:
        """
        Archive old results by removing large data fields.

        Keeps:
        - Most recent N records (full detail)
        - Best N records by Sharpe (full detail)
        - Summary stats for everything else

        Returns summary of what was archived.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Get current stats
            cursor.execute("SELECT COUNT(*) FROM discovery_results WHERE storage_tier = 'full'")
            full_count_before = cursor.fetchone()[0]

            # Archive records that are:
            # 1. Not in the most recent N
            # 2. Not in the best N by Sharpe
            # 3. Older than max_age_days
            cutoff_date = (datetime.now() - timedelta(days=max_age_days)).isoformat()

            cursor.execute("""
                UPDATE discovery_results
                SET storage_tier = 'archived',
                    archived_at = ?,
                    equity_curve = NULL,
                    trades = NULL,
                    path_wise_results = NULL
                WHERE id IN (
                    SELECT id FROM discovery_results
                    WHERE storage_tier = 'full'
                    AND id NOT IN (
                        -- Keep most recent
                        SELECT id FROM discovery_results
                        WHERE storage_tier = 'full'
                        ORDER BY timestamp DESC
                        LIMIT ?
                    )
                    AND id NOT IN (
                        -- Keep best by Sharpe
                        SELECT id FROM discovery_results
                        WHERE storage_tier = 'full'
                        ORDER BY sharpe_ratio DESC
                        LIMIT ?
                    )
                    AND timestamp < ?
                )
            """, (datetime.now().isoformat(), keep_recent, keep_best, cutoff_date))

            archived_count = cursor.rowcount

            # Get stats after archiving
            cursor.execute("SELECT COUNT(*) FROM discovery_results WHERE storage_tier = 'full'")
            full_count_after = cursor.fetchone()[0]

            # Calculate space saved
            cursor.execute("""
                SELECT
                    COUNT(*) as total_records,
                    SUM(CASE WHEN storage_tier = 'full' THEN 1 ELSE 0 END) as full_records,
                    SUM(CASE WHEN storage_tier = 'archived' THEN 1 ELSE 0 END) as archived_records
                FROM discovery_results
            """)
            stats = cursor.fetchone()

            # Commit the changes
            conn.commit()

            conn.close()

            # Vacuum to reclaim space (outside of transaction)
            conn = sqlite3.connect(self.db_path)
            conn.execute("VACUUM")
            conn.close()

            return {
                'archived_count': archived_count,
                'full_count_before': full_count_before,
                'full_count_after': full_count_after,
                'total_records': stats[0],
                'full_records': stats[1],
                'archived_records': stats[2],
                'space_saved_mb': archived_count * 39 / (1024 * 1024)  # ~39KB per record
            }

        except Exception as e:
            logger.error(f"Failed to archive results: {e}")
            conn.rollback()
            conn.close()
            raise

    def get_best_parameters(self, strategy_type: str, limit: int = 10) -> List[Dict]:
        """Get best performing parameters for a strategy type (for evolution)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT
                    strategy_id, strategy_name, strategy_type, timeframe,
                    sharpe_ratio, total_return, max_drawdown,
                    robustness_score, consistency_ratio,
                    parameters, timestamp
                FROM discovery_results
                WHERE strategy_type = ?
                  AND parameters IS NOT NULL
                  AND json_extract(parameters, '$') != '{}'
                ORDER BY
                    CASE WHEN evaluation_type = 'multipath' THEN 1 ELSE 0 END DESC,
                    COALESCE(robustness_score, sharpe_ratio) DESC
                LIMIT ?
            """, (strategy_type, limit))

            results = []
            for row in cursor.fetchall():
                result = dict(row)
                # Parse parameters JSON
                try:
                    result['parameters'] = json.loads(result['parameters'])
                except:
                    result['parameters'] = {}
                results.append(result)

            return results

        finally:
            conn.close()

    def get_diversity_stats(self) -> Dict:
        """Get diversity statistics for strategy evolution."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Type distribution
            cursor.execute("""
                SELECT strategy_type, COUNT(*) as count,
                       MAX(sharpe_ratio) as best_sharpe
                FROM discovery_results
                WHERE parameters IS NOT NULL
                  AND json_extract(parameters, '$') != '{}'
                GROUP BY strategy_type
                ORDER BY count DESC
            """)

            type_stats = {}
            for row in cursor.fetchall():
                type_stats[row[0]] = {
                    'count': row[1],
                    'best_sharpe': row[2]
                }

            return type_stats

        finally:
            conn.close()


# Global instance
_tiered_storage = None


def get_tiered_storage() -> TieredDiscoveryStorage:
    """Get the global tiered storage instance."""
    global _tiered_storage
    if _tiered_storage is None:
        _tiered_storage = TieredDiscoveryStorage()
    return _tiered_storage
