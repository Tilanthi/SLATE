#!/usr/bin/env python3
"""
Generate formatted table of top 20 SLATE strategies
"""

import sqlite3
import sys
from pathlib import Path

# Add SLATE to path
sys.path.insert(0, str(Path(__file__).parent))

def get_top_strategies():
    """Query top 20 strategies from database."""
    db_path = "slate_core/slate_realistic_discoveries.db"

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    query = """
    SELECT
        edge_type,
        edge_description,
        timeframe,
        ROUND(total_return_pct * 100, 2) as return_pct,
        ROUND(sharpe_ratio, 2) as sharpe,
        ROUND(max_drawdown_pct * 100, 2) as max_dd_pct,
        ROUND(win_rate * 100, 1) as win_rate,
        total_trades,
        beat_market,
        passed_validation
    FROM edge_discoveries
    WHERE passed_validation = 1
    ORDER BY rank_score DESC
    LIMIT 20
    """

    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()

    return results

def format_table():
    """Create formatted table with borders."""
    results = get_top_strategies()

    print("=" * 180)
    print(" " * 78 + "TOP 20 SLATE DISCOVERED STRATEGIES - WITH REALISTIC TRANSACTION COSTS" + " " * 78)
    print("=" * 180)
    print()

    # Header
    print("┌" + "─" * 178 + "┐")
    print("│ " + "RANK".ljust(6) + " │ " + "STRATEGY TYPE".ljust(30) + " │ " + "DESCRIPTION".ljust(55) + " │ " + "TIMEFRAME".ljust(10) + " │ " + "RETURN".ljust(8) + " │ " + "SHARPE".ljust(8) + " │ " + "MAX DD".ljust(8) + " │ " + "WIN RATE".ljust(10) + " │ " + "TRADES".ljust(8) + " │")
    print("├" + "─" * 178 + "┤")

    for i, row in enumerate(results, 1):
        edge_type, description, timeframe, return_pct, sharpe, max_dd, win_rate, trades, beat_market, passed = row

        # Truncate description if too long
        if len(description) > 53:
            description = description[:50] + "..."

        # Format values
        return_str = f"{return_pct:.2f}%"
        sharpe_str = f"{sharpe:.2f}"
        max_dd_str = f"{max_dd:.2f}%"
        win_rate_str = f"{win_rate:.1f}%"
        trades_str = str(trades)

        print("│ " + str(i).ljust(6) + " │ " + edge_type.ljust(30) + " │ " + description.ljust(55) + " │ " + timeframe.ljust(10) + " │ " + return_str.ljust(8) + " │ " + sharpe_str.ljust(8) + " │ " + max_dd_str.ljust(8) + " │ " + win_rate_str.ljust(10) + " │ " + trades_str.ljust(8) + " │")

    print("└" + "─" * 178 + "┘")
    print()

    # Summary statistics
    print("📊 PERFORMANCE SUMMARY:")
    print(f"   • Average Return: {sum(r[3] for r in results) / 20:.2f}%")
    print(f"   • Average Sharpe: {sum(r[4] for r in results) / 20:.2f}")
    print(f"   • Average Max DD: {sum(r[5] for r in results) / 20:.2f}%")
    print(f"   • Average Win Rate: {sum(r[6] for r in results) / 20:.1f}%")
    print(f"   • All Beat Buy & Hold: {'✅' if all(r[7] for r in results) else '❌'}")
    print(f"   • All Passed Validation: {'✅' if all(r[9] for r in results) else '❌'}")
    print()

    # Strategy type breakdown
    print("🔍 STRATEGY TYPE BREAKDOWN:")
    type_counts = {}
    for row in results:
        edge_type = row[0]
        type_counts[edge_type] = type_counts.get(edge_type, 0) + 1

    for edge_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / 20) * 100
        print(f"   • {edge_type}: {count} strategies ({percentage:.0f}%)")
    print()

if __name__ == "__main__":
    format_table()
