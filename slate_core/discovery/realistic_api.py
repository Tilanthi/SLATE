#!/usr/bin/env python3
"""
SLATE Realistic Discovery API Endpoints

API endpoints for the realistic strategy discovery system.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Optional
import logging

from .realistic_backtester import (
    get_discovery_system,
    BacktestConfig,
    BacktestResult
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/realistic-discovery", tags=["realistic-discovery"])


@router.post("/start")
async def start_discovery(cycles: int = 100):
    """Start continuous realistic discovery."""
    system = get_discovery_system()

    if system.running:
        return {"status": "already_running", "message": "Discovery already running"}

    # Start in background
    import asyncio
    asyncio.create_task(system.start_discovery(cycles))

    return {"status": "started", "cycles": cycles}


@router.post("/stop")
async def stop_discovery():
    """Stop continuous discovery."""
    system = get_discovery_system()
    system.stop_discovery()
    return {"status": "stopped"}


@router.get("/status")
async def get_discovery_status():
    """Get discovery system status."""
    system = get_discovery_system()
    return system.get_status()


@router.get("/results")
async def get_recent_results(limit: int = 50) -> List[Dict]:
    """Get recent backtest results."""
    system = get_discovery_system()
    return system.get_recent_results(limit)


@router.get("/results/top")
async def get_top_strategies(limit: int = 20) -> List[Dict]:
    """Get top performing strategies including both single-path and multi-path results.

    Returns a diverse set of strategies, including top performers from each strategy type.
    """
    system = get_discovery_system()

    # Query directly from database for all historical results
    from slate_core.discovery.realistic_memory import get_realistic_discovery_memory

    memory = get_realistic_discovery_memory()
    all_results = []

    # Fetch all results from database, sorted by robustness and sharpe
    import sqlite3

    conn = sqlite3.connect(memory.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Get top 2 from each strategy type to ensure diversity
        cursor.execute("""
            SELECT
                strategy_id, strategy_name, strategy_type, timeframe,
                sharpe_ratio, total_return, max_drawdown, win_rate,
                profit_factor, calmar_ratio, equity_smoothness,
                evaluation_type, num_paths,
                mean_sharpe, std_sharpe,
                mean_return, std_return, min_return, max_return, median_return,
                mean_max_drawdown, worst_max_drawdown,
                robustness_score, consistency_ratio,
                return_ci_lower, return_ci_upper,
                sharpe_ci_lower, sharpe_ci_upper,
                ROW_NUMBER() OVER (PARTITION BY strategy_type ORDER BY
                    CASE WHEN evaluation_type = 'multipath' THEN 1 ELSE 0 END DESC,
                    COALESCE(robustness_score, 0) DESC,
                    COALESCE(sharpe_ratio, 0) DESC
                ) as rn
            FROM discovery_results
        """)

        rows = cursor.fetchall()

        for row in rows:
            result = dict(row)

            # Only take top 2 from each type
            if result['rn'] > 2:
                continue

            if result['evaluation_type'] == 'multipath':
                all_results.append({
                    "strategy_id": result['strategy_id'],
                    "strategy_name": result['strategy_name'],
                    "strategy_type": result['strategy_type'],
                    "timeframe": result['timeframe'],
                    "sharpe_ratio": result['mean_sharpe'] or result['sharpe_ratio'],
                    "mean_sharpe": result['mean_sharpe'],
                    "std_sharpe": result['std_sharpe'],
                    "total_return": result['mean_return'] or result['total_return'],
                    "mean_return": result['mean_return'],
                    "std_return": result['std_return'],
                    "min_return": result['min_return'],
                    "max_return": result['max_return'],
                    "median_return": result['median_return'],
                    "max_drawdown": result['mean_max_drawdown'] or result['max_drawdown'],
                    "worst_max_drawdown": result['worst_max_drawdown'],
                    "robustness_score": result['robustness_score'] or 0,
                    "consistency_ratio": result['consistency_ratio'] or 0,
                    "return_ci_lower": result['return_ci_lower'],
                    "return_ci_upper": result['return_ci_upper'],
                    "sharpe_ci_lower": result['sharpe_ci_lower'],
                    "sharpe_ci_upper": result['sharpe_ci_upper'],
                    "num_paths": result['num_paths'] or 0,
                    "evaluation_type": "multipath"
                })
            else:
                all_results.append({
                    "strategy_id": result['strategy_id'],
                    "strategy_name": result['strategy_name'],
                    "strategy_type": result['strategy_type'],
                    "timeframe": result['timeframe'],
                    "sharpe_ratio": result['sharpe_ratio'] or 0,
                    "total_return": result['total_return'] or 0,
                    "max_drawdown": result['max_drawdown'] or 0,
                    "win_rate": result.get('win_rate', 0),
                    "profit_factor": result.get('profit_factor', 0),
                    "calmar_ratio": result.get('calmar_ratio', 0),
                    "equity_curve_smoothness": result.get('equity_smoothness', 0),
                    "evaluation_type": "singlepath",
                    "num_paths": 0
                })
    finally:
        conn.close()

    # Apply final sort and limit
    def sort_key(r):
        if r["evaluation_type"] == "multipath":
            return (1, r.get("robustness_score", 0))
        else:
            return (0, r["sharpe_ratio"])

    sorted_results = sorted(all_results, key=sort_key, reverse=True)

    return sorted_results[:limit]


@router.get("/insights")
async def get_discovery_insights():
    """Get insights from discovery evolution."""
    system = get_discovery_system()
    return system.get_insights()


@router.get("/by-type/{strategy_type}")
async def get_results_by_type(strategy_type: str, limit: int = 20):
    """Get results filtered by strategy type."""
    from slate_core.discovery.realistic_memory import get_realistic_discovery_memory
    import sqlite3

    memory = get_realistic_discovery_memory()

    conn = sqlite3.connect(memory.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                strategy_id, strategy_name, strategy_type, timeframe,
                sharpe_ratio, total_return, max_drawdown,
                evaluation_type, mean_sharpe, mean_return,
                robustness_score, consistency_ratio
            FROM discovery_results
            WHERE strategy_type = ?
            ORDER BY
                CASE WHEN evaluation_type = 'multipath' THEN 1 ELSE 0 END DESC,
                COALESCE(robustness_score, 0) DESC,
                COALESCE(sharpe_ratio, 0) DESC
            LIMIT ?
        """, (strategy_type, limit))

        results = []
        for row in cursor.fetchall():
            result = dict(row)
            results.append({
                "strategy_id": result['strategy_id'],
                "strategy_name": result['strategy_name'],
                "strategy_type": result['strategy_type'],
                "timeframe": result['timeframe'],
                "sharpe_ratio": result['mean_sharpe'] or result['sharpe_ratio'],
                "total_return": result['mean_return'] or result['total_return'],
                "max_drawdown": result['max_drawdown'],
                "evaluation_type": result['evaluation_type'],
                "robustness_score": result['robustness_score']
            })

        return results

    finally:
        conn.close()


@router.get("/equity-curves")
async def get_equity_curves(limit: int = 10):
    """Get equity curves for top strategies."""
    from slate_core.discovery.realistic_memory import get_realistic_discovery_memory
    import sqlite3

    memory = get_realistic_discovery_memory()

    conn = sqlite3.connect(memory.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                strategy_name, strategy_type, equity_curve,
                sharpe_ratio, total_return
            FROM discovery_results
            WHERE equity_curve IS NOT NULL
            ORDER BY sharpe_ratio DESC
            LIMIT ?
        """, (limit,))

        results = []
        for row in cursor.fetchall():
            result = dict(row)
            # Parse equity curve JSON
            try:
                import json
                equity_curve = json.loads(result['equity_curve']) if result['equity_curve'] else []
            except:
                equity_curve = []

            results.append({
                "strategy_name": result['strategy_name'],
                "strategy_type": result['strategy_type'],
                "equity_curve": equity_curve,
                "sharpe_ratio": result['sharpe_ratio'],
                "total_return": result['total_return']
            })

        return results

    finally:
        conn.close()


@router.get("/statistics")
async def get_discovery_statistics():
    """Get comprehensive discovery statistics including robustness metrics."""
    from slate_core.discovery.realistic_memory import get_realistic_discovery_memory
    import sqlite3
    from collections import Counter

    system = get_discovery_system()
    memory = get_realistic_discovery_memory()

    # Query statistics from database
    conn = sqlite3.connect(memory.db_path)
    cursor = conn.cursor()

    try:
        # Get counts
        cursor.execute("SELECT COUNT(*) FROM discovery_results")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM discovery_results WHERE evaluation_type = 'multipath'")
        multipath_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM discovery_results WHERE evaluation_type = 'singlepath'")
        singlepath_count = cursor.fetchone()[0]

        # Get strategy type distribution
        cursor.execute("""
            SELECT strategy_type, COUNT(*) as count
            FROM discovery_results
            GROUP BY strategy_type
            ORDER BY count DESC
        """)
        type_counts = {row[0]: row[1] for row in cursor.fetchall()}

        # Get timeframe distribution
        cursor.execute("""
            SELECT timeframe, COUNT(*) as count
            FROM discovery_results
            GROUP BY timeframe
            ORDER BY count DESC
        """)
        timeframe_counts = {row[0]: row[1] for row in cursor.fetchall()}

        # Get performance metrics
        cursor.execute("""
            SELECT
                AVG(total_return) as avg_return,
                MAX(total_return) as best_return,
                MIN(total_return) as worst_return,
                AVG(sharpe_ratio) as avg_sharpe,
                MAX(sharpe_ratio) as best_sharpe,
                AVG(max_drawdown) as avg_max_drawdown,
                MIN(max_drawdown) as best_max_drawdown,
                SUM(CASE WHEN total_return > 0 THEN 1 ELSE 0 END) as profitable_count
            FROM discovery_results
            WHERE evaluation_type = 'singlepath'
        """)
        perf_row = cursor.fetchone()
        avg_return = perf_row[0] or 0
        best_return = perf_row[1] or 0
        worst_return = perf_row[2] or 0
        avg_sharpe = perf_row[3] or 0
        best_sharpe = perf_row[4] or 0
        avg_max_drawdown = perf_row[5] or 0
        best_max_drawdown = perf_row[6] or 0
        profitable_count = perf_row[7] or 0

        # Get best overall result
        cursor.execute("""
            SELECT strategy_name, strategy_type, sharpe_ratio, total_return
            FROM discovery_results
            ORDER BY COALESCE(robustness_score, 0) DESC, sharpe_ratio DESC
            LIMIT 1
        """)
        best_row = cursor.fetchone()
        best_overall = {
            'name': best_row[0],
            'type': best_row[1],
            'sharpe': best_row[2],
            'return': best_row[3]
        } if best_row else {}

        # Get robustness summary from multi-path results
        cursor.execute("""
            SELECT
                AVG(robustness_score) as avg_robustness,
                MAX(robustness_score) as best_robustness,
                AVG(consistency_ratio) as avg_consistency,
                SUM(CASE WHEN consistency_ratio > 0.7 THEN 1 ELSE 0 END) as high_consistency_count
            FROM discovery_results
            WHERE evaluation_type = 'multipath'
        """)
        robust_row = cursor.fetchone()
        robustness_summary = {
            'avg_robustness': robust_row[0] or 0,
            'best_robustness': robust_row[1] or 0,
            'avg_consistency': robust_row[2] or 0,
            'high_consistency_count': robust_row[3] or 0
        }

        # Get best by type
        cursor.execute("""
            SELECT
                strategy_type,
                MAX(sharpe_ratio) as best_sharpe,
                MAX(total_return) as best_return,
                MAX(COALESCE(robustness_score, 0)) as best_robustness
            FROM discovery_results
            GROUP BY strategy_type
        """)
        best_by_type = {}
        for row in cursor.fetchall():
            best_by_type[row[0]] = {
                'sharpe': row[1],
                'return': row[2],
                'robustness': row[3]
            }

        insights = {
            'best_overall': best_overall,
            'robustness_summary': robustness_summary,
            'best_by_type': best_by_type
        }

        return {
            "total_tests": total,
            "multipath_tests": multipath_count,
            "singlepath_tests": singlepath_count,
            "running": system.running,
            "workers": system.workers,
            "strategy_types": type_counts,
            "timeframes": timeframe_counts,
            "performance": {
                "avg_return": avg_return,
                "best_return": best_return,
                "worst_return": worst_return,
                "avg_sharpe": avg_sharpe,
                "best_sharpe": best_sharpe,
                "avg_max_drawdown": avg_max_drawdown,
                "best_max_drawdown": best_max_drawdown
            },
            "profitable_strategies": profitable_count,
            "profitable_percentage": (profitable_count / singlepath_count * 100) if singlepath_count > 0 else 0,
            "insights": insights
        }

    finally:
        conn.close()


@router.post("/test-strategy")
async def test_single_strategy(strategy: Dict):
    """Test a single strategy."""
    system = get_discovery_system()

    result = await system.backtester.run_backtest(
        strategy,
        symbol=strategy.get('symbol', 'BTCUSDT'),
        timeframe=strategy.get('timeframe', '1m')
    )

    if result is None:
        raise HTTPException(status_code=400, detail="Backtest failed")

    return {
        "strategy_id": result.strategy_id,
        "strategy_name": result.strategy_name,
        "sharpe_ratio": result.sharpe_ratio,
        "total_return": result.total_return,
        "max_drawdown": result.max_drawdown,
        "win_rate": result.win_rate,
        "total_trades": result.total_trades
    }


@router.get("/diversity")
async def get_diversity_metrics():
    """Get diversity metrics showing how well the system explores across strategy types."""
    from slate_core.discovery.realistic_memory import get_realistic_discovery_memory
    import sqlite3

    memory = get_realistic_discovery_memory()

    # Query diversity from database
    conn = sqlite3.connect(memory.db_path)
    cursor = conn.cursor()

    try:
        # Get total count and type distribution
        cursor.execute("SELECT COUNT(*) FROM discovery_results")
        total_generated = cursor.fetchone()[0]

        cursor.execute("""
            SELECT strategy_type, COUNT(*) as count
            FROM discovery_results
            GROUP BY strategy_type
            ORDER BY count DESC
        """)
        type_counts = {row[0]: row[1] for row in cursor.fetchall()}

        # Calculate percentages
        type_percentages = {
            stype: (count / total_generated * 100) if total_generated > 0 else 0
            for stype, count in type_counts.items()
        }

        # Calculate balancedness score (how evenly distributed across 10 types)
        # Ideal is 10% per type, use coefficient of variation
        if type_counts:
            counts = list(type_counts.values())
            mean_count = sum(counts) / len(counts)
            std_count = (sum((c - mean_count) ** 2 for c in counts) / len(counts)) ** 0.5
            balancedness = 1 - (std_count / mean_count) if mean_count > 0 else 0
            balancedness = max(0, min(1, balancedness))  # Clamp to [0, 1]
        else:
            balancedness = 0

        # Count distinct types seen
        recent_diversity = len(type_counts)

        diversity = {
            'total_generated': total_generated,
            'balancedness': balancedness,
            'recent_diversity': recent_diversity,
            'type_percentages': type_percentages
        }

        return {
            "total_generated": total_generated,
            "balancedness_score": balancedness,
            "recent_diversity": recent_diversity,
            "type_distribution": type_percentages,
            "interpretation": _interpret_diversity(diversity)
        }

    finally:
        conn.close()


def _interpret_diversity(diversity: Dict) -> str:
    """Provide human-readable interpretation of diversity metrics."""
    balancedness = diversity.get('balancedness', 0)
    recent = diversity.get('recent_diversity', 0)
    total = diversity.get('total_generated', 0)

    if total < 50:
        return "Building initial diversity baseline..."
    elif balancedness > 0.8:
        return f"Excellent diversity across {recent}/10 types"
    elif balancedness > 0.6:
        return f"Good diversity across {recent}/10 types"
    elif balancedness > 0.4:
        return f"Moderate diversity - some types overrepresented"
    else:
        return "Poor diversity - need broader exploration"


@router.get("/database/info")
async def get_database_info():
    """Get database size and record count."""
    from .realistic_backtester import get_discovery_system
    system = get_discovery_system()

    if system.evolution.db_memory:
        return system.evolution.db_memory.get_database_size()
    else:
        return {"error": "Database not available"}


@router.post("/database/cleanup")
async def cleanup_database(max_records: int = 5000):
    """Clean up old discovery records to control database size.

    Args:
        max_records: Maximum number of records to keep (default 5000)
    """
    from .realistic_backtester import get_discovery_system
    system = get_discovery_system()

    if system.evolution.db_memory:
        system.evolution.db_memory.cleanup_old_records(max_records=max_records)
        return {"status": "cleaned", "max_records": max_records}
    else:
        return {"error": "Database not available"}


@router.get("/queue/status")
async def get_queue_status():
    """Get candidate queue status for self-evolution feedback loop."""
    try:
        from .candidate_queue import get_candidate_queue
        queue = get_candidate_queue()
        return queue.get_statistics()
    except Exception as e:
        logger.error(f"Failed to get queue status: {e}")
        return {"error": str(e), "queue_size": 0}


@router.get("/evolution/status")
async def get_evolution_status():
    """Get comprehensive evolution status including feedback loop."""
    try:
        from .candidate_queue import get_candidate_queue
        from .self_evolving import get_discovery_engine

        queue = get_candidate_queue()
        engine = get_discovery_engine()

        queue_stats = queue.get_statistics()
        engine_status = engine.get_status()

        return {
            "feedback_loop": {
                "queue": queue_stats,
                "self_evolving": engine_status,
                "integration_active": True,
                "flow_description": "Self-Evolving → Queue → Realistic Discovery → Database → Self-Evolving"
            },
            "summary": {
                "queued_candidates": queue_stats["queue_size"],
                "tested_evolved_candidates": queue_stats["total_tested"],
                "self_evolving_cycles": engine_status["total_completed"],
                "deployed_strategies": engine_status["deployed"],
                "feedback_loop_active": queue_stats["queue_size"] > 0 or queue_stats["total_tested"] > 0
            }
        }
    except Exception as e:
        logger.error(f"Failed to get evolution status: {e}")
        return {"error": str(e), "feedback_loop_active": False}


@router.get("/stigmergic/stats")
async def get_stigmergic_stats():
    """Get stigmergic coordination statistics."""
    try:
        from .stigmergic_coordinator import get_stigmergic_coordinator
        coordinator = get_stigmergic_coordinator()
        return coordinator.get_coordination_stats()
    except Exception as e:
        logger.error(f"Failed to get stigmergic stats: {e}")
        return {"error": str(e), "stigmergic_active": False}


@router.get("/stigmergic/priorities")
async def get_stigmergic_priorities():
    """Get current dynamic priorities for each strategy type."""
    try:
        from .stigmergic_coordinator import get_stigmergic_coordinator
        coordinator = get_stigmergic_coordinator()
        coordinator.update_dynamic_priorities()
        return {
            "priorities": coordinator.strategy_priorities,
            "specializations": coordinator.emergent_specializations,
            "last_updated": coordinator.last_specialization_update
        }
    except Exception as e:
        logger.error(f"Failed to get stigmergic priorities: {e}")
        return {"error": str(e)}


@router.get("/stigmergic/pheromones")
async def get_pheromone_trails(hours: int = 1, limit: int = 20):
    """Get recent pheromone trails (success signals) from the environment.

    Args:
        hours: Number of hours to look back (default 1)
        limit: Maximum number of trails to return (default 20)
    """
    try:
        from .stigmergic_coordinator import get_stigmergic_coordinator
        coordinator = get_stigmergic_coordinator()
        trails = coordinator.get_pheromone_trails(hours=hours, limit=limit)

        return {
            "trails": [
                {
                    "strategy_type": t.strategy_type,
                    "signal_strength": t.signal_strength,
                    "timestamp": t.timestamp,
                    "discovered_by": t.discovered_by,
                    "metadata": t.metadata
                }
                for t in trails
            ],
            "hours": hours,
            "count": len(trails)
        }
    except Exception as e:
        logger.error(f"Failed to get pheromone trails: {e}")
        return {"error": str(e), "trails": []}
