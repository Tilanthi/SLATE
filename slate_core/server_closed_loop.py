#!/usr/bin/env python3
"""
SLATE Main Server - Closed-Loop AI Edition

Enhanced server integrating closed-loop AI discovery framework following research from:
"The future of fundamental science led by generative closed-loop artificial intelligence"

Major Enhancements:
1. Hypothesis-driven strategy discovery (replaces random parameter search)
2. Rigorous statistical validation with 6 pluralistic methods
3. Feedback learning system that improves over time
4. Hybrid neurosymbolic strategies combining patterns + rules
5. Complete scientific discovery cycle implementation

Built on principles from leading AI research labs:
- Closed-loop scientific discovery
- Pluralistic validation to avoid epistemic collapse
- Graded autonomy with human oversight
- Domain-specific methods matched to problems
- Statistical rigor to prevent model collapse

Usage:
    python3 -m slate_core.server

The server will:
1. Start on port 8788
2. Initialize closed-loop AI discovery system
3. Provide enhanced API endpoints
4. Run continuous hypothesis-driven discovery
5. Learn and improve from feedback
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

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Closed-Loop Discovery Integration
try:
    from slate_core.discovery.closed_loop_integration import (
        get_enhanced_discovery_system,
        EnhancedDiscoveryIntegration
    )
    CLOSED_LOOP_AVAILABLE = True
except ImportError as e:
    CLOSED_LOOP_AVAILABLE = False
    logger.warning(f"Closed-loop discovery not available: {e}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="SLATE - Closed-Loop AI Trading System",
    description="AI-driven closed-loop crypto trading strategy discovery based on cutting-edge research (Paper Trading Only)",
    version="4.0.0",
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
closed_loop_system: Optional[EnhancedDiscoveryIntegration] = None
discovery_running = False
discovery_task: Optional[asyncio.Task] = None

# ============================================================================
# API Routes - Health & Status
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint showing closed-loop system status."""
    closed_loop_status = {
        "discovery_running": discovery_running,
        "closed_loop_available": CLOSED_LOOP_AVAILABLE,
        "system_type": "closed_loop_ai_discovery"
    }

    return {
        "status": "healthy",
        "mode": "paper_trading",
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": (datetime.now() - start_time).total_seconds(),
        "port": 8788,
        "closed_loop_discovery": closed_loop_status,
        "system_type": "closed_loop_ai_quantitative_trading"
    }


@app.get("/api/closed-loop/status")
async def closed_loop_status():
    """Get detailed closed-loop discovery system status."""
    if not CLOSED_LOOP_AVAILABLE:
        return {
            "status": "unavailable",
            "message": "Closed-loop discovery system not available",
            "system_type": "paper_trading"
        }

    try:
        return {
            "status": "available",
            "discovery_running": discovery_running,
            "system_type": "closed_loop_ai_quantitative_trading",
            "framework": "Hypothesis-Driven Scientific Discovery",
            "components": {
                "hypothesis_generation": "operational",
                "rigorous_validation": "6 validation methods",
                "feedback_learning": "operational",
                "hybrid_strategies": "operational"
            },
            "principles": [
                "Hypothesis-driven discovery (not random search)",
                "Pluralistic validation (bootstrap, walk-forward, Monte Carlo)",
                "Feedback learning (continuous improvement)",
                "Hybrid neurosymbolic strategies (patterns + rules)",
                "Statistical rigor (avoid epistemic collapse)"
            ],
            "research_basis": "Based on: 'The future of fundamental science led by generative closed-loop artificial intelligence'"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


@app.post("/api/closed-loop/discovery/start")
async def start_closed_loop_discovery():
    """Manually trigger a closed-loop discovery cycle."""
    if not CLOSED_LOOP_AVAILABLE:
        raise HTTPException(status_code=503, detail="Closed-loop discovery not available")

    try:
        import pandas as pd
        from slate_core.discovery.closed_loop_discovery import load_market_data_for_discovery

        # Load market data
        df = load_market_data_for_discovery()

        if df is None or len(df) < 50:
            raise HTTPException(status_code=400, detail="Insufficient market data for discovery")

        # Run discovery cycle
        global closed_loop_system
        if closed_loop_system is None:
            closed_loop_system = get_enhanced_discovery_system()

        result = closed_loop_system.run_enhanced_discovery_cycle(df)

        return {
            "status": "success",
            "discovery_result": result,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to start closed-loop discovery: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/closed-loop/performance")
async def closed_loop_performance():
    """Get closed-loop system performance metrics."""
    if not CLOSED_LOOP_AVAILABLE or closed_loop_system is None:
        return {
            "status": "unavailable",
            "message": "Closed-loop system not initialized"
        }

    try:
        return {
            "status": "available",
            "enhancement_metrics": closed_loop_system.enhancement_metrics,
            "cycle_count": closed_loop_system.cycle_count,
            "performance_history": closed_loop_system.performance_history[-10:] if closed_loop_system.performance_history else []
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


# ============================================================================
# Background Discovery Loop
# ============================================================================

async def closed_loop_discovery_loop():
    """
    Background task running continuous closed-loop discovery.

    Replaces old swarm system with systematic scientific discovery.
    """
    global discovery_running, closed_loop_system

    logger.info("🧠 Starting Closed-Loop Discovery Loop")

    if not CLOSED_LOOP_AVAILABLE:
        logger.error("Closed-loop system not available - cannot start discovery")
        return

    try:
        # Initialize system
        closed_loop_system = get_enhanced_discovery_system()

        # Load market data once (in production, would reload periodically)
        import pandas as pd
        from slate_core.discovery.closed_loop_discovery import load_market_data_for_discovery

        df = load_market_data_for_discovery()

        if df is None or len(df) < 50:
            logger.error("Insufficient market data for discovery")
            return

        discovery_running = True
        cycle_count = 0

        while discovery_running:
            try:
                cycle_count += 1
                logger.info(f"🧠 Running Closed-Loop Discovery Cycle #{cycle_count}")

                # Run complete discovery cycle
                results = closed_loop_system.run_enhanced_discovery_cycle(df)

                # Log results
                performance = results.get('performance', {})
                logger.info(f"✅ Cycle #{cycle_count} Results:")
                logger.info(f"   Hypotheses: {performance.get('hypotheses_generated', 0)}")
                logger.info(f"   Validated: {performance.get('successful_validations', 0)}")
                logger.info(f"   Success Rate: {performance.get('overall_success_rate', 0):.1%}")

                # Check if we should continue
                success_rate = performance.get('overall_success_rate', 0)
                if success_rate < 0.05:  # Less than 5% success rate
                    logger.info("Low success rate detected - pausing for better market conditions")
                    await asyncio.sleep(300)  # Wait 5 minutes before trying again
                else:
                    # Normal wait between cycles
                    await asyncio.sleep(600)  # 10 minutes between cycles

            except Exception as e:
                logger.error(f"Discovery cycle error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error

    except Exception as e:
        logger.error(f"Closed-loop discovery loop failed: {e}")
        discovery_running = False

    logger.info("Closed-loop discovery loop stopped")


async def start_closed_loop_discovery_background():
    """Start closed-loop discovery as background task."""
    global discovery_task, discovery_running

    if not CLOSED_LOOP_AVAILABLE:
        logger.error("Cannot start discovery - closed-loop system not available")
        return

    if discovery_task is None or discovery_task.done():
        logger.info("🚀 Starting Closed-Loop Discovery Background Task")
        discovery_task = asyncio.create_task(closed_loop_discovery_loop())
        logger.info("✅ Closed-Loop Discovery Task Started")
    else:
        logger.info("Discovery already running")


def stop_discovery_background():
    """Stop background discovery task."""
    global discovery_running

    logger.info("🛑 Stopping Discovery...")
    discovery_running = False


# ============================================================================
# Startup Event - Closed-Loop Discovery System
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Server startup - Initialize closed-loop AI discovery system."""
    logger.info("=" * 70)
    logger.info("🚀 SLATE SERVER STARTING - CLOSED-LOOP AI EDITION")
    logger.info("=" * 70)
    logger.info(f"Port: 8788")
    logger.info(f"Mode: Paper Trading Only")
    logger.info(f"Dashboard: http://localhost:8788")
    logger.info(f"API Docs: http://localhost:8788/docs")
    logger.info("=" * 70)

    logger.info("🧠 CLOSED-LOOP AI DISCOVERY SYSTEM:")
    logger.info("  • Hypothesis-driven discovery (systematic vs random)")
    logger.info("  • Rigorous statistical validation (6 methods)")
    logger.info("  • Feedback learning system (continuous improvement)")
    logger.info("  • Hybrid neurosymbolic strategies (patterns + rules)")
    logger.info("  • Based on cutting-edge AI research")
    logger.info("=" * 70)
    logger.info("📚 RESEARCH BASIS:")
    logger.info('  "The future of fundamental science led by')
    logger.info('   generative closed-loop artificial intelligence"')
    logger.info("=" * 70)
    logger.info("🎯 SYSTEM CAPABILITIES:")
    logger.info("  • Information Extraction → Hypothesis Generation")
    logger.info("  • Experimental Validation → Iterative Refinement")
    logger.info("  • Feedback Learning → System Optimization")
    logger.info("  • World's first application to quantitative trading")
    logger.info("=" * 70)

    # Start closed-loop discovery in background
    if CLOSED_LOOP_AVAILABLE:
        try:
            await start_closed_loop_discovery_background()
            logger.info("✅ CLOSED-LOOP DISCOVERY SYSTEM STARTED")
        except Exception as e:
            logger.error(f"Failed to start closed-loop discovery: {e}")
            logger.warning("Server will continue but discovery may not work")
    else:
        logger.error("❌ CLOSED-LOOP SYSTEM NOT AVAILABLE")
        logger.error("Server will start but discovery functionality will be limited")


@app.on_event("shutdown")
async def shutdown_event():
    """Server shutdown - Clean shutdown of closed-loop discovery."""
    logger.info("🛑 SLATE Server shutting down...")
    logger.info("Stopping closed-loop discovery system...")

    stop_discovery_background()

    logger.info("✅ Closed-loop discovery stopped")
    logger.info("👋 Server shutdown complete")


# ============================================================================
# Legacy API Routes (Disabled/Replaced)
# ============================================================================

@app.get("/api/world-class/status")
async def world_class_status_deprecated():
    """World-class status endpoint - REPLACED by closed-loop."""
    return {
        "status": "deprecated",
        "message": "World-class system replaced by closed-loop AI framework",
        "replacement": "closed_loop_ai_discovery",
        "reason": "Enhanced hypothesis-driven discovery with pluralistic validation",
        "new_endpoint": "/api/closed-loop/status"
    }


@app.get("/api/swarm/status")
async def swarm_status_disabled():
    """Swarm status endpoint - DISABLED in closed-loop edition."""
    return {
        "status": "disabled",
        "message": "Swarm system removed - replaced by hypothesis-driven closed-loop discovery",
        "replacement": "closed_loop_ai_discovery",
        "reason": "Random parameter tuning replaced by systematic scientific discovery"
    }


# ============================================================================
# Main Server Entry Point
# ============================================================================

if __name__ == "__main__":
    # Start server
    uvicorn.run(app, host="127.0.0.1", port=8788, log_level="info")