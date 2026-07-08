"""
Swarm Intelligence Discovery API Endpoints

REST API endpoints for swarm-based strategy discovery system.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/swarm", tags=["swarm"])

# Global swarm coordinator reference
_swarm_coordinator = None

def set_swarm_coordinator(coordinator):
    """Set the global swarm coordinator reference."""
    global _swarm_coordinator
    _swarm_coordinator = coordinator

@router.post("/start")
async def start_swarm_discovery(
    num_agents: int = 63,
    duration_minutes: int = 60
) -> Dict[str, Any]:
    """
    Start swarm intelligence discovery process.

    Args:
        num_agents: Number of agents to deploy (default: 63)
        duration_minutes: How long to run swarm discovery (default: 60 minutes)

    Returns:
        Swarm discovery status and configuration
    """
    if _swarm_coordinator is None:
        raise HTTPException(status_code=503, detail="Swarm coordinator not initialized")

    try:
        logger.info(f"🚀 Starting swarm discovery with {num_agents} agents")

        # Deploy swarm if not already deployed
        if len(_swarm_coordinator.agents) == 0:
            deployment = await _swarm_coordinator.deploy_swarm(num_agents)
            logger.info(f"Swarm deployed: {deployment['agents_deployed']} agents")

        return {
            "status": "success",
            "message": "Swarm discovery started",
            "agents_deployed": len(_swarm_coordinator.agents),
            "agent_types": list(set(agent.agent_type for agent in _swarm_coordinator.agents.values())),
            "duration_minutes": duration_minutes
        }

    except Exception as e:
        logger.error(f"Failed to start swarm discovery: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop")
async def stop_swarm_discovery() -> Dict[str, Any]:
    """Stop current swarm discovery process."""
    if _swarm_coordinator is None:
        raise HTTPException(status_code=503, detail="Swarm coordinator not initialized")

    try:
        logger.info("🛑 Stopping swarm discovery")

        # Clear current agents
        agent_count = len(_swarm_coordinator.agents)
        _swarm_coordinator.agents.clear()

        return {
            "status": "success",
            "message": "Swarm discovery stopped",
            "agents_stopped": agent_count
        }

    except Exception as e:
        logger.error(f"Failed to stop swarm discovery: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_swarm_status() -> Dict[str, Any]:
    """Get current swarm discovery status."""
    if _swarm_coordinator is None:
        return {
            "status": "not_initialized",
            "agents_active": 0,
            "pheromone_signals": 0
        }

    try:
        active_pheromones = len([p for p in _swarm_coordinator.pheromone_map if p.is_active()])

        return {
            "status": "active" if len(_swarm_coordinator.agents) > 0 else "idle",
            "agents_active": len(_swarm_coordinator.agents),
            "agent_distribution": {
                agent_type: len([a for a in _swarm_coordinator.agents.values() if a.agent_type == agent_type])
                for agent_type in set(agent.agent_type for agent in _swarm_coordinator.agents.values())
            },
            "pheromone_signals": active_pheromones,
            "total_discovery_cycles": _swarm_coordinator.total_agent_cycles,
            "collective_success_rate": _swarm_coordinator.collective_success_rate,
            "regime_history": [r.value for r in _swarm_coordinator.regime_history[-5:]]  # Last 5 regimes
        }

    except Exception as e:
        logger.error(f"Failed to get swarm status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/intelligence")
async def get_collective_intelligence() -> Dict[str, Any]:
    """Get current collective intelligence from swarm."""
    if _swarm_coordinator is None:
        raise HTTPException(status_code=503, detail="Swarm coordinator not initialized")

    try:
        # Synthesize current collective intelligence
        recent_observations = _swarm_coordinator.collective_memory[-100:] if _swarm_coordinator.collective_memory else []

        return {
            "collective_memory_size": len(_swarm_coordinator.collective_memory),
            "recent_observations": len(recent_observations),
            "pheromone_hotspots": [
                {
                    "location": p.location,
                    "strength": p.strength,
                    "type": p.pheromone_type.value,
                    "agent_diversity": len(set(p.source_agent for p in _swarm_coordinator.pheromone_map if p.location == p.location))
                }
                for p in sorted(_swarm_coordinator.pheromone_map, key=lambda x: x.strength, reverse=True)[:10]
            ],
            "current_regime": _swarm_coordinator.regime_history[-1].value if _swarm_coordinator.regime_history else "unknown",
            "swarm_efficiency": _swarm_coordinator.swarm_efficiency_gain
        }

    except Exception as e:
        logger.error(f"Failed to get collective intelligence: {e}")
        raise HTTPException(status_code=500, detail=str(e))