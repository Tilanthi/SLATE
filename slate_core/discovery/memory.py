"""
SLATE Discovery Memory

Persistent SQLite storage for discovered strategies.
"""

import logging
import sqlite3
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class DiscoveryMemory:
    """
    Persistent storage for discovered strategies using SQLite.

    Stores:
    - Strategy definitions
    - Evaluation results
    - Performance history
    - Method/regime statistics
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "slate_discoveries.db"

        self.db_path = str(db_path)
        self._init_database()

        logger.info(f"Discovery memory initialized at {self.db_path}")

    def _init_database(self):
        """Initialize SQLite database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Strategies table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strategies (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                discovery_method TEXT NOT NULL,
                type TEXT,
                parameters TEXT,
                code TEXT,
                score REAL,
                metrics TEXT,
                statistics TEXT,
                status TEXT DEFAULT 'discovered',
                created_at TEXT,
                updated_at TEXT
            )
        """)

        # Performance history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id TEXT,
                timestamp TEXT,
                return REAL,
                sharpe_ratio REAL,
                max_drawdown REAL,
                win_rate REAL,
                FOREIGN KEY (strategy_id) REFERENCES strategies (id)
            )
        """)

        # Statistics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discovery_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stat_key TEXT UNIQUE,
                stat_value TEXT,
                updated_at TEXT
            )
        """)

        conn.commit()
        conn.close()

    async def save_strategy(self, strategy: Dict) -> str:
        """Save a discovered strategy to memory."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO strategies
                (id, name, discovery_method, type, parameters, score, metrics, statistics, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                strategy.get("id"),
                strategy.get("strategy_name"),
                strategy.get("discovery_method"),
                strategy.get("type"),
                json.dumps(strategy.get("parameters", {})),
                strategy.get("score", 0),
                json.dumps(strategy.get("metrics", {})),
                json.dumps(strategy.get("statistics", {})),
                strategy.get("validated", "discovered"),
                now,
                now
            ))

            conn.commit()
            logger.debug(f"Saved strategy {strategy.get('id')} to memory")

            return strategy.get("id")

        except Exception as e:
            logger.error(f"Error saving strategy: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    async def get_strategy(self, strategy_id: str) -> Optional[Dict]:
        """Get a strategy by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name, discovery_method, type, parameters, score, metrics, statistics, status, created_at
            FROM strategies WHERE id = ?
        """, (strategy_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "id": row[0],
                "name": row[1],
                "discovery_method": row[2],
                "type": row[3],
                "parameters": json.loads(row[4]) if row[4] else {},
                "score": row[5],
                "metrics": json.loads(row[6]) if row[6] else {},
                "statistics": json.loads(row[7]) if row[7] else {},
                "status": row[8],
                "created_at": row[9]
            }

        return None

    async def list_strategies(
        self,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """List all strategies, optionally filtered by status."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if status:
            cursor.execute("""
                SELECT id, name, discovery_method, type, score, status, created_at
                FROM strategies WHERE status = ?
                ORDER BY score DESC
                LIMIT ?
            """, (status, limit))
        else:
            cursor.execute("""
                SELECT id, name, discovery_method, type, score, status, created_at
                FROM strategies
                ORDER BY score DESC
                LIMIT ?
            """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row[0],
                "name": row[1],
                "discovery_method": row[2],
                "type": row[3],
                "score": row[4],
                "status": row[5],
                "created_at": row[6]
            }
            for row in rows
        ]

    async def update_strategy_status(
        self,
        strategy_id: str,
        status: str
    ):
        """Update strategy status."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE strategies SET status = ?, updated_at = ?
            WHERE id = ?
        """, (status, datetime.now().isoformat(), strategy_id))

        conn.commit()
        conn.close()

    async def delete_strategy(self, strategy_id: str):
        """Delete a strategy from memory."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM strategies WHERE id = ?", (strategy_id,))
        cursor.execute("DELETE FROM performance_history WHERE strategy_id = ?", (strategy_id,))

        conn.commit()
        conn.close()

        logger.info(f"Deleted strategy {strategy_id}")

    async def get_stats_by_method(self) -> Dict[str, int]:
        """Get statistics by discovery method."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT discovery_method, COUNT(*) as count
            FROM strategies
            GROUP BY discovery_method
        """)

        return {row[0]: row[1] for row in cursor.fetchall()}

    async def get_stats_by_regime(self) -> Dict[str, int]:
        """Get statistics by target regime."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT type, COUNT(*) as count
            FROM strategies
            GROUP BY type
        """)

        return {row[0]: row[1] for row in cursor.fetchall()}
