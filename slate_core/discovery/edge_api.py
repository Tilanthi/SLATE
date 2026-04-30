#!/usr/bin/env python3
"""
SLATE Edge Discovery API

REST API endpoints for edge discovery system:
- Trigger discovery cycles
- Get top-performing edges
- View edge statistics
- Access detailed edge analysis
"""

import logging
import sqlite3
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/edge-discovery", tags=["edge-discovery"])

DB_PATH = "slate_core/slate_realistic_discoveries.db"


class EdgeDiscoveryTrigger(BaseModel):
    """Request to trigger a discovery cycle."""
    cycles: int = 1


class EdgeDiscoveryResponse(BaseModel):
    """Response from a discovery cycle."""
    status: str
    message: str
    cycle_id: Optional[str] = None


@router.post("/trigger")
async def trigger_discovery(request: EdgeDiscoveryTrigger = EdgeDiscoveryTrigger()) -> EdgeDiscoveryResponse:
    """
    Trigger a new edge discovery cycle.

    Runs immediate discovery on SOLUSDT data with full realism.
    """
    try:
        from .edge_discovery_engine import EdgeDiscoveryEngine

        engine = EdgeDiscoveryEngine()

        # Run discovery cycle
        results = await engine.run_discovery_cycle()

        return EdgeDiscoveryResponse(
            status="success",
            message=f"Discovery complete: {results['passed_validation']}/{results['total_candidates']} edges passed",
            cycle_id=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"Error triggering discovery: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_edge_statistics():
    """Get overall edge discovery statistics (USDT profit focused)."""
    try:
        conn = sqlite3.connect(DB_PATH)
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

        # By edge type
        cursor.execute("""
            SELECT edge_type, COUNT(*) as count, AVG(total_profit_usdt) as avg_profit_usdt
            FROM edge_discoveries
            GROUP BY edge_type
            ORDER BY count DESC
        """)
        by_type = [
            {"type": row[0], "count": row[1], "avg_profit_usdt": row[2]}
            for row in cursor.fetchall()
        ]

        # Average metrics
        cursor.execute("""
            SELECT
                AVG(total_profit_usdt) as avg_profit_usdt,
                AVG(vs_buy_hold_usdt) as avg_vs_buy_hold,
                AVG(max_drawdown_pct) as avg_drawdown_pct,
                AVG(sharpe_ratio) as avg_sharpe,
                AVG(total_trades) as avg_trades,
                AVG(monte_carlo_win_rate) as avg_mc_win_rate,
                SUM(CASE WHEN beat_market THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as beat_market_rate
            FROM edge_discoveries
        """)
        row = cursor.fetchone()
        averages = {
            "avg_profit_usdt": row[0] or 0,
            "avg_vs_buy_hold": row[1] or 0,
            "avg_drawdown_pct": row[2] or 0,
            "avg_sharpe": row[3] or 0,
            "avg_trades": row[4] or 0,
            "avg_mc_win_rate": row[5] or 0,
            "beat_market_rate": row[6] or 0
        }

        conn.close()

        return {
            "total_discoveries": total,
            "passed_validation": passed,
            "beat_market": beat_market,
            "pass_rate": passed / total if total > 0 else 0,
            "by_type": by_type,
            "averages": averages,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results/top")
async def get_top_edges(limit: int = 20, min_profit_usdt: float = 0.0):
    """
    Get top-performing edges ranked by USDT PROFIT.

    Args:
        limit: Maximum number of results to return
        min_profit_usdt: Minimum USDT profit threshold
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                edge_type,
                edge_description,
                total_profit_usdt,
                total_return_pct,
                final_capital,
                buy_hold_profit_usdt,
                buy_hold_return_pct,
                vs_buy_hold_usdt,
                beat_market,
                max_drawdown_pct,
                max_drawdown_usdt,
                sharpe_ratio,
                total_trades,
                win_rate,
                profit_factor,
                monte_carlo_mean_profit_usdt,
                monte_carlo_win_rate,
                passed_validation,
                timestamp,
                rank_score
            FROM edge_discoveries
            WHERE total_profit_usdt >= ? AND passed_validation = 1
            ORDER BY total_profit_usdt DESC
            LIMIT ?
        """, (min_profit_usdt, limit))

        results = []
        for row in cursor.fetchall():
            results.append({
                "edge_type": row[0],
                "description": row[1],
                "total_profit_usdt": row[2],
                "total_return_pct": row[3],
                "final_capital": row[4],
                "buy_hold_profit_usdt": row[5],
                "buy_hold_return_pct": row[6],
                "vs_buy_hold_usdt": row[7],
                "beat_market": bool(row[8]),
                "max_drawdown_pct": row[9],
                "max_drawdown_usdt": row[10],
                "sharpe_ratio": row[11],
                "total_trades": row[12],
                "win_rate": row[13],
                "profit_factor": row[14],
                "monte_carlo_mean_profit_usdt": row[15],
                "monte_carlo_win_rate": row[16],
                "passed_validation": bool(row[17]),
                "timestamp": row[18],
                "rank_score": row[19]
            })

        conn.close()

        return {
            "count": len(results),
            "results": results
        }

    except Exception as e:
        logger.error(f"Error getting top edges: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results/{edge_id}")
async def get_edge_details(edge_id: int):
    """Get detailed information about a specific edge."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM edge_discoveries WHERE id = ?
        """, (edge_id,))

        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Edge not found")

        # Get column names
        cursor.execute("PRAGMA table_info(edge_discoveries)")
        columns = [col[1] for col in cursor.fetchall()]

        result = dict(zip(columns, row))

        conn.close()

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting edge details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard")
async def get_edge_dashboard_data():
    """Get aggregated data for the edge discovery dashboard (USDT profit focused)."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Top 5 edges by USDT profit
        cursor.execute("""
            SELECT edge_description, total_profit_usdt, total_return_pct,
                   max_drawdown_pct, sharpe_ratio, beat_market
            FROM edge_discoveries
            WHERE passed_validation = 1
            ORDER BY total_profit_usdt DESC
            LIMIT 5
        """)
        top_edges = [
            {
                "description": row[0],
                "profit_usdt": row[1],
                "return_pct": row[2],
                "drawdown_pct": row[3],
                "sharpe": row[4],
                "beat_market": bool(row[5])
            }
            for row in cursor.fetchall()
        ]

        # Recent discoveries
        cursor.execute("""
            SELECT edge_type, edge_description, total_profit_usdt,
                   passed_validation, beat_market, timestamp
            FROM edge_discoveries
            ORDER BY timestamp DESC
            LIMIT 10
        """)
        recent = [
            {
                "type": row[0],
                "description": row[1],
                "profit_usdt": row[2],
                "passed": bool(row[3]),
                "beat_market": bool(row[4]),
                "timestamp": row[5]
            }
            for row in cursor.fetchall()
        ]

        # Performance distribution (by USDT profit)
        cursor.execute("""
            SELECT
                CASE
                    WHEN total_profit_usdt > 500 THEN 'exceptional'
                    WHEN total_profit_usdt > 200 THEN 'good'
                    WHEN total_profit_usdt > 0 THEN 'profitable'
                    ELSE 'unprofitable'
                END as performance_tier,
                COUNT(*) as count
            FROM edge_discoveries
            GROUP BY performance_tier
            ORDER BY
                CASE performance_tier
                    WHEN 'exceptional' THEN 1
                    WHEN 'good' THEN 2
                    WHEN 'profitable' THEN 3
                    ELSE 4
                END
        """)
        distribution = {row[0]: row[1] for row in cursor.fetchall()}

        # Market beating stats
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN beat_market THEN 1 ELSE 0 END) as beat_count,
                AVG(vs_buy_hold_usdt) as avg_outperformance
            FROM edge_discoveries
            WHERE passed_validation = 1
        """)
        row = cursor.fetchone()
        market_stats = {
            "total_validated": row[0],
            "beat_market_count": row[1],
            "beat_market_rate": row[1] / row[0] if row[0] > 0 else 0,
            "avg_outperformance_usdt": row[2]
        }

        conn.close()

        return {
            "top_edges": top_edges,
            "recent_discoveries": recent,
            "performance_distribution": distribution,
            "market_comparison": market_stats,
            "last_updated": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cleanup")
async def cleanup_old_edges(days_to_keep: int = 30):
    """
    Clean up old edge discovery results.

    Args:
        days_to_keep: Number of days of history to retain
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Count old records
        cursor.execute("""
            SELECT COUNT(*) FROM edge_discoveries
            WHERE datetime(timestamp) < datetime('now', '-' || ? || ' days')
        """, (days_to_keep,))
        old_count = cursor.fetchone()[0]

        # Delete old records
        cursor.execute("""
            DELETE FROM edge_discoveries
            WHERE datetime(timestamp) < datetime('now', '-' || ? || ' days')
        """, (days_to_keep,))

        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        return {
            "status": "success",
            "deleted": deleted,
            "message": f"Deleted {deleted} old edge discoveries (older than {days_to_keep} days)"
        }

    except Exception as e:
        logger.error(f"Error cleaning up edges: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
