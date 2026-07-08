#!/usr/bin/env python3
"""
SLATE Main Server - World-Class Version

Complete rewrite replacing broken swarm system with world-class
quantitative trading framework.

Built on principles from successful crypto trading firms:
- Market regime awareness and adaptation
- Proper risk management and position sizing
- Multiple strategy classes with proven edge
- Realistic signal generation and execution
- Robust validation and backtesting

Usage:
    python3 -m slate_core.server_clean

The server will:
1. Start on port 8788
2. Initialize world-class discovery system
3. Provide API endpoints for interaction
4. Run continuous world-class strategy discovery
5. Serve a web dashboard for monitoring
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# Add slate_core to path if needed
slate_root = Path(__file__).parent.parent
if str(slate_root) not in sys.path:
    sys.path.insert(0, str(slate_root))

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# World-Class Discovery Integration
try:
    from slate_core.world_class_server_integration import (
        start_world_class_discovery_on_startup,
        get_world_class_discovery_status
    )
    WORLD_CLASS_AVAILABLE = True
except ImportError as e:
    WORLD_CLASS_AVAILABLE = False
    logger.warning(f"World-class discovery not available: {e}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="SLATE - World-Class Quantitative Trading System",
    description="AI-driven world-class crypto trading strategy discovery (Paper Trading Only)",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    logger.info(f"Static files mounted from: {static_dir}")
else:
    logger.warning(f"Static directory not found: {static_dir}")

# Global state
start_time = datetime.now()

# ============================================================================
# API Routes - Health & Status
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint showing world-class system status."""
    world_class_status = {}

    if WORLD_CLASS_AVAILABLE:
        try:
            world_class_status = get_world_class_discovery_status()
        except Exception as e:
            logger.error(f"Error getting world-class status: {e}")

    return {
        "status": "healthy",
        "mode": "paper_trading",
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": (datetime.now() - start_time).total_seconds(),
        "port": 8788,
        "world_class_discovery": world_class_status,
        "system_type": "world_class_quantitative_trading"
    }


@app.get("/api/world-class/status")
async def world_class_status():
    """Get detailed world-class discovery system status."""
    if not WORLD_CLASS_AVAILABLE:
        return {
            "status": "unavailable",
            "message": "World-class discovery system not available",
            "system_type": "paper_trading"
        }

    try:
        status = get_world_class_discovery_status()
        return {
            "status": "available",
            "discovery_status": status,
            "system_type": "world_class_quantitative_trading",
            "principles": [
                "Market regime awareness",
                "Proper risk management",
                "Multiple strategy classes",
                "Proven edge in crypto markets",
                "Robust validation standards"
            ]
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


@app.post("/api/world-class/discovery/start")
async def start_world_class_discovery():
    """Manually trigger a world-class discovery cycle."""
    if not WORLD_CLASS_AVAILABLE:
        raise HTTPException(status_code=503, detail="World-class discovery not available")

    try:
        from slate_core.discovery.world_class_discovery import get_world_class_discovery_engine

        engine = get_world_class_discovery_engine()
        result = engine.run_discovery_cycle()

        return {
            "status": "success",
            "discovery_result": result,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to start world-class discovery: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Startup Event - World-Class Discovery Only
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Server startup - ONLY world-class discovery, NO old swarm system."""
    logger.info("=" * 70)
    logger.info("🚀 SLATE SERVER STARTING - WORLD-CLASS EDITION")
    logger.info("=" * 70)
    logger.info(f"Port: 8788")
    logger.info(f"Mode: Paper Trading Only")
    logger.info(f"Dashboard: http://localhost:8788")
    logger.info(f"API Docs: http://localhost:8788/docs")
    logger.info("=" * 70)

    logger.info("🌟 WORLD-CLASS QUANTITATIVE TRADING SYSTEM:")
    logger.info("  • Market regime awareness and adaptation")
    logger.info("  • Proper risk management (stop losses, position sizing)")
    logger.info("  • Multiple strategy classes (trend, mean reversion, momentum)")
    logger.info("  • World-class validation standards (10+ trades, 45% win rate, 0.5+ Sharpe)")
    logger.info("  • NO BROKEN SWARM SYSTEM - COMPLETE REPLACEMENT")
    logger.info("=" * 70)

    # ONLY start world-class discovery - NO old system
    if WORLD_CLASS_AVAILABLE:
        try:
            world_class_result = await start_world_class_discovery_on_startup()

            if world_class_result.get('status') == 'success':
                logger.info("✅ WORLD-CLASS DISCOVERY SYSTEM STARTED")
                logger.info("   • Generating professional quantitative strategies")
                logger.info("   • Market regime-aware strategy selection")
                logger.info("   • Proper risk management on all trades")
                logger.info("   • Robust validation before saving any strategies")
            else:
                logger.error("❌ World-class discovery startup failed")
        except Exception as e:
            logger.error(f"Failed to start world-class discovery: {e}")
    else:
        logger.error("❌ WORLD-CLASS SYSTEM NOT AVAILABLE - CANNOT START")
        raise RuntimeError("World-class discovery system required - server cannot start")


@app.on_event("shutdown")
async def shutdown_event():
    """Server shutdown - Clean shutdown of world-class discovery."""
    logger.info("🛑 SLATE Server shutting down...")
    logger.info("World-class discovery system stopping...")

    # Note: World-class discovery will stop gracefully as the event loop ends


# ============================================================================
# Legacy API Routes (Disabled for world-class edition)
# ============================================================================

@app.get("/api/swarm/status")
async def swarm_status_disabled():
    """Swarm status endpoint - DISABLED in world-class edition."""
    return {
        "status": "disabled",
        "message": "Swarm system removed in world-class edition - replaced by world-class quantitative framework",
        "replacement": "world_class_discovery",
        "reason": "Swarm parameter tuning generated fundamentally broken strategies"
    }


@app.post("/api/swarm/start")
async def swarm_start_disabled():
    """Swarm start endpoint - DISABLED in world-class edition."""
    raise HTTPException(
        status_code=410,
        detail="SWARM SYSTEM REMOVED - Replaced by world-class quantitative framework"
    )


@app.post("/api/swarm/stop")
async def swarm_stop_disabled():
    """Swarm stop endpoint - DISABLED in world-class edition."""
    return {
        "status": "disabled",
        "message": "Swarm system removed - world-class system uses different approach"
    }


if __name__ == "__main__":
    # Start server
    uvicorn.run(app, host="127.0.0.1", port=8788, log_level="info")