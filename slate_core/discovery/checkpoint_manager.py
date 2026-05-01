#!/usr/bin/env python3
"""
SLATE Checkpoint Manager - Crash Recovery for Discovery Cycles

Inspired by TradingAgents' checkpoint resume system, this module provides:
- SQLite-based per-cycle checkpoint storage
- Automatic state saving after each major discovery step
- Resume capability for crashed/interrupted cycles
- Automatic cleanup on successful completion

Checkpoints are stored at: ~/.slate/cache/checkpoints/<cycle_id>.db
"""

import sqlite3
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import hashlib

logger = logging.getLogger(__name__)


# Default checkpoint directory
DEFAULT_CACHE_DIR = Path.home() / ".slate" / "cache" / "checkpoints"


@dataclass
class DiscoveryCheckpoint:
    """Checkpoint state for a discovery cycle."""
    cycle_id: str
    timestamp: str
    stage: str  # 'candidates', 'backtesting', 'monte_carlo', 'complete'
    total_candidates: int
    tested_candidates: int
    current_candidate_index: int
    results: List[Dict[str, Any]]
    error_count: int
    last_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data['results'] = json.dumps(data['results'])
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DiscoveryCheckpoint':
        """Create from dictionary storage."""
        data['results'] = json.loads(data['results'])
        return cls(**data)


class CheckpointManager:
    """
    Manages checkpoint storage and recovery for discovery cycles.

    Based on TradingAgents' checkpoint resume architecture with SQLite
    per-cycle storage and automatic state management.
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize checkpoint manager.

        Args:
            cache_dir: Directory for checkpoint databases. Defaults to ~/.slate/cache/checkpoints
        """
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Current cycle checkpoint
        self.current_cycle_id: Optional[str] = None
        self.current_checkpoint: Optional[DiscoveryCheckpoint] = None
        self._conn: Optional[sqlite3.Connection] = None

        logger.info(f"CheckpointManager initialized with cache dir: {self.cache_dir}")

    def _get_db_path(self, cycle_id: str) -> Path:
        """Get database path for a specific cycle."""
        return self.cache_dir / f"{cycle_id}.db"

    def _init_db(self, cycle_id: str) -> sqlite3.Connection:
        """Initialize checkpoint database for a cycle."""
        db_path = self._get_db_path(cycle_id)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                stage TEXT NOT NULL,
                total_candidates INTEGER NOT NULL,
                tested_candidates INTEGER NOT NULL,
                current_candidate_index INTEGER NOT NULL,
                results TEXT NOT NULL,
                error_count INTEGER NOT NULL,
                last_error TEXT,
                UNIQUE(cycle_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_id TEXT NOT NULL,
                candidate_index INTEGER NOT NULL,
                edge_type TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL,
                result_data TEXT,
                error_message TEXT,
                timestamp TEXT NOT NULL,
                UNIQUE(cycle_id, candidate_index)
            )
        """)

        conn.commit()
        return conn

    @contextmanager
    def get_connection(self, cycle_id: str):
        """Context manager for database connection."""
        conn = self._init_db(cycle_id)
        try:
            yield conn
        finally:
            conn.close()

    def start_cycle(self, total_candidates: int) -> str:
        """
        Start a new discovery cycle with checkpoint tracking.

        Args:
            total_candidates: Total number of candidates to test

        Returns:
            cycle_id: Unique identifier for this cycle
        """
        cycle_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        checkpoint = DiscoveryCheckpoint(
            cycle_id=cycle_id,
            timestamp=timestamp,
            stage='candidates',
            total_candidates=total_candidates,
            tested_candidates=0,
            current_candidate_index=0,
            results=[],
            error_count=0
        )

        with self.get_connection(cycle_id) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO checkpoints
                (cycle_id, timestamp, stage, total_candidates, tested_candidates,
                 current_candidate_index, results, error_count, last_error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cycle_id, timestamp, checkpoint.stage, total_candidates, 0,
                0, json.dumps([]), 0, None
            ))
            conn.commit()

        self.current_cycle_id = cycle_id
        self.current_checkpoint = checkpoint

        logger.info(f"Started discovery cycle {cycle_id} with {total_candidates} candidates")
        return cycle_id

    def save_checkpoint(self, stage: str, tested_index: int,
                       result: Optional[Dict[str, Any]] = None,
                       error: Optional[str] = None) -> None:
        """
        Save checkpoint state after completing a discovery step.

        Args:
            stage: Current discovery stage
            tested_index: Index of the candidate just tested
            result: Optional result data from the tested candidate
            error: Optional error message if testing failed
        """
        if not self.current_cycle_id:
            logger.warning("No active cycle - cannot save checkpoint")
            return

        checkpoint = self.current_checkpoint
        checkpoint.stage = stage
        checkpoint.tested_candidates += 1
        checkpoint.current_candidate_index = tested_index

        if result:
            checkpoint.results.append(result)

        if error:
            checkpoint.error_count += 1
            checkpoint.last_error = error

        # Save to database
        with self.get_connection(self.current_cycle_id) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE checkpoints SET
                    stage = ?,
                    tested_candidates = ?,
                    current_candidate_index = ?,
                    results = ?,
                    error_count = ?,
                    last_error = ?
                WHERE cycle_id = ?
            """, (
                stage, checkpoint.tested_candidates, tested_index,
                json.dumps(checkpoint.results), checkpoint.error_count,
                checkpoint.last_error, self.current_cycle_id
            ))
            conn.commit()

        logger.debug(f"Saved checkpoint at stage {stage}, candidate {tested_index}/{checkpoint.total_candidates}")

    def save_candidate_result(self, candidate_index: int, edge_type: str,
                             description: str, status: str,
                             result_data: Optional[Dict[str, Any]] = None,
                             error_message: Optional[str] = None) -> None:
        """
        Save individual candidate result to checkpoint database.

        Args:
            candidate_index: Index of the candidate
            edge_type: Type of edge being tested
            description: Edge description
            status: Status of the test ('success', 'failed', 'error')
            result_data: Optional result data
            error_message: Optional error message
        """
        if not self.current_cycle_id:
            return

        timestamp = datetime.now().isoformat()

        with self.get_connection(self.current_cycle_id) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO candidates
                (cycle_id, candidate_index, edge_type, description, status,
                 result_data, error_message, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.current_cycle_id, candidate_index, edge_type, description,
                status, json.dumps(result_data) if result_data else None,
                error_message, timestamp
            ))
            conn.commit()

    def load_checkpoint(self, cycle_id: str) -> Optional[DiscoveryCheckpoint]:
        """
        Load checkpoint for a specific cycle.

        Args:
            cycle_id: Cycle identifier to load

        Returns:
            DiscoveryCheckpoint if found, None otherwise
        """
        db_path = self._get_db_path(cycle_id)
        if not db_path.exists():
            logger.warning(f"No checkpoint found for cycle {cycle_id}")
            return None

        with self.get_connection(cycle_id) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT cycle_id, timestamp, stage, total_candidates, tested_candidates,
                       current_candidate_index, results, error_count, last_error
                FROM checkpoints WHERE cycle_id = ?
            """, (cycle_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return DiscoveryCheckpoint(
                cycle_id=row[0],
                timestamp=row[1],
                stage=row[2],
                total_candidates=row[3],
                tested_candidates=row[4],
                current_candidate_index=row[5],
                results=json.loads(row[6]),
                error_count=row[7],
                last_error=row[8]
            )

    def get_incomplete_cycles(self) -> List[Dict[str, Any]]:
        """
        Get all incomplete discovery cycles that can be resumed.

        Returns:
            List of incomplete cycle info dictionaries
        """
        incomplete = []

        for db_file in self.cache_dir.glob("*.db"):
            try:
                conn = sqlite3.connect(str(db_file))
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT cycle_id, timestamp, stage, total_candidates,
                           tested_candidates, error_count, last_error
                    FROM checkpoints
                """)

                row = cursor.fetchone()
                if row:
                    cycle_id, timestamp, stage, total, tested, errors, last_error = row
                    if stage != 'complete' and tested < total:
                        incomplete.append({
                            'cycle_id': cycle_id,
                            'timestamp': timestamp,
                            'stage': stage,
                            'progress': f"{tested}/{total}",
                            'error_count': errors,
                            'last_error': last_error
                        })
                conn.close()
            except Exception as e:
                logger.warning(f"Error reading checkpoint {db_file}: {e}")

        return incomplete

    def mark_complete(self, cycle_id: str) -> None:
        """Mark a discovery cycle as complete and trigger cleanup."""
        with self.get_connection(cycle_id) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE checkpoints SET stage = 'complete' WHERE cycle_id = ?
            """, (cycle_id,))
            conn.commit()

        logger.info(f"Marked cycle {cycle_id} as complete")

    def clear_checkpoint(self, cycle_id: str) -> bool:
        """
        Clear checkpoint database for a specific cycle.

        Args:
            cycle_id: Cycle identifier to clear

        Returns:
            True if cleared, False if not found
        """
        db_path = self._get_db_path(cycle_id)
        if db_path.exists():
            db_path.unlink()
            logger.info(f"Cleared checkpoint for cycle {cycle_id}")
            return True
        return False

    def clear_all_checkpoints(self) -> int:
        """
        Clear all checkpoint databases.

        Returns:
            Number of checkpoints cleared
        """
        count = 0
        for db_file in self.cache_dir.glob("*.db"):
            try:
                db_file.unlink()
                count += 1
            except Exception as e:
                logger.warning(f"Error clearing checkpoint {db_file}: {e}")

        logger.info(f"Cleared {count} checkpoint databases")
        return count

    def can_resume(self, cycle_id: str) -> bool:
        """Check if a cycle can be resumed from checkpoint."""
        checkpoint = self.load_checkpoint(cycle_id)
        if not checkpoint:
            return False
        return checkpoint.stage != 'complete'

    def get_resume_state(self, cycle_id: str) -> Optional[Dict[str, Any]]:
        """
        Get state information needed to resume a cycle.

        Returns:
            Dictionary with resume state or None if not resumable
        """
        checkpoint = self.load_checkpoint(cycle_id)
        if not checkpoint or checkpoint.stage == 'complete':
            return None

        return {
            'cycle_id': checkpoint.cycle_id,
            'stage': checkpoint.stage,
            'resume_from_index': checkpoint.current_candidate_index,
            'completed_results': checkpoint.results,
            'error_count': checkpoint.error_count,
            'last_error': checkpoint.last_error,
            'timestamp': checkpoint.timestamp
        }


# Global checkpoint manager instance
_checkpoint_manager: Optional[CheckpointManager] = None


def get_checkpoint_manager() -> CheckpointManager:
    """Get the global checkpoint manager instance."""
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = CheckpointManager()
    return _checkpoint_manager
