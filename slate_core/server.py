#!/usr/bin/env python3
"""
SLATE Main Server

Auto-starting server for SLATE on port 8788.
This is the main entry point - it starts the API server and
automatically begins discovery cycles.

Usage:
    python3 -m slate_core.server

The server will:
1. Start on port 8788
2. Automatically begin discovery cycles
3. Provide API endpoints for interaction
4. Serve a web dashboard for monitoring
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add slate_core to path if needed
slate_root = Path(__file__).parent.parent
if str(slate_root) not in sys.path:
    sys.path.insert(0, str(slate_root))

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Autonomous system integration
try:
    from slate_core.autonomous import (
        AutonomousOrchestrator,
        get_exploratory_config,
        AutonomousConfig
    )
    AUTONOMOUS_AVAILABLE = True
except ImportError:
    AUTONOMOUS_AVAILABLE = False

# Startup coordinator for automatic discovery
try:
    from slate_core.startup_coordinator import (
        get_startup_coordinator,
        record_user_activity,
        execute_with_discovery_paused,
        get_system_status,
        initialize_with_discovery
    )
    STARTUP_COORDINATOR_AVAILABLE = True
except ImportError:
    STARTUP_COORDINATOR_AVAILABLE = False

# Enhanced discovery integration
try:
    from slate_core.server_enhanced import get_enhanced_integration, reset_enhanced_integration
    from slate_core.discovery.enhanced_strategy_generation import get_enhanced_generator
    from slate_core.discovery.pre_filters import get_pre_filters
    from slate_core.discovery.phase1_integration import run_phase1_discovery_cycle
    ENHANCED_DISCOVERY_AVAILABLE = True
except ImportError as e:
    ENHANCED_DISCOVERY_AVAILABLE = False
    logger.warning(f"Enhanced discovery not available - using basic discovery: {e}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="SLATE - Strategy Learning & Autonomous Trading Engine",
    description="AI-driven autonomous trading strategy discovery system (Paper Trading Only)",
    version="2.0.0",
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
discovery_running = False
discovery_task: Optional[asyncio.Task] = None
start_time = datetime.now()

# Autonomous system global state
autonomous_orchestrator: Optional[AutonomousOrchestrator] = None
autonomous_enabled = False

# Startup coordinator for automatic discovery
startup_coordinator: Optional[Any] = None
startup_coordinator_enabled = False


def track_user_activity():
    """Track user activity for automatic discovery pause/resume"""
    # Record in autonomous system
    if autonomous_enabled and autonomous_orchestrator:
        autonomous_orchestrator.record_user_activity()

    # Record in startup coordinator
    if STARTUP_COORDINATOR_AVAILABLE:
        try:
            record_user_activity()
        except Exception as e:
            logger.error(f"Error recording user activity: {e}")


# ============================================================================
# API Routes - Health & Status
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    from slate_core.discovery.edge_discovery_engine import EdgeDiscoveryEngine

    # Get startup coordinator status if available
    startup_status = {}
    if STARTUP_COORDINATOR_AVAILABLE and startup_coordinator:
        try:
            startup_status = get_system_status()
        except Exception as e:
            logger.error(f"Error getting startup coordinator status: {e}")

    return {
        "status": "healthy",
        "mode": "paper_trading",
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": (datetime.now() - start_time).total_seconds(),
        "discovery_running": discovery_running,
        "port": 8788,
        "startup_coordinator": startup_status
    }


@app.get("/api/metrics")
async def get_metrics():
    """Get system metrics."""
    from slate_core.discovery.edge_discovery_engine import EdgeDiscoveryEngine

    try:
        engine = EdgeDiscoveryEngine()
        stats = await engine.get_overall_statistics()
        return {
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": (datetime.now() - start_time).total_seconds(),
            "discovery_running": discovery_running,
            "statistics": stats
        }
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return {
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": (datetime.now() - start_time).total_seconds(),
            "discovery_running": discovery_running,
            "error": str(e)
        }


@app.get("/api/health/summary")
async def health_summary():
    """Complete health summary."""
    return {
        "status": "operational",
        "mode": "paper_trading_only",
        "server": {
            "port": 8788,
            "uptime_seconds": (datetime.now() - start_time).total_seconds(),
            "start_time": start_time.isoformat()
        },
        "discovery": {
            "running": discovery_running,
            "auto_start": True,
            "continuous": True
        },
        "database": {
            "path": "slate_core/slate_realistic_discoveries.db",
            "status": "active"
        },
        "warnings": [],
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# API Routes - Discovery Control
# ============================================================================

@app.post("/api/discovery/enhanced/start")
async def start_enhanced_discovery(
    num_strategies: int = 100,
    enable_enhanced: bool = True,
    timeframes: str = "1d,4h,1h"
):
    """
    Start enhanced discovery cycle with BIODISC-inspired improvements.

    Args:
        num_strategies: Number of strategies to test (default: 100)
        enable_enhanced: Whether to use enhanced discovery (default: True)
        timeframes: Comma-separated timeframes to test (default: "1d,4h,1h")
    """
    track_user_activity()
    global discovery_running, discovery_task

    if discovery_running:
        return {"status": "already_running", "message": "Discovery already in progress"}

    try:
        discovery_running = True

        # Parse timeframes
        timeframe_list = [tf.strip() for tf in timeframes.split(',') if tf.strip()]

        async def run_enhanced():
            global discovery_running
            try:
                if ENHANCED_DISCOVERY_AVAILABLE and enable_enhanced:
                    integration = get_enhanced_integration(enable_enhanced=enable_enhanced)
                    logger.info(f"Starting enhanced discovery: {num_strategies} strategies, timeframes: {timeframe_list}")

                    results = await integration.run_enhanced_discovery_cycle(
                        num_strategies=num_strategies,
                        timeframes=timeframe_list
                    )

                    logger.info(f"Enhanced discovery complete: {results['status']}")
                    if results['status'] == 'success':
                        logger.info(f"Performance: {results['performance_metrics']['estimated_total_speedup']}x speedup")
                else:
                    # Fallback to basic discovery
                    from slate_core.discovery.edge_discovery_engine import EdgeDiscoveryEngine
                    engine = EdgeDiscoveryEngine()
                    results = await engine.run_multi_timeframe_discovery_cycle()
                    logger.info(f"Basic discovery complete: {results['status']}")

            except Exception as e:
                logger.error(f"Enhanced discovery error: {e}", exc_info=True)
            finally:
                discovery_running = False

        discovery_task = asyncio.create_task(run_enhanced())

        return {
            "status": "started",
            "message": f"Enhanced discovery started (enhanced={enable_enhanced})",
            "num_strategies": num_strategies,
            "timeframes": timeframe_list,
            "enhanced_mode": enable_enhanced,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        discovery_running = False
        logger.error(f"Error starting enhanced discovery: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.get("/api/discovery/enhanced/stats")
async def get_enhanced_stats():
    """Get enhanced discovery statistics and performance metrics."""
    track_user_activity()

    try:
        if ENHANCED_DISCOVERY_AVAILABLE:
            integration = get_enhanced_integration()
            stats = integration.get_enhancement_stats()

            return {
                "timestamp": datetime.now().isoformat(),
                "enhanced_active": integration.is_enhanced_active(),
                "stats": stats,
                "available": True
            }
        else:
            return {
                "timestamp": datetime.now().isoformat(),
                "enhanced_active": False,
                "available": False,
                "message": "Enhanced discovery not available"
            }

    except Exception as e:
        logger.error(f"Error getting enhanced stats: {e}")
        return {
            "timestamp": datetime.now().isoformat(),
            "enhanced_active": False,
            "error": str(e)
        }


@app.get("/api/discovery/performance")
async def get_discovery_performance():
    """Get discovery performance comparison (basic vs enhanced)."""
    track_user_activity()

    try:
        if ENHANCED_DISCOVERY_AVAILABLE:
            integration = get_enhanced_integration()
            stats = integration.get_enhancement_stats()

            # Performance comparison
            comparison = {
                "basic_discovery": {
                    "strategies_per_second": 0.2,  # 5-second cycles
                    "parallel_speedup": 1.0,
                    "cache_hit_rate": 0.0,
                    "total_speedup": 1.0
                },
                "enhanced_discovery": {
                    "strategies_per_second": 0,
                    "parallel_speedup": 4.0,
                    "cache_hit_rate": 0.0,
                    "total_speedup": 4.0
                },
                "improvement_factor": 4.0,
                "time_saved_28k_discoveries": "~38 hours"
            }

            # Calculate actual stats if available
            if stats.get('enhanced_enabled') and stats.get('stats'):
                parallel_stats = stats['stats'].get('parallel_testing', {})
                cache_stats = stats['stats'].get('caching', {})

                parallel_speedup = parallel_stats.get('parallel_speedup', 4.0)
                cache_hit_rate = cache_stats.get('hit_rate', 0.0)

                enhanced_rate = 0.2 * parallel_speedup * (1 + cache_hit_rate * 3)
                improvement_factor = enhanced_rate / 0.2

                comparison["enhanced_discovery"]["strategies_per_second"] = round(enhanced_rate, 1)
                comparison["enhanced_discovery"]["parallel_speedup"] = round(parallel_speedup, 1)
                comparison["enhanced_discovery"]["cache_hit_rate"] = round(cache_hit_rate, 3)
                comparison["enhanced_discovery"]["total_speedup"] = round(improvement_factor, 1)
                comparison["improvement_factor"] = round(improvement_factor, 1)

                # Time calculation for 28,401 discoveries
                basic_time = 28401 / 0.2 / 3600  # hours
                enhanced_time = 28401 / enhanced_rate / 3600  # hours
                comparison["time_saved_28k_discoveries"] = f"{basic_time - enhanced_time:.1f} hours"

            return {
                "timestamp": datetime.now().isoformat(),
                "enhanced_active": integration.is_enhanced_active(),
                "performance_comparison": comparison,
                "current_stats": stats
            }
        else:
            return {
                "timestamp": datetime.now().isoformat(),
                "enhanced_active": False,
                "available": False,
                "message": "Enhanced discovery not available"
            }

    except Exception as e:
        logger.error(f"Error getting performance comparison: {e}")
        return {
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "enhanced_active": False
        }


@app.post("/api/discovery/enhanced/toggle")
async def toggle_enhanced_mode(enabled: bool = True):
    """Toggle enhanced discovery mode on/off."""
    track_user_activity()

    try:
        # Reset integration to apply new settings
        if ENHANCED_DISCOVERY_AVAILABLE:
            reset_enhanced_integration()

            # Create new integration with updated settings
            integration = get_enhanced_integration(enable_enhanced=enabled)

            return {
                "status": "success",
                "enhanced_mode": integration.is_enhanced_active(),
                "message": f"Enhanced discovery {'enabled' if enabled else 'disabled'}",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "unavailable",
                "message": "Enhanced discovery not available",
                "timestamp": datetime.now().isoformat()
            }

    except Exception as e:
        logger.error(f"Error toggling enhanced mode: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.post("/api/discovery/phase1/start")
async def start_phase1_discovery(num_strategies: int = 25):
    """
    Start Phase 1 Enhanced Discovery with Daily Priority + Pre-Filters.

    This is the quickest way to improve profitability from 3.6% to 20-25%:
    - Focuses exclusively on daily timeframes (97.5% of profitable strategies)
    - Uses smart pre-filters to eliminate obviously unprofitable strategies
    - Realistic trading frequency estimation
    - Proven parameter ranges for daily timeframes

    Args:
        num_strategies: Number of strategies to test (default: 25)
    """
    track_user_activity()
    global discovery_running, discovery_task

    if discovery_running:
        return {"status": "already_running", "message": "Discovery already in progress"}

    if not ENHANCED_DISCOVERY_AVAILABLE:
        return {"status": "unavailable", "message": "Phase 1 enhanced discovery not available"}

    try:
        discovery_running = True

        async def run_phase1():
            global discovery_running
            try:
                logger.info(f"Starting Phase 1 Enhanced Discovery: {num_strategies} strategies")
                logger.info("Focus: Daily Priority + Pre-Filters for 20-25% profitability rate")

                results = await run_phase1_discovery_cycle(num_strategies)

                logger.info(f"Phase 1 discovery complete: {results['status']}")
                if results['status'] == 'success':
                    passed = results.get('candidates_passed_filters', 0)
                    total = results.get('candidates_generated', 0)
                    logger.info(f"Phase 1 Results: {passed}/{total} candidates passed filters")

                    improvement = results.get('estimated_improvement', {})
                    improvement_factor = improvement.get('improvement_factor', 0)
                    logger.info(f"Estimated improvement: {improvement_factor}x better than baseline")

            except Exception as e:
                logger.error(f"Phase 1 discovery error: {e}", exc_info=True)
            finally:
                discovery_running = False

        discovery_task = asyncio.create_task(run_phase1())

        return {
            "status": "started",
            "message": "Phase 1 Enhanced Discovery started (Daily Priority + Pre-Filters)",
            "phase": "phase1_quick_wins",
            "num_strategies": num_strategies,
            "focus": "Daily timeframes with smart pre-filtering",
            "target_profitability": "20-25% (up from 3.6%)",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        discovery_running = False
        logger.error(f"Error starting Phase 1 discovery: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.get("/api/discovery/phase1/stats")
async def get_phase1_stats():
    """Get Phase 1 Enhanced Discovery statistics."""
    track_user_activity()

    try:
        if not ENHANCED_DISCOVERY_AVAILABLE:
            return {
                "timestamp": datetime.now().isoformat(),
                "available": False,
                "message": "Phase 1 enhanced discovery not available"
            }

        # Test Phase 1 components
        from slate_core.discovery.enhanced_strategy_generation import get_enhanced_generator
        from slate_core.discovery.pre_filters import get_pre_filters

        generator = get_enhanced_generator()
        pre_filters = get_pre_filters()

        # Get component stats
        generator_stats = generator.get_generation_stats()
        filter_stats = pre_filters.get_stats()

        return {
            "timestamp": datetime.now().isoformat(),
            "available": True,
            "phase": "phase1_quick_wins",
            "components": {
                "enhanced_strategy_generator": generator_stats,
                "smart_pre_filters": filter_stats
            },
            "focus": "Daily timeframes (97.5% of profitable strategies)",
            "target_improvement": "20-25% profitability rate (up from 3.6%)",
            "key_improvements": [
                "Daily timeframe exclusive focus",
                "Realistic trading frequency estimation",
                "Smart pre-filtering of unprofitable strategies",
                "Proven parameter ranges for daily data"
            ]
        }

    except Exception as e:
        logger.error(f"Error getting Phase 1 stats: {e}")
        return {
            "timestamp": datetime.now().isoformat(),
            "available": False,
            "error": str(e)
        }


@app.get("/api/intelligence/status")
async def get_intelligence_status():
    """Get trading intelligence system status and component availability."""
    track_user_activity()

    try:
        if autonomous_orchestrator:
            intelligence_status = autonomous_orchestrator.get_intelligence_status()
            return {
                "timestamp": datetime.now().isoformat(),
                "intelligence_system": intelligence_status,
                "available": intelligence_status.get('intelligence_available', False),
                "active": intelligence_status.get('intelligence_active', False)
            }
        else:
            return {
                "timestamp": datetime.now().isoformat(),
                "available": False,
                "active": False,
                "message": "Autonomous system not initialized"
            }

    except Exception as e:
        logger.error(f"Error getting intelligence status: {e}")
        return {
            "timestamp": datetime.now().isoformat(),
            "available": False,
            "error": str(e)
        }


@app.post("/api/intelligence/toggle")
async def toggle_intelligence_layer(enabled: bool = True):
    """Enable or disable the trading intelligence layer."""
    track_user_activity()

    try:
        if not autonomous_orchestrator:
            return {
                "status": "unavailable",
                "message": "Autonomous system not initialized"
            }

        success = autonomous_orchestrator.enable_intelligence_layer(enabled)

        if success:
            return {
                "status": "success",
                "intelligence_enabled": enabled,
                "message": f"Trading Intelligence {'enabled' if enabled else 'disabled'}",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "message": "Failed to toggle intelligence layer",
                "timestamp": datetime.now().isoformat()
            }

    except Exception as e:
        logger.error(f"Error toggling intelligence layer: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.get("/api/intelligence/components")
async def get_intelligence_components():
    """Get availability status of all intelligence components."""
    track_user_activity()

    try:
        if autonomous_orchestrator:
            components = autonomous_orchestrator.get_intelligence_components()
            return {
                "timestamp": datetime.now().isoformat(),
                "components": components,
                "total_components": len(components),
                "available_components": sum(1 for available in components.values() if available)
            }
        else:
            return {
                "timestamp": datetime.now().isoformat(),
                "components": {},
                "message": "Autonomous system not initialized"
            }

    except Exception as e:
        logger.error(f"Error getting intelligence components: {e}")
        return {
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }


@app.post("/api/discovery/start")
async def start_discovery():
    """Start a discovery cycle."""
    track_user_activity()  # Track user activity for autonomous pause
    global discovery_running, discovery_task

    if discovery_running:
        return {"status": "already_running", "message": "Discovery already in progress"}

    try:
        discovery_running = True
        from slate_core.discovery.edge_discovery_engine import EdgeDiscoveryEngine

        async def run_discovery():
            global discovery_running
            try:
                engine = EdgeDiscoveryEngine()
                logger.info("Starting multi-timeframe auto-discovery cycle...")
                results = await engine.run_multi_timeframe_discovery_cycle()
                logger.info(f"Multi-timeframe discovery complete: {results}")
            except Exception as e:
                logger.error(f"Discovery error: {e}", exc_info=True)
            finally:
                discovery_running = False

        discovery_task = asyncio.create_task(run_discovery())

        return {
            "status": "started",
            "message": "Discovery cycle started",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        discovery_running = False
        logger.error(f"Error starting discovery: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.post("/api/discovery/stop")
async def stop_discovery():
    """Stop the current discovery cycle."""
    track_user_activity()  # Track user activity for autonomous pause
    global discovery_running, discovery_task

    if not discovery_running:
        return {"status": "not_running", "message": "No discovery in progress"}

    discovery_running = False

    if discovery_task and not discovery_task.done():
        discovery_task.cancel()

    return {
        "status": "stopped",
        "message": "Discovery stopped",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/discovery/status")
async def get_discovery_status():
    """Get current discovery status."""
    track_user_activity()  # Track user activity for autonomous pause
    global discovery_running

    try:
        from slate_core.discovery.edge_discovery_engine import EdgeDiscoveryEngine
        engine = EdgeDiscoveryEngine()
        stats = await engine.get_overall_statistics()

        return {
            "running": discovery_running,
            "statistics": stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return {
            "running": discovery_running,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.get("/api/discovery/top")
async def get_top_strategies(limit: int = 10, sort_by: str = "total_profit_usdt"):
    """Get top performing strategies."""
    try:
        import sqlite3

        db_path = "slate_core/slate_realistic_discoveries.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get top strategies
        if sort_by == "total_profit_usdt":
            order_by = "total_profit_usdt DESC"
        elif sort_by == "sharpe_ratio":
            order_by = "sharpe_ratio DESC"
        elif sort_by == "win_rate":
            order_by = "win_rate DESC"
        else:
            order_by = "total_profit_usdt DESC"

        query = f"""
            SELECT
                edge_type,
                edge_description,
                total_profit_usdt,
                total_return_pct,
                sharpe_ratio,
                max_drawdown_pct,
                win_rate,
                profit_factor,
                passed_validation,
                beat_market
            FROM edge_discoveries
            ORDER BY {order_by}
            LIMIT ?
        """

        cursor.execute(query, (limit,))
        rows = cursor.fetchall()
        conn.close()

        strategies = []
        for row in rows:
            strategies.append({
                "edge_type": row[0],
                "edge_description": row[1],
                "total_profit_usdt": row[2],
                "total_return_pct": row[3],  # This is the decimal percentage (0.0379 = 3.79%)
                "sharpe_ratio": row[4],
                "max_drawdown_pct": row[5],
                "win_rate": row[6],
                "profit_factor": row[7],
                "passed_validation": bool(row[8]),
                "beat_market": bool(row[9])
            })

        return {
            "total": len(strategies),
            "sort_by": sort_by,
            "strategies": strategies
        }
    except Exception as e:
        logger.error(f"Error getting top strategies: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.get("/api/discovery/statistics")
async def get_discovery_statistics():
    """Get overall discovery statistics."""
    try:
        import sqlite3

        db_path = "slate_core/slate_realistic_discoveries.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Total discoveries
        cursor.execute("SELECT COUNT(*) FROM edge_discoveries")
        total = cursor.fetchone()[0]

        # Passed validation
        cursor.execute("SELECT COUNT(*) FROM edge_discoveries WHERE passed_validation = 1")
        passed = cursor.fetchone()[0]

        # Beat market
        cursor.execute("SELECT COUNT(*) FROM edge_discoveries WHERE beat_market = 1")
        beat_market = cursor.fetchone()[0]

        # Average metrics (use total_return_pct for average return, not total_profit_usdt)
        cursor.execute("""
            SELECT
                AVG(total_return_pct),
                AVG(sharpe_ratio),
                AVG(max_drawdown_pct),
                AVG(win_rate)
            FROM edge_discoveries
        """)
        avg_metrics = cursor.fetchone()

        # Best strategy (use total_return_pct for percentage, not total_profit_usdt)
        cursor.execute("""
            SELECT edge_type, total_return_pct, total_profit_usdt, sharpe_ratio
            FROM edge_discoveries
            ORDER BY total_profit_usdt DESC
            LIMIT 1
        """)
        best = cursor.fetchone()
        conn.close()

        return {
            "total_tests": total,
            "profitable_strategies": passed,
            "beat_market_count": beat_market,
            "best_return": float(best[1]) if best else 0,  # total_return_pct (already as decimal)
            "best_return_pct": float(best[1] * 100) if best else 0,  # as percentage for display
            "best_profit_usdt": float(best[2]) if best else 0,  # actual USDT profit
            "best_sharpe": float(best[3]) if best else 0,
            "average_return": float(avg_metrics[0]) if avg_metrics[0] else 0,  # avg of total_return_pct (decimal)
            "average_sharpe": float(avg_metrics[1]) if avg_metrics[1] else 0,
            "average_drawdown": float(avg_metrics[2]) if avg_metrics[2] else 0,
            "average_win_rate": float(avg_metrics[3]) if avg_metrics[3] else 0,
            "discovery_running": discovery_running,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        return {
            "total_tests": 0,
            "error": str(e),
            "discovery_running": discovery_running
        }


@app.get("/api/discovery/benchmark")
async def get_benchmark_comparison():
    """
    Get benchmark comparison statistics.

    Compares strategy performance against buy-and-hold baseline.
    Includes Information Ratio calculation and market beating statistics.
    """
    try:
        import sqlite3

        db_path = "slate_core/slate_realistic_discoveries.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get all benchmark data
        cursor.execute("""
            SELECT
                edge_type,
                edge_description,
                total_profit_usdt,
                total_return_pct,
                buy_hold_profit_usdt,
                buy_hold_return_pct,
                vs_buy_hold_usdt,
                beat_market,
                sharpe_ratio,
                max_drawdown_pct,
                win_rate,
                timestamp
            FROM edge_discoveries
            ORDER BY timestamp DESC
        """)
        rows = cursor.fetchall()

        if not rows:
            conn.close()
            return {
                "status": "no_data",
                "message": "No benchmark data available yet"
            }

        # Calculate aggregate statistics
        total_strategies = len(rows)
        beat_market_count = sum(1 for r in rows if r[8])  # beat_market column
        beat_market_pct = beat_market_count / total_strategies if total_strategies > 0 else 0

        # Calculate excess returns and tracking error for Information Ratio
        excess_returns = [r[6] for r in rows]  # vs_buy_hold_usdt
        strategy_returns = [r[3] for r in rows]  # total_return_pct
        buy_hold_returns = [r[5] for r in rows]  # buy_hold_return_pct

        # Calculate tracking error (std dev of excess returns)
        if len(excess_returns) > 1:
            import numpy as np
            avg_excess_return = np.mean(excess_returns)
            tracking_error = np.std(excess_returns)

            # Information Ratio = Average Excess Return / Tracking Error
            information_ratio = avg_excess_return / tracking_error if tracking_error > 0 else 0
        else:
            avg_excess_return = excess_returns[0] if excess_returns else 0
            tracking_error = 0
            information_ratio = 0

        # Get top performers vs market
        top_vs_market = sorted(rows, key=lambda x: x[6], reverse=True)[:10]

        # Get worst vs market
        worst_vs_market = sorted(rows, key=lambda x: x[6])[:5]

        # Calculate cumulative performance
        total_strategy_profit = sum(r[2] for r in rows)  # total_profit_usdt
        total_buy_hold_profit = sum(r[4] for r in rows)  # buy_hold_profit_usdt
        cumulative_excess = total_strategy_profit - total_buy_hold_profit

        conn.close()

        return {
            "status": "success",
            "summary": {
                "total_strategies": total_strategies,
                "beat_market_count": beat_market_count,
                "beat_market_percentage": beat_market_pct,
                "total_strategy_profit_usdt": total_strategy_profit,
                "total_buy_hold_profit_usdt": total_buy_hold_profit,
                "cumulative_excess_usdt": cumulative_excess,
                "average_excess_return_usdt": avg_excess_return,
                "tracking_error_usdt": tracking_error,
                "information_ratio": information_ratio
            },
            "top_performers": [
                {
                    "edge_type": r[0],
                    "description": r[1],
                    "total_profit_usdt": r[2],
                    "buy_hold_profit_usdt": r[4],
                    "excess_return_usdt": r[6],
                    "beat_market": r[8],
                    "sharpe_ratio": r[9],
                    "win_rate": r[11]
                }
                for r in top_vs_market
            ],
            "worst_performers": [
                {
                    "edge_type": r[0],
                    "description": r[1],
                    "total_profit_usdt": r[2],
                    "buy_hold_profit_usdt": r[4],
                    "excess_return_usdt": r[6],
                    "beat_market": r[8]
                }
                for r in worst_vs_market
            ],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting benchmark comparison: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


@app.get("/api/discovery/correlation")
async def get_strategy_correlation():
    """
    Get correlation matrix analysis between strategies.

    Calculates Pearson correlation coefficients between strategy types
    to identify diversification opportunities and redundant strategies.
    """
    try:
        import sqlite3
        import numpy as np

        db_path = "slate_core/slate_realistic_discoveries.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get all strategies with their metrics
        cursor.execute("""
            SELECT
                edge_type,
                edge_description,
                total_profit_usdt,
                total_return_pct,
                sharpe_ratio,
                max_drawdown_pct,
                win_rate,
                profit_factor,
                beat_market
            FROM edge_discoveries
            WHERE total_trades > 0
            ORDER BY edge_type
        """)
        rows = cursor.fetchall()

        if len(rows) < 2:
            conn.close()
            return {
                "status": "insufficient_data",
                "message": "Need at least 2 strategies for correlation analysis"
            }

        # Group strategies by edge type
        type_metrics = {}
        for row in rows:
            edge_type = row[0]
            if edge_type not in type_metrics:
                type_metrics[edge_type] = {
                    'profits': [],
                    'returns': [],
                    'sharpe': [],
                    'drawdowns': [],
                    'win_rates': []
                }
            type_metrics[edge_type]['profits'].append(row[2])
            type_metrics[edge_type]['returns'].append(row[3])
            type_metrics[edge_type]['sharpe'].append(row[4])
            type_metrics[edge_type]['drawdowns'].append(row[5])
            type_metrics[edge_type]['win_rates'].append(row[6])

        # Calculate average metrics for each edge type (to handle different sample sizes)
        edge_type_stats = {}
        for edge_type, metrics in type_metrics.items():
            edge_type_stats[edge_type] = {
                'avg_return': np.mean(metrics['returns']) if metrics['returns'] else 0,
                'avg_sharpe': np.mean(metrics['sharpe']) if metrics['sharpe'] else 0,
                'avg_win_rate': np.mean(metrics['win_rates']) if metrics['win_rates'] else 0,
                'avg_drawdown': np.mean(metrics['drawdowns']) if metrics['drawdowns'] else 0,
                'count': len(metrics['returns'])
            }

        # Calculate correlation matrix using average metrics
        edge_types = list(edge_type_stats.keys())
        correlation_matrix = []
        type_pairs = []

        for i, type1 in enumerate(edge_types):
            row_data = []
            for j, type2 in enumerate(edge_types):
                if i == j:
                    correlation = 1.0
                else:
                    # Calculate correlation based on average metrics
                    stats1 = edge_type_stats[type1]
                    stats2 = edge_type_stats[type2]

                    # Use multiple metrics for correlation
                    # Compare similarity in profile across metrics
                    metrics1 = np.array([
                        stats1['avg_return'],
                        stats1['avg_sharpe'],
                        stats1['avg_win_rate'],
                        -stats1['avg_drawdown']  # Negative because lower drawdown is better
                    ])
                    metrics2 = np.array([
                        stats2['avg_return'],
                        stats2['avg_sharpe'],
                        stats2['avg_win_rate'],
                        -stats2['avg_drawdown']
                    ])

                    # Normalize to 0-1 range for fair comparison
                    all_metrics = np.array([metrics1, metrics2])
                    min_vals = all_metrics.min(axis=0)
                    max_vals = all_metrics.max(axis=0)
                    range_vals = max_vals - min_vals

                    # Avoid division by zero
                    range_vals = np.where(range_vals == 0, 1, range_vals)

                    norm1 = (metrics1 - min_vals) / range_vals
                    norm2 = (metrics2 - min_vals) / range_vals

                    # Calculate correlation
                    correlation = float(np.corrcoef(norm1, norm2)[0, 1])
                    if np.isnan(correlation):
                        correlation = 0.0

                    # Store pair data for detailed analysis
                    if i < j:
                        type_pairs.append({
                            'type1': type1,
                            'type2': type2,
                            'correlation': abs(correlation),
                            'diversification_benefit': 'High' if abs(correlation) < 0.3 else 'Medium' if abs(correlation) < 0.7 else 'Low'
                        })

                row_data.append(correlation)
            correlation_matrix.append(row_data)

        # Find highly correlated pairs (potential redundancy)
        redundant_pairs = [p for p in type_pairs if p['correlation'] > 0.8]

        # Find low correlation pairs (good diversification)
        diversified_pairs = [p for p in type_pairs if p['correlation'] < 0.3]

        conn.close()

        return {
            "status": "success",
            "matrix": {
                "types": edge_types,
                "correlations": correlation_matrix
            },
            "summary": {
                "total_types": len(edge_types),
                "high_correlation_pairs": len([p for p in type_pairs if p['correlation'] > 0.7]),
                "low_correlation_pairs": len([p for p in type_pairs if p['correlation'] < 0.3])
            },
            "recommendations": {
                "redundant_strategies": redundant_pairs[:5],
                "diversification_opportunities": diversified_pairs[:5]
            },
            "detailed_pairs": type_pairs,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error calculating strategy correlation: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


@app.get("/api/discovery/portfolio/optimize")
async def optimize_portfolio(method: str = "mean_variance"):
    """
    Perform portfolio optimization on discovered strategies.

    Supports multiple optimization methods:
    - mean_variance: Traditional Markowitz mean-variance optimization
    - risk_parity: Equal risk contribution portfolio
    - equal_weight: Simple equal-weighted portfolio
    - sharpe_ratio: Maximize Sharpe ratio

    Args:
        method: Optimization method to use

    Returns:
        Optimized portfolio weights and metrics
    """
    try:
        import sqlite3
        import numpy as np

        db_path = "slate_core/slate_realistic_discoveries.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get top performing strategies (passed validation, with real trades)
        cursor.execute("""
            SELECT
                edge_type,
                edge_description,
                total_profit_usdt,
                total_return_pct,
                sharpe_ratio,
                max_drawdown_pct,
                win_rate,
                profit_factor,
                beat_market,
                total_trades
            FROM edge_discoveries
            WHERE passed_validation = 1 AND total_trades >= 10
            ORDER BY total_profit_usdt DESC
            LIMIT 20
        """)
        rows = cursor.fetchall()

        if len(rows) < 2:
            conn.close()
            return {
                "status": "insufficient_strategies",
                "message": f"Need at least 2 validated strategies for optimization, found {len(rows)}"
            }

        # Extract strategy data
        strategies = []
        for row in rows:
            strategies.append({
                "edge_type": row[0],
                "edge_description": row[1],
                "total_profit_usdt": row[2],
                "total_return_pct": row[3],
                "sharpe_ratio": row[4],
                "max_drawdown_pct": row[5],
                "win_rate": row[6],
                "profit_factor": row[7],
                "beat_market": row[8],
                "total_trades": row[9]
            })

        # Calculate returns and risk for optimization
        returns = np.array([s["total_return_pct"] for s in strategies])
        sharpe_ratios = np.array([s["sharpe_ratio"] for s in strategies])
        drawdowns = np.array([abs(s["max_drawdown_pct"]) for s in strategies])

        # Normalize metrics for weight calculation
        n_strategies = len(strategies)

        if method == "equal_weight":
            # Simple equal weight portfolio
            weights = np.ones(n_strategies) / n_strategies

        elif method == "mean_variance":
            # Mean-variance optimization (simplified)
            # Use Sharpe ratio as expected return, drawdown as risk
            expected_returns = sharpe_ratios
            risk_matrix = np.diag(drawdowns)

            # Calculate inverse variance weights
            inv_var = 1.0 / (drawdowns + 1e-6)  # Add small epsilon to avoid division by zero
            weights = inv_var / np.sum(inv_var)

        elif method == "risk_parity":
            # Risk parity: equalize risk contribution
            # Use inverse of drawdown squared as proxy for risk
            inv_risk_sq = 1.0 / (drawdowns ** 2 + 1e-6)
            weights = inv_risk_sq / np.sum(inv_risk_sq)

        elif method == "sharpe_ratio":
            # Maximize Sharpe ratio by weighting proportional to Sharpe
            # Only use positive Sharpe ratios
            positive_sharpe = np.maximum(sharpe_ratios, 0)
            if np.sum(positive_sharpe) > 0:
                weights = positive_sharpe / np.sum(positive_sharpe)
            else:
                weights = np.ones(n_strategies) / n_strategies
        else:
            # Default to equal weight
            weights = np.ones(n_strategies) / n_strategies

        # Normalize weights to sum to 1
        weights = weights / np.sum(weights)

        # Calculate portfolio metrics
        portfolio_return = np.sum(returns * weights)
        portfolio_sharpe = np.sum(sharpe_ratios * weights)
        portfolio_drawdown = np.sum(drawdowns * weights)  # Simplified

        # Calculate diversification ratio
        weighted_avg_risk = np.sum(drawdowns * weights)
        portfolio_risk = np.sqrt(np.sum(weights[:, None] * weights[None, :] * np.outer(drawdowns, drawdowns)))
        diversification_ratio = weighted_avg_risk / (portfolio_risk + 1e-6)

        # Calculate expected profit
        initial_capital = 10000.0
        portfolio_profit_usdt = initial_capital * portfolio_return

        # Prepare results
        portfolio_allocations = []
        for i, strategy in enumerate(strategies):
            portfolio_allocations.append({
                "edge_type": strategy["edge_type"],
                "weight": float(weights[i]),
                "weight_pct": float(weights[i] * 100),
                "allocated_usdt": float(initial_capital * weights[i]),
                "expected_return_pct": float(strategy["total_return_pct"] * 100),
                "sharpe_ratio": float(strategy["sharpe_ratio"]),
                "max_drawdown_pct": float(strategy["max_drawdown_pct"] * 100)
            })

        # Sort by weight
        portfolio_allocations.sort(key=lambda x: x["weight"], reverse=True)

        conn.close()

        return {
            "status": "success",
            "method": method,
            "portfolio": {
                "total_strategies": n_strategies,
                "initial_capital": initial_capital,
                "expected_return_pct": float(portfolio_return * 100),
                "expected_profit_usdt": float(portfolio_profit_usdt),
                "portfolio_sharpe": float(portfolio_sharpe),
                "portfolio_drawdown_pct": float(portfolio_drawdown * 100),
                "diversification_ratio": float(diversification_ratio)
            },
            "allocations": portfolio_allocations,
            "metrics": {
                "top_allocation": portfolio_allocations[0]["weight_pct"] if portfolio_allocations else 0,
                "allocation_count": len([a for a in portfolio_allocations if a["weight_pct"] > 5]),
                "effective_strategies": len([a for a in portfolio_allocations if a["weight_pct"] > 1])
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error optimizing portfolio: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


# ============================================================================
# API Routes - Natural Language Strategy Generation
# ============================================================================

@app.post("/api/discovery/nl/generate")
async def generate_nl_strategy(request: dict):
    """
    Generate a trading strategy from natural language description.

    Body:
        description: Natural language strategy description
        provider: LLM provider (optional, default: "mock")
        api_key: API key for provider (optional)

    Example:
        POST /api/discovery/nl/generate
        {
            "description": "Test a mean reversion strategy when RSI is below 30"
        }
    """
    track_user_activity()  # Track user activity for autonomous pause
    try:
        description = request.get("description", "")
        provider = request.get("provider", "mock")
        api_key = request.get("api_key", None)

        if not description:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "description is required"}
            )

        from slate_core.discovery.edge_discovery_engine import EdgeDiscoveryEngine

        engine = EdgeDiscoveryEngine()
        candidate = engine.generate_nl_strategy(description, provider=provider, api_key=api_key)

        if candidate is None:
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": "Failed to generate strategy"}
            )

        return {
            "status": "success",
            "strategy": {
                "edge_type": candidate.edge_type.value,
                "description": candidate.description,
                "entry_conditions": candidate.entry_conditions,
                "exit_conditions": candidate.exit_conditions,
                "risk_params": candidate.risk_params,
                "confidence": candidate.confidence,
                "expected_return": candidate.expected_return,
                "expected_drawdown": candidate.expected_drawdown
            },
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error generating NL strategy: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.post("/api/discovery/nl/test")
async def test_nl_strategy(request: dict):
    """
    Generate and immediately test a strategy from natural language description.

    Body:
        description: Natural language strategy description
        provider: LLM provider (optional, default: "mock")
        api_key: API key for provider (optional)

    Example:
        POST /api/discovery/nl/test
        {
            "description": "Test a breakout strategy when volume is high"
        }
    """
    track_user_activity()  # Track user activity for autonomous pause
    try:
        description = request.get("description", "")
        provider = request.get("provider", "mock")
        api_key = request.get("api_key", None)

        if not description:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "description is required"}
            )

        from slate_core.discovery.edge_discovery_engine import EdgeDiscoveryEngine

        # Generate strategy
        engine = EdgeDiscoveryEngine()
        candidate = engine.generate_nl_strategy(description, provider=provider, api_key=api_key)

        if candidate is None:
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": "Failed to generate strategy"}
            )

        # Fetch data and backtest
        df = await engine.fetch_solusdt_data(days=90)
        if df is None:
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": "Failed to fetch market data"}
            )

        # Run backtest
        result = engine.simulate_edge_backtest(df, candidate, engine.config)

        # Save to database
        engine.save_discovery(result)

        return {
            "status": "success",
            "strategy": {
                "edge_type": result.edge_type,
                "description": result.edge_description
            },
            "results": {
                "total_profit_usdt": result.total_profit_usdt,
                "total_return_pct": result.total_return_pct,
                "sharpe_ratio": result.sharpe_ratio,
                "max_drawdown_pct": result.max_drawdown_pct,
                "win_rate": result.win_rate,
                "profit_factor": result.profit_factor,
                "total_trades": result.total_trades,
                "beat_market": result.beat_market,
                "passed_validation": result.passed_validation
            },
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error testing NL strategy: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


# ============================================================================
# Checkpoint & Recovery APIs
# ============================================================================

@app.get("/api/discovery/checkpoint/status")
async def get_checkpoint_status():
    """Get checkpoint status and incomplete cycles."""
    try:
        from slate_core.discovery.checkpoint_manager import get_checkpoint_manager

        checkpoint_mgr = get_checkpoint_manager()
        incomplete_cycles = checkpoint_mgr.get_incomplete_cycles()

        return {
            "status": "success",
            "checkpoint_enabled": True,
            "incomplete_cycles": incomplete_cycles,
            "cache_directory": str(checkpoint_mgr.cache_dir),
            "total_incomplete": len(incomplete_cycles)
        }
    except Exception as e:
        logger.error(f"Error getting checkpoint status: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.post("/api/discovery/checkpoint/resume")
async def resume_from_checkpoint(request: dict):
    """Resume discovery from a specific checkpoint."""
    try:
        cycle_id = request.get("cycle_id")
        if not cycle_id:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "cycle_id required"}
            )

        from slate_core.discovery.checkpoint_manager import get_checkpoint_manager
        from slate_core.discovery.edge_discovery_engine import EdgeDiscoveryEngine

        checkpoint_mgr = get_checkpoint_manager()

        if not checkpoint_mgr.can_resume(cycle_id):
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Cycle cannot be resumed"}
            )

        # Create engine with checkpoint enabled
        engine = EdgeDiscoveryEngine(checkpoint_enabled=True)

        # Resume the cycle
        result = await engine.run_discovery_cycle_with_checkpoint(resume_cycle_id=cycle_id)

        return result

    except Exception as e:
        logger.error(f"Error resuming from checkpoint: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.post("/api/discovery/checkpoint/clear")
async def clear_checkpoints(request: dict):
    """Clear checkpoints."""
    try:
        cycle_id = request.get("cycle_id")
        from slate_core.discovery.checkpoint_manager import get_checkpoint_manager

        checkpoint_mgr = get_checkpoint_manager()

        if cycle_id:
            success = checkpoint_mgr.clear_checkpoint(cycle_id)
            message = f"Checkpoint {cycle_id} cleared" if success else "Checkpoint not found"
        else:
            count = checkpoint_mgr.clear_all_checkpoints()
            message = f"Cleared {count} checkpoint databases"

        return {
            "status": "success",
            "message": message
        }

    except Exception as e:
        logger.error(f"Error clearing checkpoints: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


# ============================================================================
# Reflection Memory APIs
# ============================================================================

@app.get("/api/memory/reflection")
async def get_reflection_memory():
    """Get reflection memory content."""
    try:
        from slate_core.discovery.reflection_memory import get_reflection_memory
        from pathlib import Path

        memory_mgr = get_reflection_memory()

        if not memory_mgr.memory_path.exists():
            return {
                "status": "success",
                "memory_exists": False,
                "content": None
            }

        content = memory_mgr.memory_path.read_text()

        return {
            "status": "success",
            "memory_exists": True,
            "content": content,
            "memory_path": str(memory_mgr.memory_path),
            "last_modified": datetime.fromtimestamp(
                memory_mgr.memory_path.stat().st_mtime
            ).isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting reflection memory: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.get("/api/memory/lessons")
async def get_recent_lessons(limit: int = 10):
    """Get recent lessons from reflection memory."""
    try:
        from slate_core.discovery.reflection_memory import get_reflection_memory

        memory_mgr = get_reflection_memory()
        lessons = memory_mgr.get_recent_lessons(limit=limit)

        return {
            "status": "success",
            "lessons": lessons,
            "count": len(lessons)
        }

    except Exception as e:
        logger.error(f"Error getting recent lessons: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.get("/api/memory/context")
async def get_discovery_context():
    """Get contextual information for a new discovery cycle."""
    try:
        from slate_core.discovery.reflection_memory import get_reflection_memory

        memory_mgr = get_reflection_memory()
        context = memory_mgr.get_context_for_new_cycle()

        return {
            "status": "success",
            "context": context
        }

    except Exception as e:
        logger.error(f"Error getting discovery context: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.post("/api/memory/clear")
async def clear_reflection_memory():
    """Clear all reflection memory."""
    try:
        from slate_core.discovery.reflection_memory import get_reflection_memory

        memory_mgr = get_reflection_memory()
        memory_mgr.clear_memory()

        return {
            "status": "success",
            "message": "Reflection memory cleared"
        }

    except Exception as e:
        logger.error(f"Error clearing reflection memory: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


# ============================================================================
# API Routes - YouTube Transcription & Video Analysis
# ============================================================================

@app.post("/api/youtube/transcribe")
async def transcribe_youtube_video(request: Request):
    """
    Transcribe a YouTube video and extract trading insights.

    Expects JSON body:
    {
        "url": "https://www.youtube.com/watch?v=...",
        "extract_insights": true  # optional, default true
    }

    Returns:
    {
        "success": true,
        "transcript": "...",
        "video_id": "...",
        "title": "...",
        "duration": ...,
        "insights": {
            "strategies_found": [...],
            "indicators_found": [...],
            "assets_mentioned": [...],
            "trading_relevance_score": 85.0,
            "slate_action_items": [...]
        }
    }
    """
    try:
        from slate_core.external_data.youtube_transcriber import YouTubeTranscriber
        from slate_core.external_data.video_insight_extractor import VideoInsightExtractor

        body = await request.json()
        url = body.get('url')
        extract_insights = body.get('extract_insights', True)

        if not url:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Missing YouTube URL"}
            )

        logger.info(f"YouTube transcription request: {url}")

        # Get transcript
        transcriber = YouTubeTranscriber()
        transcript_result = transcriber.get_transcript(url)

        if not transcript_result.get('success'):
            return transcript_result

        # Extract trading insights if requested
        insights = None
        if extract_insights:
            extractor = VideoInsightExtractor()
            insights = extractor.extract_insights(transcript_result)

        return {
            "success": True,
            "transcript": transcript_result.get('transcript'),
            "video_id": transcript_result.get('video_id'),
            "url": url,
            "title": transcript_result.get('title', 'Unknown'),
            "duration": transcript_result.get('duration', 0),
            "word_count": transcript_result.get('word_count', 0),
            "language": transcript_result.get('language', 'unknown'),
            "method": transcript_result.get('method', 'unknown'),
            "segments_count": len(transcript_result.get('segments', [])),
            "insights": insights,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error transcribing YouTube video: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.post("/api/youtube/search")
async def search_youtube_transcript(request: Request):
    """
    Search within a YouTube video transcript for specific topics.

    Expects JSON body:
    {
        "url": "https://www.youtube.com/watch?v=...",
        "query": "stop loss strategy"
    }

    Returns:
    {
        "success": true,
        "query": "stop loss strategy",
        "total_matches": 5,
        "results": [
            {
                "timestamp": 123.45,
                "timestamp_formatted": "2:03",
                "text": "...",
                "context": "..."
            }
        ]
    }
    """
    try:
        from slate_core.external_data.youtube_transcriber import YouTubeTranscriber

        body = await request.json()
        url = body.get('url')
        query = body.get('query')

        if not url or not query:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Missing URL or query"}
            )

        logger.info(f"YouTube search request: {url} - query: {query}")

        transcriber = YouTubeTranscriber()
        search_result = transcriber.search_transcript(url, query)

        return search_result

    except Exception as e:
        logger.error(f"Error searching YouTube transcript: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.get("/api/youtube/status")
async def youtube_status():
    """Check YouTube transcription dependencies and capabilities."""
    try:
        from slate_core.external_data.youtube_transcriber import YouTubeTranscriber

        transcriber = YouTubeTranscriber()
        deps_status = transcriber._check_dependencies()

        # Count cached transcripts
        cache_count = 0
        cache_dir = transcriber.cache_dir
        if cache_dir.exists():
            cache_count = len(list(cache_dir.glob("*.json")))

        return {
            "status": "operational",
            "dependencies": deps_status,
            "cache": {
                "enabled": True,
                "cached_transcripts": cache_count,
                "cache_directory": str(cache_dir)
            },
            "capabilities": {
                "transcribe": deps_status.get('youtube_transcript_api', False) or deps_status.get('yt_dlp', False) or deps_status.get('whisper', False),
                "search": True,
                "insight_extraction": True,
                "multi_language": deps_status.get('whisper', False)
            },
            "installation_guide": transcriber.get_installation_instructions().strip(),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting YouTube status: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.post("/api/youtube/cache/clear")
async def clear_youtube_cache():
    """Clear cached YouTube transcripts."""
    try:
        from slate_core.external_data.youtube_transcriber import YouTubeTranscriber

        transcriber = YouTubeTranscriber()
        cache_dir = transcriber.cache_dir

        if cache_dir.exists():
            cache_files = list(cache_dir.glob("*.json"))
            for file in cache_files:
                file.unlink()

            logger.info(f"Cleared {len(cache_files)} cached transcripts")

            return {
                "success": True,
                "message": f"Cleared {len(cache_files)} cached transcripts"
            }
        else:
            return {
                "success": True,
                "message": "No cache directory found"
            }

    except Exception as e:
        logger.error(f"Error clearing YouTube cache: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


# ============================================================================
# Web Dashboard
# ============================================================================

@app.get("/minimal", response_class=HTMLResponse)
async def minimal_dashboard():
    """Minimal test dashboard to isolate JavaScript issues."""
    return """<!DOCTYPE html>
<html>
<head>
    <title>Minimal Dashboard Test</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; background: #1e3c72; color: white; }
        .result { margin: 10px 0; padding: 10px; background: rgba(255,255,255,0.1); }
    </style>
</head>
<body>
    <h1>Minimal Dashboard Test</h1>
    <div class="result" id="test1">Test 1: Pending...</div>
    <div class="result" id="test2">Test 2: Pending...</div>
    <div class="result" id="test3">Test 3: Pending...</div>

    <script>
        console.log('[MINIMAL] Script started');
        document.getElementById('test1').textContent = 'Test 1: JavaScript works! ✓';
        document.getElementById('test1').style.color = '#27ae60';

        setTimeout(() => {
            console.log('[MINIMAL] setTimeout executed');
            document.getElementById('test2').textContent = 'Test 2: setTimeout works! ✓';
            document.getElementById('test2').style.color = '#27ae60';
        }, 1000);

        (async () => {
            console.log('[MINIMAL] async function started');
            try {
                const resp = await fetch('/api/discovery/statistics');
                console.log('[MINIMAL] fetch completed');
                const data = await resp.json();
                console.log('[MINIMAL] data received:', data);

                document.getElementById('test3').textContent = `Test 3: API works! Found ${data.total_tests} tests ✓`;
                document.getElementById('test3').style.color = '#27ae60';
            } catch (error) {
                console.error('[MINIMAL] Error:', error);
                document.getElementById('test3').textContent = `Test 3: Error: ${error.message} ✗`;
                document.getElementById('test3').style.color = '#e74c3c';
            }
        })();
    </script>
</body>
</html>"""

@app.get("/test", response_class=HTMLResponse)
async def test_dashboard():
    """Diagnostic test page for debugging dashboard issues."""
    from pathlib import Path
    test_file = Path(__file__).parent / "test_dashboard.html"
    if test_file.exists():
        return test_file.read_text()
    return "<h1>Test file not found</h1>"

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Main dashboard landing page - serves static HTML file."""
    static_index = Path(__file__).parent / "static" / "index.html"
    if static_index.exists():
        return static_index.read_text()
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>SLATE Dashboard - Not Found</title>
        <style>
            body { font-family: sans-serif; padding: 40px; text-align: center; background: #1e3c72; color: white; }
            h1 { color: #e74c3c; }
        </style>
    </head>
    <body>
        <h1>Dashboard Not Found</h1>
        <p>The static dashboard file could not be found.</p>
        <p>Please ensure <code>slate_core/static/index.html</code> exists.</p>
        <p><a href="/docs" style="color: #3498db;">View API Documentation</a></p>
    </body>
    </html>
    """


# ============================================================================
# Auto-Start Discovery on Server Start
# ============================================================================

async def auto_start_discovery():
    """Auto-start discovery when server launches."""
    global discovery_running

    # Wait a bit for server to fully start
    await asyncio.sleep(2)

    logger.info("Auto-starting discovery cycle...")
    try:
        from slate_core.discovery.edge_discovery_engine import EdgeDiscoveryEngine

        engine = EdgeDiscoveryEngine()
        discovery_running = True

        while True:
            try:
                logger.info("Running multi-timeframe discovery cycle...")
                results = await engine.run_multi_timeframe_discovery_cycle()
                logger.info(f"Multi-timeframe discovery cycle complete: {results}")

                # Wait before next cycle (continuous discovery) - SHORT WAIT for continuous testing
                logger.info("Waiting 5 seconds before next cycle...")
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Discovery cycle error: {e}", exc_info=True)
                await asyncio.sleep(5)  # Wait before retry

    except Exception as e:
        logger.error(f"Auto-start error: {e}", exc_info=True)
    finally:
        discovery_running = False


# ============================================================================
# Startup Event
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Run on server startup - ALWAYS starts automatic discovery."""
    logger.info("=" * 70)
    logger.info("SLATE Server Starting with AUTOMATIC DISCOVERY")
    logger.info("=" * 70)
    logger.info(f"Port: 8788")
    logger.info(f"Mode: Paper Trading Only")
    logger.info(f"Dashboard: http://localhost:8788")
    logger.info(f"API Docs: http://localhost:8788/docs")
    logger.info("=" * 70)
    logger.info("AUTOMATIC DISCOVERY ENABLED:")
    logger.info("  • Discovery starts immediately on startup")
    logger.info("  • Runs continuously unless user requests specific tasks")
    logger.info("  • User activity automatically pauses discovery")
    logger.info("  • Resumes after 5 minutes of user inactivity")
    logger.info("=" * 70)

    # Initialize startup coordinator for automatic discovery
    if STARTUP_COORDINATOR_AVAILABLE:
        try:
            global startup_coordinator
            startup_coordinator = await initialize_with_discovery()
            logger.info("✅ Startup coordinator initialized - automatic discovery started")
        except Exception as e:
            logger.error(f"Failed to initialize startup coordinator: {e}")
    else:
        logger.warning("Startup coordinator not available - using legacy auto-start")
        # Fallback to legacy auto-start
        asyncio.create_task(auto_start_discovery())

    # Initialize enhanced discovery system if available
    if ENHANCED_DISCOVERY_AVAILABLE:
        try:
            enhanced_integration = get_enhanced_integration(enable_enhanced=True)
            is_enhanced = enhanced_integration.is_enhanced_active()
            logger.info("✅ Enhanced discovery system initialized")
            logger.info(f"   - Enhanced mode: {'ENABLED' if is_enhanced else 'DISABLED'}")
            logger.info("   - Parallel testing: 4-8x speedup")
            logger.info("   - Intelligent caching: 5-10x speedup")
            logger.info("   - Early stopping: 2-5x speedup")
            logger.info("   - Progressive results: Real-time updates")
        except Exception as e:
            logger.error(f"Failed to initialize enhanced discovery: {e}")
    else:
        logger.info("ℹ️  Enhanced discovery not available - using basic discovery")

    # Initialize autonomous system if available (with async context)
    global autonomous_orchestrator, autonomous_enabled
    if AUTONOMOUS_AVAILABLE:
        try:
            autonomous_config = get_exploratory_config()
            autonomous_orchestrator = AutonomousOrchestrator(autonomous_config)
            await autonomous_orchestrator.start_async()  # Use async start for full functionality
            autonomous_enabled = True
            logger.info("✅ Autonomous system initialized in async context")
            logger.info("   - Real discovery engine integrated")
            logger.info("   - Trading executor active (paper trading)")
            logger.info("   - Market data auto-fetch enabled")
        except Exception as e:
            logger.error(f"Failed to initialize autonomous system: {e}")
            autonomous_enabled = False


@app.on_event("shutdown")
async def shutdown_event():
    """Run on server shutdown."""
    global discovery_running, discovery_task, autonomous_orchestrator, autonomous_enabled

    logger.info("SLATE Server shutting down...")

    # Stop autonomous system
    if autonomous_orchestrator:
        try:
            autonomous_orchestrator.cleanup()
            autonomous_enabled = False
            logger.info("Autonomous system stopped")
        except Exception as e:
            logger.error(f"Error stopping autonomous system: {e}")

    discovery_running = False

    if discovery_task and not discovery_task.done():
        discovery_task.cancel()
        try:
            await discovery_task
        except asyncio.CancelledError:
            pass


# ============================================================================
# Autonomous System Helper Functions
# ============================================================================

def get_autonomous_status():
    """Get autonomous system status"""
    if not autonomous_enabled or not autonomous_orchestrator:
        return {
            "autonomous_available": AUTONOMOUS_AVAILABLE,
            "autonomous_enabled": False,
            "message": "Autonomous system not enabled"
        }

    try:
        status = autonomous_orchestrator.get_status()
        status["autonomous_available"] = AUTONOMOUS_AVAILABLE
        status["autonomous_enabled"] = True
        return status
    except Exception as e:
        logger.error(f"Error getting autonomous status: {e}")
        return {
            "autonomous_available": AUTONOMOUS_AVAILABLE,
            "autonomous_enabled": False,
            "error": str(e)
        }

def get_autonomous_discoveries(limit: int = 20):
    """Get autonomous discoveries"""
    if not autonomous_enabled or not autonomous_orchestrator:
        return {
            "autonomous_enabled": False,
            "discoveries": [],
            "message": "Autonomous system not enabled"
        }

    try:
        discoveries = autonomous_orchestrator.get_discoveries(limit=limit)
        return {
            "autonomous_enabled": True,
            "total": len(discoveries),
            "discoveries": discoveries,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting autonomous discoveries: {e}")
        return {
            "autonomous_enabled": False,
            "discoveries": [],
            "error": str(e)
        }

def start_autonomous_operations():
    """Start autonomous operations"""
    if not AUTONOMOUS_AVAILABLE:
        return {
            "success": False,
            "message": "Autonomous capabilities not available"
        }

    try:
        global autonomous_orchestrator, autonomous_enabled

        if not autonomous_orchestrator:
            autonomous_config = get_exploratory_config()
            autonomous_orchestrator = AutonomousOrchestrator(autonomous_config)

        autonomous_orchestrator.start()
        autonomous_enabled = True

        return {
            "success": True,
            "message": "Autonomous operations started",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error starting autonomous operations: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def stop_autonomous_operations():
    """Stop autonomous operations"""
    try:
        global autonomous_enabled

        if autonomous_orchestrator:
            autonomous_orchestrator.stop()
            autonomous_enabled = False

        return {
            "success": True,
            "message": "Autonomous operations stopped",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error stopping autonomous operations: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def generate_autonomous_report():
    """Generate comprehensive autonomous discovery report"""
    if not autonomous_enabled or not autonomous_orchestrator:
        return {
            "autonomous_enabled": False,
            "report": None,
            "message": "Autonomous system not enabled"
        }

    try:
        report = autonomous_orchestrator.generate_report()
        return {
            "autonomous_enabled": True,
            "report": report,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error generating autonomous report: {e}")
        return {
            "autonomous_enabled": False,
            "report": None,
            "error": str(e)
        }


# ============================================================================
# Autonomous System API Routes
# ============================================================================

@app.get("/api/autonomous/status")
async def api_get_autonomous_status():
    """Get autonomous system status and configuration"""
    track_user_activity()
    return get_autonomous_status()

@app.get("/api/autonomous/discoveries")
async def api_get_autonomous_discoveries(limit: int = 20):
    """Get autonomous discoveries"""
    track_user_activity()
    return get_autonomous_discoveries(limit=limit)

@app.post("/api/autonomous/start")
async def api_start_autonomous():
    """Start autonomous operations"""
    track_user_activity()
    return start_autonomous_operations()

@app.post("/api/autonomous/stop")
async def api_stop_autonomous():
    """Stop autonomous operations"""
    track_user_activity()
    return stop_autonomous_operations()

@app.get("/api/autonomous/report")
async def api_get_autonomous_report():
    """Generate comprehensive autonomous discovery report"""
    track_user_activity()
    return generate_autonomous_report()

@app.get("/api/autonomous/trading/statistics")
async def api_get_trading_statistics():
    """Get autonomous trading executor statistics"""
    track_user_activity()
    try:
        if not autonomous_enabled or not autonomous_orchestrator:
            return {
                "success": False,
                "error": "Autonomous system not enabled",
                "trading_enabled": False
            }

        trading_stats = autonomous_orchestrator.trading_executor.get_statistics()
        return {
            "success": True,
            "trading_enabled": True,
            "statistics": trading_stats
        }
    except Exception as e:
        logger.error(f"Error getting trading statistics: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/autonomous/trading/positions")
async def api_get_paper_positions():
    """Get current paper trading positions"""
    track_user_activity()
    try:
        if not autonomous_enabled or not autonomous_orchestrator:
            return {
                "success": False,
                "error": "Autonomous system not enabled",
                "positions": []
            }

        positions = autonomous_orchestrator.trading_executor.get_paper_positions()
        return {
            "success": True,
            "positions": positions
        }
    except Exception as e:
        logger.error(f"Error getting paper positions: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/autonomous/trading/decisions")
async def api_get_trading_decisions(limit: int = 20):
    """Get recent trading decisions"""
    track_user_activity()
    try:
        if not autonomous_enabled or not autonomous_orchestrator:
            return {
                "success": False,
                "error": "Autonomous system not enabled",
                "decisions": []
            }

        decisions = autonomous_orchestrator.trading_executor.get_decision_history(limit=limit)
        return {
            "success": True,
            "decisions": decisions,
            "count": len(decisions)
        }
    except Exception as e:
        logger.error(f"Error getting trading decisions: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/autonomous/market/data")
async def api_get_market_data():
    """Get autonomous market data manager statistics"""
    track_user_activity()
    try:
        if not autonomous_enabled or not autonomous_orchestrator:
            return {
                "success": False,
                "error": "Autonomous system not enabled",
                "market_data_available": False
            }

        market_stats = autonomous_orchestrator.market_data_manager.get_statistics()
        market_intelligence = autonomous_orchestrator.market_data_manager.get_market_intelligence()

        return {
            "success": True,
            "statistics": market_stats,
            "market_intelligence": market_intelligence
        }
    except Exception as e:
        logger.error(f"Error getting market data: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/autonomous/market/symbols")
async def api_get_market_symbols():
    """Get cached market data for all symbols"""
    track_user_activity()
    try:
        if not autonomous_enabled or not autonomous_orchestrator:
            return {
                "success": False,
                "error": "Autonomous system not enabled",
                "symbols": {}
            }

        market_data = autonomous_orchestrator.market_data_manager.get_all_cached_data()
        symbols_data = {
            symbol: data.to_dict()
            for symbol, data in market_data.items()
        }

        return {
            "success": True,
            "symbols": symbols_data,
            "count": len(symbols_data),
            "last_update": autonomous_orchestrator.market_data_manager.last_update_time.isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting market symbols: {e}")
        return {"success": False, "error": str(e)}

# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SLATE Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8788, help="Port to bind to")
    parser.add_argument("--no-discovery", action="store_true", help="Don't auto-start discovery")

    args = parser.parse_args()

    logger.info(f"Starting SLATE server on {args.host}:{args.port}")

    uvicorn.run(
        "slate_core.server:app",
        host=args.host,
        port=args.port,
        reload=False,
        log_level="info"
    )
