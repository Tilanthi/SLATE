#!/usr/bin/env python3
"""
SLATE Discovery Persistent Memory System

Stores edge discoveries as a knowledge graph for persistent memory across cycles.
Enables learning, relationship mapping, and temporal tracking of discovered edges.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryMemoryNode:
    """A node in the discovery knowledge graph."""
    id: str
    edge_type: str
    edge_description: str

    # Performance metrics
    total_profit_usdt: float
    total_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    beat_market: bool
    vs_buy_hold_usdt: float

    # Validation
    monte_carlo_win_rate: float
    passed_validation: bool

    # Market context
    period_start: str
    period_end: str
    start_price: float
    end_price: float
    volatility_regime: str

    # Temporal
    timestamp: str
    discovery_cycle: int

    # Relationships
    related_edges: List[str]  # IDs of related edges
    improvements_on: List[str]  # IDs of edges this improves
    similar_to: List[str]  # IDs of similar edges

    def to_graph_dict(self) -> Dict[str, Any]:
        """Convert to graph storage format."""
        return {
            "id": self.id,
            "type": "discovered_edge",
            "properties": {
                "edge_type": self.edge_type,
                "description": self.edge_description,
                "profit_usdt": float(self.total_profit_usdt),
                "return_pct": float(self.total_return_pct),
                "drawdown_pct": float(self.max_drawdown_pct),
                "sharpe": float(self.sharpe_ratio),
                "beat_market": bool(self.beat_market),
                "vs_buy_hold": float(self.vs_buy_hold_usdt),
                "mc_win_rate": float(self.monte_carlo_win_rate),
                "passed": bool(self.passed_validation),
                "start_price": float(self.start_price),
                "end_price": float(self.end_price),
                "volatility_regime": str(self.volatility_regime),
                "timestamp": str(self.timestamp),
                "cycle": int(self.discovery_cycle)
            },
            "relationships": {
                "related_to": list(self.related_edges),
                "improves_on": list(self.improvements_on),
                "similar_to": list(self.similar_to)
            }
        }


class DiscoveryPersistentMemory:
    """
    Persistent memory system for edge discoveries.

    Stores discoveries as a knowledge graph with:
    - Temporal tracking (when was edge discovered?)
    - Performance evolution (how does it perform over time?)
    - Relationships (which edges are similar/improvements?)
    - Market context (what conditions did it work in?)
    """

    def __init__(self, storage_path: str = "./slate_core/palace_data/discoveries"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Knowledge graph storage
        self.graph_file = self.storage_path / "discovery_graph.json"
        self.index_file = self.storage_path / "edge_index.json"

        # Load existing memory
        self.graph = self._load_graph()
        self.edge_index = self._load_index()

        # Cycle counter
        self.current_cycle = self._get_next_cycle()

        logger.info(f"DiscoveryPersistentMemory initialized with {len(self.graph)} nodes")

    def _load_graph(self) -> Dict[str, Dict]:
        """Load existing knowledge graph."""
        if self.graph_file.exists():
            try:
                with open(self.graph_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load graph: {e}")
                return {}
        return {}

    def _load_index(self) -> Dict[str, List[str]]:
        """Load edge index for quick lookup."""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load index: {e}")
                return {}
        return {}

    def _get_next_cycle(self) -> int:
        """Get the next discovery cycle number."""
        if self.graph:
            cycles = [node.get("properties", {}).get("cycle", 0) for node in self.graph.values()]
            return max(cycles) + 1 if cycles else 1
        return 1

    def _generate_edge_id(self, edge_type: str, description: str) -> str:
        """Generate unique ID for an edge."""
        content = f"{edge_type}:{description}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def store_discovery(self, discovery_data: Dict[str, Any]) -> str:
        """
        Store a discovery in persistent memory.

        Creates a knowledge graph node with relationships to similar edges.
        """
        try:
            # Generate edge ID
            edge_type = discovery_data.get("edge_type", "unknown")
            description = discovery_data.get("edge_description", "")
            edge_id = self._generate_edge_id(edge_type, description)

            # Create memory node
            node = DiscoveryMemoryNode(
                id=edge_id,
                edge_type=edge_type,
                edge_description=description,
                total_profit_usdt=discovery_data.get("total_profit_usdt", 0),
                total_return_pct=discovery_data.get("total_return_pct", 0),
                max_drawdown_pct=discovery_data.get("max_drawdown_pct", 0),
                sharpe_ratio=discovery_data.get("sharpe_ratio", 0),
                beat_market=discovery_data.get("beat_market", False),
                vs_buy_hold_usdt=discovery_data.get("vs_buy_hold_usdt", 0),
                monte_carlo_win_rate=discovery_data.get("monte_carlo_win_rate", 0),
                passed_validation=discovery_data.get("passed_validation", False),
                period_start=discovery_data.get("period_start", ""),
                period_end=discovery_data.get("period_end", ""),
                start_price=discovery_data.get("start_price", 0),
                end_price=discovery_data.get("end_price", 0),
                volatility_regime=discovery_data.get("volatility_regime", "unknown"),
                timestamp=datetime.now().isoformat(),
                discovery_cycle=self.current_cycle,
                related_edges=[],
                improvements_on=[],
                similar_to=[]
            )

            # Find relationships
            related = self._find_related_edges(node)
            node.related_edges = related["related"]
            node.improvements_on = related["improves"]
            node.similar_to = related["similar"]

            # Store in graph
            self.graph[edge_id] = node.to_graph_dict()

            # Update index
            if edge_type not in self.edge_index:
                self.edge_index[edge_type] = []
            if edge_id not in self.edge_index[edge_type]:
                self.edge_index[edge_type].append(edge_id)

            # Persist to disk
            self._save_memory()

            logger.info(f"Stored discovery in persistent memory: {description} (ID: {edge_id})")
            return edge_id

        except Exception as e:
            logger.error(f"Error storing discovery: {e}")
            return ""

    def _find_related_edges(self, node: DiscoveryMemoryNode) -> Dict[str, List[str]]:
        """Find related edges in the knowledge graph."""
        related = []
        improves = []
        similar = []

        for existing_id, existing_node in self.graph.items():
            existing_props = existing_node.get("properties", {})

            # Same type
            if existing_props.get("edge_type") == node.edge_type:
                # Check if this is an improvement
                if existing_props.get("passed_validation"):
                    if node.total_profit_usdt > existing_props.get("profit_usdt", 0):
                        improves.append(existing_id)

                # Check similarity (same type, similar performance)
                profit_diff = abs(node.total_profit_usdt - existing_props.get("profit_usdt", 0))
                if profit_diff < 100:  # Within $100
                    similar.append(existing_id)

                # Always related if same type
                related.append(existing_id)

        return {
            "related": related,
            "improves": improves,
            "similar": similar
        }

    def _save_memory(self):
        """Persist memory to disk."""
        try:
            with open(self.graph_file, 'w') as f:
                json.dump(self.graph, f, indent=2)

            with open(self.index_file, 'w') as f:
                json.dump(self.edge_index, f, indent=2)

        except Exception as e:
            logger.error(f"Error saving memory: {e}")

    def query_by_performance(self, min_profit_usdt: float = 0) -> List[Dict]:
        """Query edges by minimum profit."""
        results = []
        for node_id, node in self.graph.items():
            props = node.get("properties", {})
            if props.get("profit_usdt", 0) >= min_profit_usdt:
                results.append({
                    "id": node_id,
                    **props
                })
        return sorted(results, key=lambda x: x.get("profit_usdt", 0), reverse=True)

    def query_by_type(self, edge_type: str) -> List[Dict]:
        """Query edges by type."""
        results = []
        edge_ids = self.edge_index.get(edge_type, [])
        for edge_id in edge_ids:
            if edge_id in self.graph:
                node = self.graph[edge_id]
                results.append({
                    "id": edge_id,
                    **node.get("properties", {})
                })
        return results

    def query_market_beaters(self) -> List[Dict]:
        """Query edges that beat buy-hold."""
        results = []
        for node_id, node in self.graph.items():
            props = node.get("properties", {})
            if props.get("beat_market", False):
                results.append({
                    "id": node_id,
                    **props
                })
        return sorted(results, key=lambda x: x.get("vs_buy_hold", 0), reverse=True)

    def get_statistics(self) -> Dict[str, Any]:
        """Get memory statistics."""
        total_nodes = len(self.graph)

        by_type = defaultdict(int)
        passed = 0
        market_beaters = 0
        total_profit = 0

        for node in self.graph.values():
            props = node.get("properties", {})
            edge_type = props.get("edge_type", "unknown")
            by_type[edge_type] += 1

            if props.get("passed_validation", False):
                passed += 1

            if props.get("beat_market", False):
                market_beaters += 1

            total_profit += props.get("profit_usdt", 0)

        return {
            "total_edges": total_nodes,
            "passed_validation": passed,
            "market_beaters": market_beaters,
            "total_profit_usdt": total_profit,
            "by_type": dict(by_type),
            "current_cycle": self.current_cycle
        }

    def get_edge_history(self, edge_id: str) -> List[Dict]:
        """Get history of an edge across cycles."""
        if edge_id not in self.graph:
            return []

        # This edge
        node = self.graph[edge_id]

        # Similar edges (same type, similar description)
        similar = []
        for sim_id in node.get("relationships", {}).get("similar_to", []):
            if sim_id in self.graph:
                similar.append(self.graph[sim_id])

        return [node] + similar

    def cleanup_old_cycles(self, keep_cycles: int = 10):
        """Clean up data from old cycles, keeping only recent."""
        if not self.graph:
            return

        current_cycle = self.current_cycle
        min_cycle = current_cycle - keep_cycles

        to_remove = []
        for node_id, node in self.graph.items():
            props = node.get("properties", {})
            cycle = props.get("cycle", 0)
            if cycle < min_cycle and not props.get("passed_validation", False):
                # Keep passed edges, remove failed old ones
                to_remove.append(node_id)

        for node_id in to_remove:
            del self.graph[node_id]
            # Remove from index
            for edge_type, ids in self.edge_index.items():
                if node_id in ids:
                    ids.remove(node_id)

        if to_remove:
            self._save_memory()
            logger.info(f"Cleaned up {len(to_remove)} old discovery nodes")


# Global memory instance
_memory: Optional[DiscoveryPersistentMemory] = None


def get_discovery_memory() -> DiscoveryPersistentMemory:
    """Get or create the global discovery memory instance."""
    global _memory
    if _memory is None:
        _memory = DiscoveryPersistentMemory()
    return _memory
