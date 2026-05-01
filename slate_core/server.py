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


# ============================================================================
# API Routes - Health & Status
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    from slate_core.discovery.edge_discovery_engine import EdgeDiscoveryEngine

    return {
        "status": "healthy",
        "mode": "paper_trading",
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": (datetime.now() - start_time).total_seconds(),
        "discovery_running": discovery_running,
        "port": 8788
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

@app.post("/api/discovery/start")
async def start_discovery():
    """Start a discovery cycle."""
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
                logger.info("Starting auto-discovery cycle...")
                results = await engine.run_discovery_cycle()
                logger.info(f"Discovery complete: {results}")
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
                logger.info("Running discovery cycle...")
                results = await engine.run_discovery_cycle()
                logger.info(f"Discovery cycle complete: {results}")

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
    """Run on server startup."""
    logger.info("=" * 60)
    logger.info("SLATE Server Starting")
    logger.info("=" * 60)
    logger.info(f"Port: 8788")
    logger.info(f"Mode: Paper Trading Only")
    logger.info(f"Dashboard: http://localhost:8788")
    logger.info(f"API Docs: http://localhost:8788/docs")
    logger.info("=" * 60)

    # Start auto-discovery in background
    asyncio.create_task(auto_start_discovery())


@app.on_event("shutdown")
async def shutdown_event():
    """Run on server shutdown."""
    global discovery_running, discovery_task

    logger.info("SLATE Server shutting down...")

    discovery_running = False

    if discovery_task and not discovery_task.done():
        discovery_task.cancel()
        try:
            await discovery_task
        except asyncio.CancelledError:
            pass


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
