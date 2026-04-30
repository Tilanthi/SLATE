#!/usr/bin/env python3
"""
SLATE Enhanced Discovery API Endpoints

API endpoints for the enhanced discovery system with all advanced modules.
"""

from fastapi import APIRouter, HTTPException, Response
from typing import List, Dict, Optional
import logging
from datetime import datetime

from .enhanced_discovery import (
    get_enhanced_discovery_system,
    EnhancedDiscoveryConfig,
    EnhancedDiscoverySystem
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/enhanced-discovery", tags=["enhanced-discovery"])


@router.post("/start")
async def start_enhanced_discovery(
    cycles: int = 50,
    enable_ensembles: bool = True,
    enable_walk_forward: bool = True,
    enable_regime_aware: bool = True,
    enable_portfolio_risk: bool = True,
    enable_feature_engineering: bool = True,
    enable_online_learning: bool = True,
    enable_multi_objective: bool = True,
    enable_advanced_backtest: bool = True
):
    """Start enhanced discovery with specified modules enabled."""
    config = EnhancedDiscoveryConfig(
        cycles=cycles,
        enable_ensembles=enable_ensembles,
        enable_walk_forward=enable_walk_forward,
        enable_regime_aware=enable_regime_aware,
        enable_portfolio_risk=enable_portfolio_risk,
        enable_feature_engineering=enable_feature_engineering,
        enable_online_learning=enable_online_learning,
        enable_multi_objective=enable_multi_objective,
        enable_advanced_backtest=enable_advanced_backtest
    )

    system = get_enhanced_discovery_system(config)

    # Start discovery in background
    import asyncio
    asyncio.create_task(system.discover_strategies(cycles))

    return {
        "status": "started",
        "config": {
            "cycles": cycles,
            "modules_enabled": {
                "ensembles": enable_ensembles,
                "walk_forward": enable_walk_forward,
                "regime_aware": enable_regime_aware,
                "portfolio_risk": enable_portfolio_risk,
                "feature_engineering": enable_feature_engineering,
                "online_learning": enable_online_learning,
                "multi_objective": enable_multi_objective,
                "advanced_backtest": enable_advanced_backtest
            }
        }
    }


@router.get("/status")
async def get_enhanced_discovery_status():
    """Get enhanced discovery system status."""
    system = get_enhanced_discovery_system()
    return await system.get_discovery_summary()


@router.get("/results/ensembles")
async def get_ensemble_strategies(limit: int = 20):
    """Get discovered ensemble strategies."""
    system = get_enhanced_discovery_system()
    stats = await system.get_discovery_summary()

    # Return ensemble information
    return {
        "ensembles_created": stats["statistics"].get("ensembles_created", 0),
        "max_ensemble_size": system.config.max_ensemble_size if system.config else 5,
        "min_diversity_score": system.config.min_diversity_score if system.config else 0.3
    }


@router.get("/results/pareto-frontier")
async def get_pareto_frontier():
    """Get Pareto-optimal strategies from multi-objective optimization."""
    system = get_enhanced_discovery_system()

    if not system.multi_objective:
        raise HTTPException(status_code=400, detail="Multi-objective optimization not enabled")

    # Get Pareto frontier summary (would be populated after discovery runs)
    return {
        "frontier_size": 0,
        "objective_ranges": {},
        "message": "Run discovery to populate Pareto frontier"
    }


@router.get("/regime/current")
async def get_current_regime():
    """Get current detected market regime."""
    system = get_enhanced_discovery_system()

    if not system.regime_detector:
        raise HTTPException(status_code=400, detail="Regime detection not enabled")

    # Detect current regime
    regime = await system._detect_regime()

    return {
        "regime": regime,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/regime/strategies")
async def get_strategies_for_regime(regime: str):
    """Get recommended strategies for a specific market regime."""
    system = get_enhanced_discovery_system()

    if not system.regime_selector:
        raise HTTPException(status_code=400, detail="Regime-aware selection not enabled")

    try:
        strategies = system.regime_selector.get_strategies_for_regime(regime)
        return {
            "regime": regime,
            "recommended_strategies": strategies
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid regime: {e}")


@router.get("/risk/portfolio")
async def get_portfolio_risk_status():
    """Get current portfolio risk status."""
    system = get_enhanced_discovery_system()

    if not system.risk_manager:
        raise HTTPException(status_code=400, detail="Portfolio risk management not enabled")

    # Get portfolio summary
    summary = system.risk_manager.get_portfolio_summary()
    risk_metrics = system.risk_manager.calculate_portfolio_risk(system.risk_manager.positions)

    return {
        "portfolio_summary": summary,
        "risk_metrics": {
            "portfolio_var_95": risk_metrics.portfolio_var_95,
            "max_correlation": risk_metrics.max_correlation,
            "concentration_risk": risk_metrics.concentration_risk,
            "leverage_ratio": risk_metrics.leverage_ratio
        },
        "risk_limits": {
            "max_portfolio_var": system.risk_manager.risk_limits.max_portfolio_var,
            "max_correlation": system.risk_manager.risk_limits.max_correlation_exposure,
            "max_concentration": system.risk_manager.risk_limits.max_concentration_ratio
        }
    }


@router.get("/features/technical")
async def get_technical_features(symbol: str = "BTCUSDT"):
    """Get current technical features for a symbol."""
    system = get_enhanced_discovery_system()

    if not system.feature_engineering:
        raise HTTPException(status_code=400, detail="Feature engineering not enabled")

    # Get data for feature calculation
    if system.base_system and system.base_system.historical_archive:
        data = await system.base_system.historical_archive.get_test_data(symbol, "1h")

        if data:
            features = system.feature_engineering.calculate_features(data)

            return {
                "symbol": symbol,
                "features": {
                    "roc_5": features.roc_5,
                    "roc_10": features.roc_10,
                    "roc_20": features.roc_20,
                    "rsi_14": features.rsi_14,
                    "atr_ratio": features.atr_ratio,
                    "volatility_regime": features.volatility_regime,
                    "volume_profile": features.volume_profile,
                    "trend_direction": features.trend_direction,
                    "trend_strength": features.trend_strength,
                    "dominant_cycle": features.dominant_cycle,
                    "cycle_phase": features.cycle_phase
                },
                "timestamp": datetime.now().isoformat()
            }

    raise HTTPException(status_code=404, detail=f"No data available for {symbol}")


@router.get("/learning/status")
async def get_online_learning_status():
    """Get online learning system status."""
    system = get_enhanced_discovery_system()

    if not system.online_optimizer:
        raise HTTPException(status_code=400, detail="Online learning not enabled")

    status = system.online_optimizer.get_learning_status()

    return {
        "learning_status": status,
        "statistics": {
            "total_adaptations": system.discovery_stats.get("parameter_adaptations", 0)
        }
    }


@router.post("/validate/walk-forward")
async def validate_strategy_walk_forward(strategy: Dict):
    """Validate a strategy using walk-forward analysis."""
    system = get_enhanced_discovery_system()

    if not system.walk_forward_validator:
        raise HTTPException(status_code=400, detail="Walk-forward validation not enabled")

    # Get historical data
    if system.base_system and system.base_system.historical_archive:
        data = await system.base_system.historical_archive.load_data(
            symbol=strategy.get("symbol", "BTCUSDT"),
            timeframe=strategy.get("timeframe", "1m")
        )

        if data and len(data) > 1000:
            result = await system.walk_forward_validator.validate_walk_forward(
                strategy, data
            )

            return {
                "strategy_id": strategy.get("id"),
                "is_valid": result.is_valid,
                "stability_score": result.stability_score,
                "avg_test_sharpe": result.avg_test_sharpe,
                "avg_test_return": result.avg_test_return,
                "validation_periods": result.validation_periods,
                "is_stable": result.is_stable
            }

    raise HTTPException(status_code=400, detail="Insufficient data for validation")


@router.get("/config")
async def get_enhanced_config():
    """Get current enhanced discovery configuration."""
    system = get_enhanced_discovery_system()

    return {
        "config": {
            "cycles": system.config.cycles,
            "workers": system.config.workers,
            "enable_ensembles": system.config.enable_ensembles,
            "enable_walk_forward": system.config.enable_walk_forward,
            "enable_regime_aware": system.config.enable_regime_aware,
            "enable_portfolio_risk": system.config.enable_portfolio_risk,
            "enable_feature_engineering": system.config.enable_feature_engineering,
            "enable_online_learning": system.config.enable_online_learning,
            "enable_multi_objective": system.config.enable_multi_objective,
            "enable_advanced_backtest": system.config.enable_advanced_backtest
        },
        "modules_status": {
            "ensembles": system.ensemble_generator is not None,
            "walk_forward": system.walk_forward_validator is not None,
            "regime_aware": system.regime_detector is not None,
            "portfolio_risk": system.risk_manager is not None,
            "feature_engineering": system.feature_engineering is not None,
            "online_learning": system.online_optimizer is not None,
            "multi_objective": system.multi_objective is not None,
            "advanced_backtest": system.advanced_backtester is not None
        }
    }


@router.get("/statistics")
async def get_enhanced_statistics():
    """Get enhanced discovery statistics."""
    system = get_enhanced_discovery_system()
    summary = await system.get_discovery_summary()

    return summary
