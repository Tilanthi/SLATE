"""
Shared Candidate Queue for Bidirectional Self-Evolution

Provides a bridge between:
- Self-evolving discovery (generates evolved candidates)
- Realistic discovery (tests candidates against real data)

Creates a continuous feedback loop:
1. Realistic discovery tests strategies → stores results
2. Self-evolving reads results → evolves new candidates
3. Evolved candidates queued for testing
4. Results stored → cycle repeats
"""

import asyncio
import logging
from typing import List, Dict, Optional, Deque
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime
import json

logger = logging.getLogger(__name__)


@dataclass
class QueuedCandidate:
    """A candidate strategy queued for testing."""
    id: str
    name: str
    type: str
    timeframe: str
    parameters: Dict
    source: str  # 'self_evolving', 'parameter_variation', etc.
    confidence: float
    expected_return: float
    sharpe_ratio: float
    generation: int
    timestamp: str
    status: str = "queued"  # queued, testing, completed, failed


class CandidateQueue:
    """
    Thread-safe queue for sharing candidates between discovery systems.
    """

    def __init__(self, max_size: int = 100):
        self.queue: Deque[QueuedCandidate] = deque()
        self.max_size = max_size
        self.lock = asyncio.Lock()

        # Statistics
        self.total_added = 0
        self.total_tested = 0
        self.by_source = {}
        self.by_type = {}

        logger.info(f"CandidateQueue initialized (max_size={max_size})")

    async def add_candidate(self, candidate: QueuedCandidate) -> bool:
        """Add a candidate to the queue."""
        async with self.lock:
            if len(self.queue) >= self.max_size:
                logger.warning(f"Queue full ({len(self.queue)}/{self.max_size}), rejecting candidate {candidate.id}")
                return False

            self.queue.append(candidate)
            self.total_added += 1

            # Track statistics
            self.by_source[candidate.source] = self.by_source.get(candidate.source, 0) + 1
            self.by_type[candidate.type] = self.by_type.get(candidate.type, 0) + 1

            logger.info(f"Added candidate {candidate.id} ({candidate.type} from {candidate.source}) - Queue size: {len(self.queue)}")
            return True

    async def get_candidates(self, count: int = 1) -> List[QueuedCandidate]:
        """Get candidates from the queue for testing."""
        async with self.lock:
            if not self.queue:
                return []

            candidates = []
            for _ in range(min(count, len(self.queue))):
                if self.queue:
                    candidate = self.queue.popleft()
                    candidate.status = "testing"
                    candidates.append(candidate)

            logger.info(f"Retrieved {len(candidates)} candidates for testing - Queue size: {len(self.queue)}")
            return candidates

    async def mark_completed(self, candidate_id: str, success: bool):
        """Mark a candidate as completed (success or failed)."""
        async with self.lock:
            self.total_tested += 1
            logger.info(f"Marked candidate {candidate_id} as {'completed' if success else 'failed'}")

    def get_statistics(self) -> Dict:
        """Get queue statistics."""
        return {
            "queue_size": len(self.queue),
            "max_size": self.max_size,
            "total_added": self.total_added,
            "total_tested": self.total_tested,
            "by_source": self.by_source,
            "by_type": self.by_type,
            "utilization": len(self.queue) / self.max_size if self.max_size > 0 else 0
        }

    def clear(self):
        """Clear the queue."""
        self.queue.clear()
        logger.info("Queue cleared")


# Global singleton instance
_candidate_queue: Optional[CandidateQueue] = None


def get_candidate_queue() -> CandidateQueue:
    """Get the global candidate queue instance."""
    global _candidate_queue
    if _candidate_queue is None:
        _candidate_queue = CandidateQueue()
    return _candidate_queue
