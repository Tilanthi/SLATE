#!/usr/bin/env python3
"""
SLATE Adaptive Discovery API Endpoints

API endpoints for the adaptive learning discovery system.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Optional
import logging
from datetime import datetime

from .adaptive_learning import get_adaptive_learning_engine
from .adaptive_discovery import AdaptiveContinuousDiscovery, AdaptiveDiscoveryConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/adaptive-discovery", tags=["adaptive-discovery"])


@router.post("/analyze")
async def run_learning_analysis():
    """Run adaptive learning analysis and update allocations."""
    engine = get_adaptive_learning_engine()

    result = await engine.analyze_and_learn()

    return {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "analysis_result": result
    }


@router.get("/status")
async def get_adaptive_status():
    """Get current adaptive learning status."""
    engine = get_adaptive_learning_engine()

    return {
        "status": "active",
        "last_analysis": engine.last_analysis_time.isoformat() if engine.last_analysis_time else None,
        "regime_change_detected": engine.regime_change_detected,
        "performance_summary": engine._get_performance_summary(),
        "config": {
            "exploitation_ratio": engine.exploitation_ratio,
            "min_exploration_budget": engine.min_exploration_budget
        }
    }


@router.get("/allocations")
async def get_resource_allocations():
    """Get current resource allocation for discovery cycles."""
    engine = get_adaptive_learning_engine()

    if not engine.resource_allocations:
        # Run analysis if no allocations exist
        await engine.analyze_and_learn()

    allocations = []

    for key, alloc in engine.resource_allocations.items():
        strategy_type, timeframe = key
        allocations.append({
            "strategy_type": strategy_type,
            "timeframe": timeframe,
            "allocation_percent": alloc.allocation_percent,
            "min_allocation": alloc.min_allocation,
            "max_allocation": alloc.max_allocation,
            "reason": alloc.allocation_reason
        })

    # Sort by allocation percentage
    allocations.sort(key=lambda x: x['allocation_percent'], reverse=True)

    return {
        "total_allocations": len(allocations),
        "allocations": allocations[:20],  # Top 20
        "exploitation_targets": len([
            a for a in allocations
            if "exploitation" in a.get('reason', '')
        ]),
        "exploration_areas": len([
            a for a in allocations
            if "exploration" in a.get('reason', '')
        ])
    }


@router.get("/performance")
async def get_performance_profiles():
    """Get performance profiles for all strategy types/timeframes."""
    engine = get_adaptive_learning_engine()

    profiles = []

    for key, profile in engine.performance_profiles.items():
        strategy_type, timeframe = key
        profiles.append({
            "strategy_type": strategy_type,
            "timeframe": timeframe,
            "total_tests": profile.total_tests,
            "successful_tests": profile.successful_tests,
            "success_rate": profile.success_rate(),
            "avg_sharpe": profile.avg_sharpe,
            "avg_return": profile.avg_return,
            "avg_win_rate": profile.avg_win_rate,
            "best_sharpe": profile.best_sharpe,
            "recent_trend": profile.recent_trend(),
            "parameter_ranges": profile.parameter_ranges,
            "last_update": profile.last_update.isoformat()
        })

    # Sort by average Sharpe
    profiles.sort(key=lambda x: x['avg_sharpe'], reverse=True)

    return {
        "total_profiles": len(profiles),
        "profiles": profiles[:30]  # Top 30
    }


@router.get("/insights")
async def get_learning_insights():
    """Get current learning insights and recommendations."""
    engine = get_adaptive_learning_engine()

    # Run analysis if needed
    if not engine.last_analysis_time:
        await engine.analyze_and_learn()

    # Get insights
    insights = await engine._generate_insights()

    return {
        "timestamp": datetime.now().isoformat(),
        "regime_change_detected": engine.regime_change_detected,
        "insights": insights,
        "summary": engine._get_performance_summary()
    }


@router.get("/parameters/{strategy_type}/{timeframe}")
async def get_suggested_parameters(strategy_type: str, timeframe: str):
    """Get suggested parameter ranges for a strategy type/timeframe."""
    engine = get_adaptive_learning_engine()

    params = engine.get_suggested_parameters(strategy_type, timeframe)

    if not params:
        raise HTTPException(
            status_code=404,
            detail=f"No parameter data available for {strategy_type} @ {timeframe}"
        )

    return {
        "strategy_type": strategy_type,
        "timeframe": timeframe,
        "parameter_ranges": params
    }


@router.post("/start")
async def start_adaptive_discovery(
    cycles: int = 50,
    exploitation_ratio: float = 0.75,
    min_exploration_budget: float = 0.05
):
    """Start adaptive discovery with specified parameters."""
    config = AdaptiveDiscoveryConfig(
        cycles_per_analysis=50,
        exploitation_ratio=exploitation_ratio,
        min_exploration_budget=min_exploration_budget
    )

    discovery = AdaptiveContinuousDiscovery(config)

    # Start in background
    import asyncio
    asyncio.create_task(discovery.start_discovery(cycles))

    return {
        "status": "started",
        "cycles": cycles,
        "config": {
            "exploitation_ratio": exploitation_ratio,
            "min_exploration_budget": min_exploration_budget
        }
    }


@router.get("/config")
async def get_adaptive_config():
    """Get current adaptive discovery configuration."""
    engine = get_adaptive_learning_engine()

    return {
        "learning_engine": {
            "exploitation_ratio": engine.exploitation_ratio,
            "min_exploration_budget": engine.min_exploration_budget,
            "analysis_interval_hours": engine.analysis_interval_hours
        },
        "strategy_types": engine.strategy_types,
        "timeframes": engine.timeframes
    }


@router.post("/config")
async def update_adaptive_config(
    exploitation_ratio: Optional[float] = None,
    min_exploration_budget: Optional[float] = None
):
    """Update adaptive learning configuration."""
    engine = get_adaptive_learning_engine()

    if exploitation_ratio is not None:
        if 0.5 <= exploitation_ratio <= 0.9:
            engine.exploitation_ratio = exploitation_ratio
        else:
            raise HTTPException(
                status_code=400,
                detail="exploitation_ratio must be between 0.5 and 0.9"
            )

    if min_exploration_budget is not None:
        if 0.01 <= min_exploration_budget <= 0.2:
            engine.min_exploration_budget = min_exploration_budget
        else:
            raise HTTPException(
                status_code=400,
                detail="min_exploration_budget must be between 0.01 and 0.2"
            )

    return {
        "status": "updated",
        "config": {
            "exploitation_ratio": engine.exploitation_ratio,
            "min_exploration_budget": engine.min_exploration_budget
        }
    }


@router.get("/allocation-demo")
async def get_allocation_demo(total_cycles: int = 100):
    """Get example allocation for a given number of cycles."""
    engine = get_adaptive_learning_engine()

    # Ensure we have allocations
    if not engine.resource_allocations:
        await engine.analyze_and_learn()

    allocation = engine.get_allocation_for_cycle(total_cycles)

    return {
        "total_cycles": total_cycles,
        "allocation": allocation,
        "summary": {
            "exploitation": sum(a['count'] for a in allocation if 'exploitation' in a['reason']),
            "exploration": sum(a['count'] for a in allocation if 'exploration' in a['reason']),
            "areas_covered": len(allocation)
        }
    }
