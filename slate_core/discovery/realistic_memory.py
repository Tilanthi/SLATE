"""
SLATE Realistic Discovery Memory

Persistent SQLite storage for realistic discovery results including
multi-path testing, robustness metrics, and confidence intervals.
"""

import sqlite3
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class RealisticDiscoveryMemory:
    """
    Persistent storage for realistic discovery results.

    Stores:
    - Single-path and multi-path backtest results
    - Robustness metrics (robustness_score, consistency_ratio)
    - Confidence intervals
    - Strategy parameters and evolution history
    - Performance tracking across discovery cycles
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "slate_realistic_discoveries.db"

        self.db_path = str(db_path)
        self._init_database()

        logger.info(f"Realistic discovery memory initialized at {self.db_path}")

    def _init_database(self):
        """Initialize SQLite database schema for realistic discoveries."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Main results table (both single-path and multi-path)
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

                -- Performance metrics
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

                -- Multi-path specific metrics (NULL for single-path)
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

                -- Additional data
                parameters TEXT,
                equity_curve TEXT,
                trades TEXT,
                path_wise_results TEXT,

                -- Validation
                is_realistic INTEGER DEFAULT 1,
                validation_failures INTEGER DEFAULT 0,

                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Index for efficient queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_strategy_type
            ON discovery_results(strategy_type, timestamp DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_robustness
            ON discovery_results(robustness_score DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_evaluation_type
            ON discovery_results(evaluation_type, timestamp DESC)
        """)

        # Evolution tracking table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evolution_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_type TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp TEXT NOT NULL,

                -- Best metrics for this type
                best_score REAL,
                best_mean_return REAL,
                best_sharpe REAL,
                best_robustness REAL,

                -- Sample counts
                total_tests INTEGER DEFAULT 0,
                multipath_tests INTEGER DEFAULT 0,

                -- Additional insights
                insights TEXT
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_evolution_type
            ON evolution_history(strategy_type, timestamp DESC)
        """)

        # Statistics summary table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discovery_statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stat_key TEXT UNIQUE,
                stat_value TEXT,
                stat_type TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

        logger.info("Database schema initialized")

    def cleanup_old_records(self, max_records: int = 1000):
        """Keep only the most recent N records to control database size.

        Args:
            max_records: Maximum number of records to keep (default 1000, reduced from 5000)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get current count
        cursor.execute("SELECT COUNT(*) FROM discovery_results")
        current_count = cursor.fetchone()[0]

        if current_count > max_records:
            # Delete oldest records beyond max_records, but keep the best 100 by Sharpe ratio
            cursor.execute("""
                DELETE FROM discovery_results
                WHERE id NOT IN (
                    -- Keep the most recent records
                    SELECT id FROM discovery_results
                    ORDER BY timestamp DESC
                    LIMIT ?
                )
                AND id NOT IN (
                    -- Also keep the best 100 records by Sharpe ratio
                    SELECT id FROM discovery_results
                    ORDER BY sharpe_ratio DESC
                    LIMIT 100
                )
            """, (max_records,))

            deleted = current_count - max_records
            logger.info(f"Cleaned up {deleted} old discovery records (kept {max_records} most recent + best 100)")

            # Vacuum to reclaim space
            cursor.execute("VACUUM")
            conn.commit()

        conn.close()

    def get_database_size(self) -> Dict:
        """Get current database size and record count."""
        import os

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM discovery_results")
        count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT strategy_type) FROM discovery_results")
        types_count = cursor.fetchone()[0]

        conn.close()

        size_bytes = os.path.getsize(self.db_path)
        size_mb = size_bytes / (1024 * 1024)

        return {
            'size_bytes': size_bytes,
            'size_mb': round(size_mb, 2),
            'record_count': count,
            'strategy_types_tested': types_count
        }

    async def save_result(self, result: Dict, discovery_cycle: Optional[int] = None) -> int:
        """Save a discovery result (single-path or multi-path) to the database.

        Args:
            result: BacktestResult or MultiPathResult as dict
            discovery_cycle: Current discovery cycle number

        Returns:
            Row ID of inserted record
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Handle both single-path and multi-path results
            evaluation_type = result.get('evaluation_type', 'singlepath')

            # Convert complex objects to JSON
            parameters_json = json.dumps(result.get('parameters', {}))
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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.get('strategy_id'),
                result.get('strategy_name'),
                result.get('strategy_type'),
                result.get('timeframe', '1m'),

                evaluation_type,
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
                1 if result.get('is_realistic', True) else 0,
                result.get('validation_failures', 0)
            ))

            row_id = cursor.lastrowid
            conn.commit()

            logger.debug(f"Saved result {result.get('strategy_name')} as row {row_id}")
            return row_id

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to save result: {e}")
            raise
        finally:
            conn.close()

    async def save_evolution_snapshot(self, strategy_type: str, timeframe: str,
                                     insights: Dict) -> int:
        """Save evolution progress snapshot.

        Args:
            strategy_type: Type of strategy
            timeframe: Timeframe being tested
            insights: Evolution insights dict

        Returns:
            Row ID of inserted record
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            best_by_type = insights.get('best_by_type', {}).get(strategy_type, {})

            cursor.execute("""
                INSERT INTO evolution_history (
                    strategy_type, timeframe, timestamp,
                    best_score, best_mean_return, best_sharpe, best_robustness,
                    total_tests, multipath_tests, insights
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                strategy_type,
                timeframe,
                datetime.now().isoformat(),
                best_by_type.get('robustness_score') or best_by_type.get('sharpe'),
                best_by_type.get('return') or best_by_type.get('mean_return'),
                best_by_type.get('sharpe') or best_by_type.get('mean_sharpe'),
                best_by_type.get('robustness_score'),
                insights.get('total_tests', 0),
                insights.get('multipath_tests', 0),
                json.dumps(insights)
            ))

            row_id = cursor.lastrowid
            conn.commit()
            return row_id

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to save evolution snapshot: {e}")
            raise
        finally:
            conn.close()

    async def get_top_results(self, limit: int = 20,
                             evaluation_type: Optional[str] = None) -> List[Dict]:
        """Get top performing results.

        Args:
            limit: Maximum number of results
            evaluation_type: Filter by 'singlepath', 'multipath', or None for all

        Returns:
            List of result dicts
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            query = """
                SELECT * FROM discovery_results
                WHERE 1=1
            """

            params = []
            if evaluation_type:
                query += " AND evaluation_type = ?"
                params.append(evaluation_type)

            query += " ORDER BY robustness_score DESC, sharpe_ratio DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            # Get column names
            columns = [desc[0] for desc in cursor.description]

            results = []
            for row in rows:
                result = dict(zip(columns, row))
                # Parse JSON fields
                if result.get('parameters'):
                    result['parameters'] = json.loads(result['parameters'])
                if result.get('equity_curve'):
                    result['equity_curve'] = json.loads(result['equity_curve'])
                if result.get('trades'):
                    result['trades'] = json.loads(result['trades'])
                if result.get('path_wise_results'):
                    result['path_wise_results'] = json.loads(result['path_wise_results'])

                results.append(result)

            return results

        finally:
            conn.close()

    async def get_statistics(self) -> Dict:
        """Get overall discovery statistics.

        Returns:
            Statistics dict with counts and best metrics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Get counts
            cursor.execute("SELECT COUNT(*) FROM discovery_results")
            total = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM discovery_results WHERE evaluation_type = 'multipath'")
            multipath = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM discovery_results WHERE evaluation_type = 'singlepath'")
            singlepath = cursor.fetchone()[0]

            # Get best results
            cursor.execute("""
                SELECT strategy_name, strategy_type, sharpe_ratio, robustness_score,
                       total_return, mean_return, consistency_ratio
                FROM discovery_results
                ORDER BY robustness_score DESC, sharpe_ratio DESC
                LIMIT 1
            """)
            best = cursor.fetchone()

            # Get by type
            cursor.execute("""
                SELECT strategy_type, COUNT(*) as count,
                       MAX(robustness_score) as best_robustness,
                       MAX(sharpe_ratio) as best_sharpe
                FROM discovery_results
                GROUP BY strategy_type
            """)
            by_type = cursor.fetchall()

            return {
                'total_results': total,
                'multipath_results': multipath,
                'singlepath_results': singlepath,
                'best_result': {
                    'name': best[0] if best else None,
                    'type': best[1] if best else None,
                    'sharpe': best[2] if best else None,
                    'robustness': best[3] if best else None,
                    'return': best[4] if best else None,
                    'mean_return': best[5] if best else None,
                    'consistency': best[6] if best else None,
                } if best else None,
                'by_type': [
                    {
                        'type': row[0],
                        'count': row[1],
                        'best_robustness': row[2],
                        'best_sharpe': row[3]
                    }
                    for row in by_type
                ]
            }

        finally:
            conn.close()

    async def get_best_parameters(self, strategy_type: str) -> Optional[Dict]:
        """Get best performing parameters for a strategy type.

        Args:
            strategy_type: Type of strategy

        Returns:
            Best result dict or None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM discovery_results
                WHERE strategy_type = ?
                ORDER BY robustness_score DESC, sharpe_ratio DESC
                LIMIT 1
            """, (strategy_type,))

            row = cursor.fetchone()
            if not row:
                return None

            columns = [desc[0] for desc in cursor.description]
            result = dict(zip(columns, row))

            # Parse JSON fields
            if result.get('parameters'):
                result['parameters'] = json.loads(result['parameters'])

            return result

        finally:
            conn.close()


# Global instance
_realistic_discovery_memory = None


def get_realistic_discovery_memory() -> RealisticDiscoveryMemory:
    """Get the global realistic discovery memory instance."""
    global _realistic_discovery_memory
    if _realistic_discovery_memory is None:
        _realistic_discovery_memory = RealisticDiscoveryMemory()
    return _realistic_discovery_memory
