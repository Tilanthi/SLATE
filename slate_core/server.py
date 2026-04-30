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
# Web Dashboard
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Main dashboard landing page."""

    html = """
<!DOCTYPE html>
<html>
<head>
    <title>SLATE Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 10px;
            font-size: 2.5em;
        }
        .subtitle {
            text-align: center;
            color: rgba(255,255,255,0.8);
            margin-bottom: 30px;
        }
        .warning {
            background: #e74c3c;
            color: white;
            text-align: center;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 20px;
            font-weight: bold;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .stat-card h3 {
            color: #2c3e50;
            margin-bottom: 10px;
            font-size: 0.9em;
            text-transform: uppercase;
        }
        .stat-card .value {
            font-size: 2em;
            font-weight: bold;
            color: #3498db;
        }
        .stat-card .value.running {
            color: #27ae60;
        }
        .stat-card .value.idle {
            color: #95a5a6;
        }
        .strategy-item {
            border-bottom: 1px solid #ecf0f1;
            padding: 12px 0;
        }
        .strategy-item:last-child {
            border-bottom: none;
        }
        .strategy-item small {
            color: #7f8c8d;
        }
        .loading {
            color: #95a5a6;
            font-style: italic;
        }
        .actions {
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .actions h2 {
            margin-bottom: 15px;
            color: #2c3e50;
        }
        button {
            background: #27ae60;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 5px;
            font-size: 1em;
            cursor: pointer;
            margin-right: 10px;
        }
        button:hover {
            background: #229954;
        }
        button:disabled {
            background: #95a5a6;
            cursor: not-allowed;
        }
        .links {
            background: white;
            border-radius: 10px;
            padding: 20px;
        }
        .links h2 {
            margin-bottom: 15px;
            color: #2c3e50;
        }
        .links a {
            color: #3498db;
            text-decoration: none;
            margin-right: 20px;
        }
        .links a:hover {
            text-decoration: underline;
        }
        #strategies {
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-top: 20px;
        }
        #strategies h2 {
            margin-bottom: 15px;
            color: #2c3e50;
        }
        .strategy-item {
            border-bottom: 1px solid #ecf0f1;
            padding: 10px 0;
        }
        .strategy-item:last-child {
            border-bottom: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧪 SLATE Dashboard</h1>
        <p class="subtitle">Strategy Learning & Autonomous Trading Engine</p>

        <div class="warning">
            ⚠️ PAPER TRADING ONLY - No real money is ever risked
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <h3>Status</h3>
                <div class="value" id="status">Loading...</div>
            </div>
            <div class="stat-card">
                <h3>Total Tests</h3>
                <div class="value" id="total-tests">-</div>
            </div>
            <div class="stat-card">
                <h3>Profitable</h3>
                <div class="value" id="profitable">-</div>
            </div>
            <div class="stat-card">
                <h3>Best Return</h3>
                <div class="value" id="best-return">-</div>
            </div>
        </div>

        <div class="actions">
            <h2>Discovery Control</h2>
            <button onclick="startDiscovery()" id="start-btn">Start Discovery</button>
            <button onclick="stopDiscovery()" id="stop-btn" disabled>Stop Discovery</button>
            <button onclick="refreshData()">Refresh Data</button>
        </div>

        <div class="links">
            <h2>Quick Links</h2>
            <a href="/docs" target="_blank">📚 API Documentation</a>
            <a href="/redoc" target="_blank">📖 ReDoc</a>
            <a href="/api/discovery/statistics" target="_blank">📊 Statistics JSON</a>
        </div>

        <div id="strategies">
            <h2>Top Strategies</h2>
            <p id="discovery-status" class="loading">Discovery runs automatically in the background...</p>
            <div id="strategies-list"></div>
        </div>
    </div>

    <script>
        async function refreshData() {
            try {
                // Get statistics
                const statsResp = await fetch('/api/discovery/statistics');
                const stats = await statsResp.json();

                const statusEl = document.getElementById('status');
                if (stats.discovery_running) {
                    statusEl.textContent = '● Running';
                    statusEl.className = 'value running';
                } else {
                    statusEl.textContent = '○ Idle';
                    statusEl.className = 'value idle';
                }

                document.getElementById('total-tests').textContent = stats.total_tests || 0;
                document.getElementById('profitable').textContent = stats.profitable_strategies || 0;
                // best_return is now a decimal (0.0379), multiply by 100 for percentage
                document.getElementById('best-return').textContent = stats.best_return !== undefined ? (stats.best_return * 100).toFixed(1) + '%' : '-';

                // Get top strategies
                const strategiesResp = await fetch('/api/discovery/top?limit=10');
                const data = await strategiesResp.json();

                const list = document.getElementById('strategies-list');
                const statusEl = document.getElementById('discovery-status');

                if (data.strategies && data.strategies.length > 0) {
                    // Hide the status message when we have strategies
                    if (statusEl) statusEl.style.display = 'none';

                    list.innerHTML = data.strategies.map((s, i) => `
                        <div class="strategy-item">
                            <strong>#${i+1} ${s.edge_type}</strong>: ${s.edge_description}<br>
                            <small>
                            Return: ${(s.total_return_pct * 100).toFixed(2)}% |
                            Profit: $${s.total_profit_usdt.toFixed(2)} |
                            Sharpe: ${s.sharpe_ratio.toFixed(2)} |
                            Win Rate: ${(s.win_rate * 100).toFixed(1)}% |
                            Drawdown: ${(s.max_drawdown_pct * 100).toFixed(2)}%
                            </small>
                        </div>
                    `).join('');
                } else {
                    // Show loading status when no strategies yet
                    if (statusEl) {
                        statusEl.style.display = 'block';
                        statusEl.textContent = stats.discovery_running
                            ? 'Discovery is running... Strategies will appear here shortly.'
                            : 'No strategies yet. Click "Start Discovery" to begin.';
                    }
                    list.innerHTML = '';
                }

                // Update button states
                document.getElementById('start-btn').disabled = stats.discovery_running;
                document.getElementById('stop-btn').disabled = !stats.discovery_running;

            } catch (error) {
                console.error('Error refreshing data:', error);
            }
        }

        async function startDiscovery() {
            try {
                const resp = await fetch('/api/discovery/start', { method: 'POST' });
                const data = await resp.json();
                alert(data.message);
                setTimeout(refreshData, 1000);
            } catch (error) {
                alert('Error starting discovery: ' + error);
            }
        }

        async function stopDiscovery() {
            try {
                const resp = await fetch('/api/discovery/stop', { method: 'POST' });
                const data = await resp.json();
                alert(data.message);
                setTimeout(refreshData, 1000);
            } catch (error) {
                alert('Error stopping discovery: ' + error);
            }
        }

        // Auto-refresh every 5 seconds
        refreshData();
        setInterval(refreshData, 5000);
    </script>
</body>
</html>
    """

    return html


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

                # Wait before next cycle (continuous discovery)
                logger.info("Waiting 60 seconds before next cycle...")
                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"Discovery cycle error: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait before retry

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
