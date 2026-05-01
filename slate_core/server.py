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
