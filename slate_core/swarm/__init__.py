"""
Swarm Intelligence Discovery Module

Multi-agent collective discovery system for regime-adaptive strategy discovery.
"""

from .swarm_discovery import (
    SwarmIntelligenceCoordinator,
    DiscoveryAgent,
    RegimeType,
    PheromoneType,
    PheromoneSignal,
    get_swarm_coordinator
)

__all__ = [
    'SwarmIntelligenceCoordinator',
    'DiscoveryAgent',
    'RegimeType',
    'PheromoneType',
    'PheromoneSignal',
    'get_swarm_coordinator'
]