#!/usr/bin/env python3
"""
SLATE Perpetual Futures Database Manager - CORRECTED VERSION

Fixed to match exactly 47 fields from PerpetualBacktestResult + rank_score.
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class PerpetualDatabaseManager:
    """Manage perpetual futures backtesting results database."""

    def __init__(self, db_path: str = "slate_core/slate_realistic_discoveries.db"):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize perpetual futures database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create perpetual futures discoveries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS perpetual_discoveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- Strategy identification
                strategy_name TEXT NOT NULL,
                strategy_description TEXT NOT NULL,
                edge_type TEXT NOT NULL,

                -- PRIMARY METRICS: USDT Profit (brutally realistic)
                total_profit_usdt REAL NOT NULL,
                total_return_pct REAL NOT NULL,
                final_capital REAL NOT NULL,
                initial_capital REAL NOT NULL,

                -- Baseline comparison (buy-hold for perpetuals)
                buy_hold_profit_usdt REAL NOT NULL,
                buy_hold_return_pct REAL NOT NULL,
                vs_buy_hold_usdt REAL NOT NULL,
                beat_market INTEGER NOT NULL,

                -- Risk metrics
                max_drawdown_pct REAL NOT NULL,
                max_drawdown_usdt REAL NOT NULL,
                sharpe_ratio REAL NOT NULL,
                sortino_ratio REAL,
                calmar_ratio REAL,

                -- Trading statistics
                total_trades INTEGER NOT NULL,
                winning_trades INTEGER NOT NULL,
                losing_trades INTEGER NOT NULL,
                win_rate REAL NOT NULL,
                profit_factor REAL,
                avg_trade_pnl_usdt REAL,
                avg_win_usdt REAL,
                avg_loss_usdt REAL,
                largest_win_usdt REAL,
                largest_loss_usdt REAL,

                -- Perpetual-specific metrics (CRITICAL)
                total_funding_paid_usdt REAL NOT NULL,
                total_funding_received_usdt REAL NOT NULL,
                net_funding_usdt REAL NOT NULL,
                avg_funding_daily_usdt REAL NOT NULL,

                -- Cost breakdown (transparency)
                total_fees_usdt REAL NOT NULL,
                total_slippage_usdt REAL NOT NULL,
                total_transaction_costs_usdt REAL NOT NULL,

                -- Realism metrics
                avg_slippage_bps REAL,
                avg_fill_rate REAL,
                total_signals INTEGER NOT NULL,
                filled_signals INTEGER NOT NULL,
                partial_fills INTEGER NOT NULL,

                -- Market data
                period_start TEXT NOT NULL,
                period_end TEXT NOT NULL,
                start_price REAL NOT NULL,
                end_price REAL NOT NULL,
                volatility_regime TEXT,
                timeframe TEXT NOT NULL,

                -- Validation
                passed_validation INTEGER NOT NULL,
                validation_failures TEXT,

                -- Ranking
                rank_score REAL,
                timestamp TEXT NOT NULL,

                UNIQUE(strategy_name, period_start, period_end)
            )
        """)

        # Create indexes for performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_perpetual_profit
            ON perpetual_discoveries(total_profit_usdt DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_perpetual_validation
            ON perpetual_discoveries(passed_validation, total_profit_usdt DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_perpetual_beat_market
            ON perpetual_discoveries(beat_market, total_profit_usdt DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_perpetual_edge_type
            ON perpetual_discoveries(edge_type, total_profit_usdt DESC)
        """)

        conn.commit()
        conn.close()

        logger.info("Perpetual futures database initialized with brutal realism schema")

    def save_discovery(self, result: Dict[str, Any]) -> bool:
        """Save perpetual futures backtest result to database."""
        try:
            # DEBUG: Log input values with full context
            import traceback
            logger.info(f"🔍 save_discovery called with:")
            logger.info(f"   strategy_name: {result.get('strategy_name')}")
            logger.info(f"   total_trades: {result.get('total_trades')}")
            logger.info(f"   sharpe_ratio: {result.get('sharpe_ratio')}")
            logger.info(f"   total_profit_usdt: {result.get('total_profit_usdt')}")
            logger.info(f"   win_rate: {result.get('win_rate')}")
            logger.info(f"   Call stack:")
            for line in traceback.format_stack()[-4:]:
                logger.info(f"     {line.strip()}")

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # CRITICAL DEBUG: Check if entry already exists before save
            cursor.execute("SELECT timestamp, total_trades, sharpe_ratio, total_profit_usdt FROM perpetual_discoveries WHERE strategy_name = ? AND period_start = ? AND period_end = ?", (result['strategy_name'], result.get('period_start', '2025-11-01'), result.get('period_end', '2026-07-01')))
            existing = cursor.fetchone()
            if existing:
                logger.info(f"⚠️ Existing entry found: timestamp={existing[0]}, trades={existing[1]}, sharpe={existing[2]}, profit={existing[3]}")

            # Calculate rank score (USDT profit is PRIMARY, accounting for costs)
            rank_score = (
                result['total_profit_usdt'] * 1.0 -  # Actual USDT profit after ALL costs
                result['max_drawdown_usdt'] * 0.5 +   # Penalize drawdown
                (result['vs_buy_hold_usdt'] if result['beat_market'] else 0) * 0.3  # Bonus for beating market
            )

            # CORRECTED: Exactly 48 parameters to match database columns (excluding id)
            cursor.execute("""
                INSERT OR REPLACE INTO perpetual_discoveries (
                    strategy_name, strategy_description, edge_type,
                    total_profit_usdt, total_return_pct, final_capital, initial_capital,
                    buy_hold_profit_usdt, buy_hold_return_pct, vs_buy_hold_usdt, beat_market,
                    max_drawdown_pct, max_drawdown_usdt, sharpe_ratio, sortino_ratio, calmar_ratio,
                    total_trades, winning_trades, losing_trades, win_rate, profit_factor,
                    avg_trade_pnl_usdt, avg_win_usdt, avg_loss_usdt, largest_win_usdt, largest_loss_usdt,
                    total_funding_paid_usdt, total_funding_received_usdt, net_funding_usdt, avg_funding_daily_usdt,
                    total_fees_usdt, total_slippage_usdt, total_transaction_costs_usdt,
                    avg_slippage_bps, avg_fill_rate, total_signals, filled_signals, partial_fills,
                    period_start, period_end, start_price, end_price, volatility_regime, timeframe,
                    passed_validation, validation_failures, rank_score, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result['strategy_name'], result['strategy_description'], result['edge_type'],
                result['total_profit_usdt'], result['total_return_pct'], result['final_capital'], result['initial_capital'],
                result['buy_hold_profit_usdt'], result['buy_hold_return_pct'], result['vs_buy_hold_usdt'], int(result['beat_market']),
                result['max_drawdown_pct'], result['max_drawdown_usdt'], result['sharpe_ratio'],
                result.get('sortino_ratio', 0), result.get('calmar_ratio', 0),
                int(result['total_trades']), int(result['winning_trades']), int(result['losing_trades']),
                result['win_rate'], result.get('profit_factor', 0),
                result.get('avg_trade_pnl_usdt', 0), result.get('avg_win_usdt', 0), result.get('avg_loss_usdt', 0),
                result.get('largest_win_usdt', 0), result.get('largest_loss_usdt', 0),
                result['total_funding_paid_usdt'], result['total_funding_received_usdt'],
                result['net_funding_usdt'], result['avg_funding_daily_usdt'],
                result['total_fees_usdt'], result['total_slippage_usdt'], result['total_transaction_costs_usdt'],
                result.get('avg_slippage_bps', 0), result.get('avg_fill_rate', 0),
                int(result['total_signals']), int(result['filled_signals']), int(result['partial_fills']),
                result['period_start'], result['period_end'], result['start_price'], result['end_price'],
                result.get('volatility_regime', 'unknown'), result['timeframe'],
                int(result['passed_validation']), json.dumps(result.get('validation_failures', [])),
                rank_score, result['timestamp']
            ))

            # CRITICAL DEBUG: Log before commit
            logger.info(f"🔍 Before commit: {result['strategy_name']} with timestamp {result['timestamp']}")

            # DEBUG: Log SQL execution
            logger.info(f"🔍 SQL executed for {result['strategy_name']}")
            logger.info(f"   Parameters bound: total_trades={int(result['total_trades'])}, sharpe={result['sharpe_ratio']:.6f}, profit={result['total_profit_usdt']:.2f}")
            logger.info(f"   Timestamp used: {result['timestamp']}")

            # CRITICAL DEBUG: Check commit status
            logger.info(f"🔍 About to commit transaction for {result['strategy_name']}")
            conn.commit()
            logger.info(f"✅ Transaction committed successfully")
            conn.close()
            logger.info(f"✅ Database connection closed")

            # Verify save by reading back
            import os
            logger.info(f"   🔍 Database path: {self.db_path}")
            logger.info(f"   🔍 Absolute path: {os.path.abspath(self.db_path)}")
            logger.info(f"   🔍 Working dir: {os.getcwd()}")

            # CRITICAL FIX: Use the exact timestamp to verify the specific row we just inserted
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT total_trades, sharpe_ratio, total_profit_usdt FROM perpetual_discoveries WHERE strategy_name = ? AND timestamp = ?", (result['strategy_name'], result['timestamp']))
            saved_values = cursor.fetchone()
            conn.close()

            logger.info(f"   Verification from DB: total_trades={saved_values[0] if saved_values else 'NOT_FOUND'}, sharpe={saved_values[1] if saved_values and len(saved_values) > 1 else 'NOT_FOUND'}, profit={saved_values[2] if saved_values and len(saved_values) > 2 else 'NOT_FOUND'}")

            # CRITICAL: Second verification from FRESH connection to ensure data is actually persisted
            import time
            time.sleep(0.1)  # Small delay to ensure flush to disk
            fresh_conn = sqlite3.connect(self.db_path)
            fresh_cursor = fresh_conn.cursor()
            fresh_cursor.execute("SELECT total_trades, sharpe_ratio, total_profit_usdt FROM perpetual_discoveries WHERE strategy_name = ? AND timestamp = ?", (result['strategy_name'], result['timestamp']))
            fresh_values = fresh_cursor.fetchone()
            fresh_conn.close()
            logger.info(f"   🔍 FRESH connection verification: total_trades={fresh_values[0] if fresh_values else 'NOT_FOUND'}, sharpe={fresh_values[1] if fresh_values and len(fresh_values) > 1 else 'NOT_FOUND'}, profit={fresh_values[2] if fresh_values and len(fresh_values) > 2 else 'NOT_FOUND'}")

            logger.info(f"✓ Saved perpetual discovery: {result['strategy_name']} | Profit: ${result['total_profit_usdt']:.2f} | Costs: ${result['total_transaction_costs_usdt']:.2f}")
            return True

        except Exception as e:
            logger.error(f"Failed to save perpetual discovery: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def get_top_strategies(self, limit: int = 10, min_profit: float = 0) -> List[Dict[str, Any]]:
        """Get top performing perpetual futures strategies."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM perpetual_discoveries
                WHERE passed_validation = 1 AND total_profit_usdt >= ?
                ORDER BY total_profit_usdt DESC
                LIMIT ?
            """, (min_profit, limit))

            columns = [desc[0] for desc in cursor.description]
            results = []

            for row in cursor.fetchall():
                result = dict(zip(columns, row))
                result['validation_failures'] = json.loads(result['validation_failures'])
                results.append(result)

            conn.close()
            return results

        except Exception as e:
            logger.error(f"Failed to get top strategies: {e}")
            return []

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall perpetual futures discovery statistics."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Total discoveries
            cursor.execute("SELECT COUNT(*) FROM perpetual_discoveries")
            total = cursor.fetchone()[0]

            # Profitable strategies
            cursor.execute("SELECT COUNT(*) FROM perpetual_discoveries WHERE total_profit_usdt > 0")
            profitable = cursor.fetchone()[0]

            # Passed validation
            cursor.execute("SELECT COUNT(*) FROM perpetual_discoveries WHERE passed_validation = 1")
            passed = cursor.fetchone()[0]

            # Beat market
            cursor.execute("SELECT COUNT(*) FROM perpetual_discoveries WHERE beat_market = 1")
            beat_market = cursor.fetchone()[0]

            # Average metrics
            cursor.execute("""
                SELECT
                    AVG(total_profit_usdt),
                    AVG(max_drawdown_pct),
                    AVG(sharpe_ratio),
                    AVG(total_transaction_costs_usdt),
                    AVG(net_funding_usdt)
                FROM perpetual_discoveries
            """)
            avg_metrics = cursor.fetchone()

            # Total costs breakdown
            cursor.execute("""
                SELECT
                    SUM(total_fees_usdt),
                    SUM(total_slippage_usdt),
                    SUM(total_funding_paid_usdt),
                    SUM(total_funding_received_usdt)
                FROM perpetual_discoveries
            """)
            total_costs = cursor.fetchone()

            conn.close()

            return {
                'total_discoveries': total,
                'profitable_strategies': profitable,
                'passed_validation': passed,
                'beat_market': beat_market,
                'success_rate': profitable / total if total > 0 else 0,
                'avg_profit_usdt': avg_metrics[0] or 0,
                'avg_drawdown_pct': avg_metrics[1] or 0,
                'avg_sharpe': avg_metrics[2] or 0,
                'avg_transaction_costs': avg_metrics[3] or 0,
                'avg_net_funding': avg_metrics[4] or 0,
                'total_fees_usdt': total_costs[0] or 0,
                'total_slippage_usdt': total_costs[1] or 0,
                'total_funding_paid': total_costs[2] or 0,
                'total_funding_received': total_costs[3] or 0
            }

        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}


if __name__ == "__main__":
    # Test the database manager
    print("Testing Perpetual Database Manager...")

    db_manager = PerpetualDatabaseManager()

    stats = db_manager.get_statistics()
    print(f"\n📊 Perpetual Futures Database Statistics:")
    print(f"  Total Discoveries: {stats.get('total_discoveries', 0)}")
    print(f"  Profitable Strategies: {stats.get('profitable_strategies', 0)}")
    print(f"  Passed Validation: {stats.get('passed_validation', 0)}")
    print(f"  Beat Market: {stats.get('beat_market', 0)}")
    print(f"  Success Rate: {stats.get('success_rate', 0):.2%}")

    print("\n✓ Perpetual Database Manager initialized successfully")