#!/usr/bin/env python3
"""
SLATE Automated Profitability Reporter

Automatically generates comprehensive profitability analysis reports
based on the discovery database, similar to the manual 52,268 strategy analysis.

Key features:
- Timeframe success rate analysis
- Trading frequency impact analysis
- Drawdown correlation analysis
- Transaction cost impact analysis
- Strategy type performance breakdown
- Automated recommendations generation

Run weekly/monthly to track system performance and optimization effectiveness.
"""

import sqlite3
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import json

logger = logging.getLogger(__name__)


@dataclass
class ProfitabilityMetrics:
    """Key profitability metrics for analysis."""
    total_strategies: int
    profitable_strategies: int
    unprofitable_strategies: int
    success_rate: float
    avg_profit_per_strategy: float
    avg_trades_profitable: float
    avg_trades_unprofitable: float
    avg_drawdown_profitable: float
    avg_drawdown_unprofitable: float
    avg_win_rate_profitable: float
    avg_win_rate_unprofitable: float
    avg_fees_profitable: float
    avg_fees_unprofitable: float


@dataclass
class TimeframeAnalysis:
    """Analysis results for a specific timeframe."""
    timeframe: str
    total_count: int
    profitable_count: int
    success_rate: float
    avg_profit: float
    avg_trades: float
    avg_fees: float
    avg_drawdown: float
    avg_win_rate: float


@dataclass
class StrategyTypeAnalysis:
    """Analysis results for a specific strategy type."""
    strategy_type: str
    total_count: int
    profitable_count: int
    success_rate: float
    avg_profit: float


class ProfitabilityReporter:
    """
    Automated profitability analysis and reporting system.

    Generates comprehensive reports similar to the manual 52,268 strategy
    analysis, but automated for regular monitoring.
    """

    def __init__(self, db_path: str = "slate_core/slate_realistic_discoveries.db"):
        """Initialize profitability reporter with database connection."""
        self.db_path = db_path
        self.conn = None
        logger.info(f"ProfitabilityReporter initialized with database: {db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        return self.conn

    def generate_comprehensive_report(self, output_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate comprehensive profitability analysis report.

        Args:
            output_dir: Optional directory to save report files

        Returns:
            Dictionary with complete analysis results
        """
        logger.info("Generating comprehensive profitability report...")
        start_time = datetime.now()

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 1. Overall metrics
            overall_metrics = self._analyze_overall_metrics(cursor)

            # 2. Timeframe analysis
            timeframe_analysis = self._analyze_timeframes(cursor)

            # 3. Strategy type analysis
            strategy_type_analysis = self._analyze_strategy_types(cursor)

            # 4. Trading frequency impact
            frequency_impact = self._analyze_trading_frequency_impact(cursor)

            # 5. Drawdown impact analysis
            drawdown_impact = self._analyze_drawdown_impact(cursor)

            # 6. Transaction cost impact
            cost_impact = self._analyze_transaction_cost_impact(cursor)

            # 7. Generate recommendations
            recommendations = self._generate_recommendations(
                overall_metrics, timeframe_analysis, frequency_impact,
                drawdown_impact, cost_impact
            )

            # Compile report
            report = {
                'generated_at': datetime.now().isoformat(),
                'analysis_period_days': self._get_analysis_period(cursor),
                'overall_metrics': overall_metrics,
                'timeframe_analysis': timeframe_analysis,
                'strategy_type_analysis': strategy_type_analysis,
                'frequency_impact': frequency_impact,
                'drawdown_impact': drawdown_impact,
                'cost_impact': cost_impact,
                'recommendations': recommendations,
                'generation_time_seconds': (datetime.now() - start_time).total_seconds()
            }

            # Save report if output directory provided
            if output_dir:
                self._save_report(report, output_dir)

            logger.info(f"Report generated successfully in {report['generation_time_seconds']:.1f}s")
            return report

        except Exception as e:
            logger.error(f"Error generating report: {e}")
            raise

    def _analyze_overall_metrics(self, cursor) -> ProfitabilityMetrics:
        """Analyze overall profitability metrics."""
        cursor.execute("""
            SELECT
                COUNT(*) as total_strategies,
                SUM(CASE WHEN passed_validation = 1 THEN 1 ELSE 0 END) as profitable_strategies,
                SUM(CASE WHEN passed_validation = 0 OR passed_validation IS NULL THEN 1 ELSE 0 END) as unprofitable_strategies,
                AVG(total_profit_usdt) as avg_profit,
                AVG(total_trades) as avg_trades,
                AVG(max_drawdown_pct) as avg_drawdown,
                AVG(win_rate) as avg_win_rate,
                AVG(total_fees_usdt) as avg_fees
            FROM edge_discoveries
            WHERE total_profit_usdt IS NOT NULL
        """)

        row = cursor.fetchone()
        total = row['total_strategies']
        profitable = row['profitable_strategies']
        unprofitable = row['unprofitable_strategies']
        success_rate = (profitable / total * 100) if total > 0 else 0

        # Get separate metrics for profitable vs unprofitable
        cursor.execute("""
            SELECT
                AVG(total_trades) as avg_trades,
                AVG(max_drawdown_pct) as avg_drawdown,
                AVG(win_rate) as avg_win_rate,
                AVG(total_fees_usdt) as avg_fees
            FROM edge_discoveries
            WHERE passed_validation = 1 AND total_profit_usdt IS NOT NULL
        """)
        profitable_row = cursor.fetchone()

        cursor.execute("""
            SELECT
                AVG(total_trades) as avg_trades,
                AVG(max_drawdown_pct) as avg_drawdown,
                AVG(win_rate) as avg_win_rate,
                AVG(total_fees_usdt) as avg_fees
            FROM edge_discoveries
            WHERE (passed_validation = 0 OR passed_validation IS NULL) AND total_profit_usdt IS NOT NULL
        """)
        unprofitable_row = cursor.fetchone()

        return ProfitabilityMetrics(
            total_strategies=total,
            profitable_strategies=profitable,
            unprofitable_strategies=unprofitable,
            success_rate=success_rate,
            avg_profit_per_strategy=row['avg_profit'] or 0,
            avg_trades_profitable=profitable_row['avg_trades'] or 0,
            avg_trades_unprofitable=unprofitable_row['avg_trades'] or 0,
            avg_drawdown_profitable=profitable_row['avg_drawdown'] or 0,
            avg_drawdown_unprofitable=unprofitable_row['avg_drawdown'] or 0,
            avg_win_rate_profitable=profitable_row['avg_win_rate'] or 0,
            avg_win_rate_unprofitable=unprofitable_row['avg_win_rate'] or 0,
            avg_fees_profitable=profitable_row['avg_fees'] or 0,
            avg_fees_unprofitable=unprofitable_row['avg_fees'] or 0
        )

    def _analyze_timeframes(self, cursor) -> List[TimeframeAnalysis]:
        """Analyze profitability by timeframe."""
        cursor.execute("""
            SELECT
                CASE
                    WHEN edge_description LIKE '%[1d]%' THEN '1d'
                    WHEN edge_description LIKE '%[12h]%' THEN '12h'
                    WHEN edge_description LIKE '%[8h]%' THEN '8h'
                    WHEN edge_description LIKE '%[4h]%' THEN '4h'
                    WHEN edge_description LIKE '%[1h]%' THEN '1h'
                    WHEN edge_description LIKE '%[30m]%' THEN '30m'
                    WHEN edge_description LIKE '%[15m]%' THEN '15m'
                    WHEN edge_description LIKE '%[5m]%' THEN '5m'
                    WHEN edge_description LIKE '%[1m]%' THEN '1m'
                    ELSE 'unknown'
                END as timeframe,
                COUNT(*) as total_count,
                SUM(CASE WHEN passed_validation = 1 THEN 1 ELSE 0 END) as profitable_count,
                AVG(total_profit_usdt) as avg_profit,
                AVG(total_trades) as avg_trades,
                AVG(total_fees_usdt) as avg_fees,
                AVG(max_drawdown_pct) as avg_drawdown,
                AVG(win_rate) as avg_win_rate
            FROM edge_discoveries
            WHERE edge_description IS NOT NULL AND total_profit_usdt IS NOT NULL
            GROUP BY timeframe
            ORDER BY
                CASE timeframe
                    WHEN '1d' THEN 1
                    WHEN '12h' THEN 2
                    WHEN '8h' THEN 3
                    WHEN '4h' THEN 4
                    WHEN '1h' THEN 5
                    WHEN '30m' THEN 6
                    WHEN '15m' THEN 7
                    WHEN '5m' THEN 8
                    WHEN '1m' THEN 9
                    ELSE 10
                END
        """)

        results = []
        for row in cursor.fetchall():
            if row['timeframe'] != 'unknown':
                total = row['total_count']
                profitable = row['profitable_count']
                success_rate = (profitable / total * 100) if total > 0 else 0

                results.append(TimeframeAnalysis(
                    timeframe=row['timeframe'],
                    total_count=total,
                    profitable_count=profitable,
                    success_rate=success_rate,
                    avg_profit=row['avg_profit'] or 0,
                    avg_trades=row['avg_trades'] or 0,
                    avg_fees=row['avg_fees'] or 0,
                    avg_drawdown=row['avg_drawdown'] or 0,
                    avg_win_rate=row['avg_win_rate'] or 0
                ))

        return results

    def _analyze_strategy_types(self, cursor) -> List[StrategyTypeAnalysis]:
        """Analyze profitability by strategy type."""
        cursor.execute("""
            SELECT
                CASE
                    WHEN edge_description LIKE '%momentum%' OR edge_description LIKE '%mean reversion%' THEN 'momentum_mean_reversion'
                    WHEN edge_description LIKE '%time pattern%' OR edge_description LIKE '%seasonal%' THEN 'time_pattern'
                    WHEN edge_description LIKE '%correlation%' OR edge_description LIKE '%arbitrage%' THEN 'correlation_arbitrage'
                    WHEN edge_description LIKE '%microstructure%' OR edge_description LIKE '%order book%' THEN 'market_microstructure'
                    WHEN edge_description LIKE '%volatility%' OR edge_description LIKE '%regime%' THEN 'volatility_regime'
                    ELSE 'other'
                END as strategy_type,
                COUNT(*) as total_count,
                SUM(CASE WHEN passed_validation = 1 THEN 1 ELSE 0 END) as profitable_count,
                AVG(total_profit_usdt) as avg_profit
            FROM edge_discoveries
            WHERE edge_description IS NOT NULL AND total_profit_usdt IS NOT NULL
            GROUP BY strategy_type
            ORDER BY profitable_count DESC
        """)

        results = []
        for row in cursor.fetchall():
            if row['strategy_type'] != 'other':
                total = row['total_count']
                profitable = row['profitable_count']
                success_rate = (profitable / total * 100) if total > 0 else 0

                results.append(StrategyTypeAnalysis(
                    strategy_type=row['strategy_type'],
                    total_count=total,
                    profitable_count=profitable,
                    success_rate=success_rate,
                    avg_profit=row['avg_profit'] or 0
                ))

        return results

    def _analyze_trading_frequency_impact(self, cursor) -> Dict[str, Any]:
        """Analyze how trading frequency impacts profitability."""
        cursor.execute("""
            SELECT
                CASE
                    WHEN total_trades < 100 THEN 'low_frequency'
                    WHEN total_trades < 500 THEN 'medium_frequency'
                    WHEN total_trades < 1000 THEN 'high_frequency'
                    ELSE 'excessive_frequency'
                END as frequency_category,
                COUNT(*) as total_count,
                SUM(CASE WHEN passed_validation = 1 THEN 1 ELSE 0 END) as profitable_count,
                AVG(total_profit_usdt) as avg_profit,
                AVG(total_fees_usdt) as avg_fees,
                AVG(total_trades) as avg_trades
            FROM edge_discoveries
            WHERE total_trades IS NOT NULL AND total_profit_usdt IS NOT NULL
            GROUP BY frequency_category
            ORDER BY
                CASE frequency_category
                    WHEN 'low_frequency' THEN 1
                    WHEN 'medium_frequency' THEN 2
                    WHEN 'high_frequency' THEN 3
                    ELSE 4
                END
        """)

        results = {}
        for row in cursor.fetchall():
            category = row['frequency_category']
            total = row['total_count']
            profitable = row['profitable_count']
            success_rate = (profitable / total * 100) if total > 0 else 0

            results[category] = {
                'total_count': total,
                'profitable_count': profitable,
                'success_rate': success_rate,
                'avg_profit': row['avg_profit'] or 0,
                'avg_fees': row['avg_fees'] or 0,
                'avg_trades': row['avg_trades'] or 0
            }

        return results

    def _analyze_drawdown_impact(self, cursor) -> Dict[str, Any]:
        """Analyze how drawdown impacts profitability."""
        cursor.execute("""
            SELECT
                CASE
                    WHEN ABS(max_drawdown_pct) < 2 THEN 'tight_control'
                    WHEN ABS(max_drawdown_pct) < 5 THEN 'moderate_control'
                    WHEN ABS(max_drawdown_pct) < 10 THEN 'loose_control'
                    ELSE 'poor_control'
                END as drawdown_category,
                COUNT(*) as total_count,
                SUM(CASE WHEN passed_validation = 1 THEN 1 ELSE 0 END) as profitable_count,
                AVG(total_profit_usdt) as avg_profit,
                AVG(ABS(max_drawdown_pct)) as avg_drawdown
            FROM edge_discoveries
            WHERE max_drawdown_pct IS NOT NULL AND total_profit_usdt IS NOT NULL
            GROUP BY drawdown_category
            ORDER BY
                CASE drawdown_category
                    WHEN 'tight_control' THEN 1
                    WHEN 'moderate_control' THEN 2
                    WHEN 'loose_control' THEN 3
                    ELSE 4
                END
        """)

        results = {}
        for row in cursor.fetchall():
            category = row['drawdown_category']
            total = row['total_count']
            profitable = row['profitable_count']
            success_rate = (profitable / total * 100) if total > 0 else 0

            results[category] = {
                'total_count': total,
                'profitable_count': profitable,
                'success_rate': success_rate,
                'avg_profit': row['avg_profit'] or 0,
                'avg_drawdown': row['avg_drawdown'] or 0
            }

        return results

    def _analyze_transaction_cost_impact(self, cursor) -> Dict[str, Any]:
        """Analyze how transaction costs impact profitability."""
        cursor.execute("""
            SELECT
                CASE
                    WHEN total_fees_usdt < 50 THEN 'low_costs'
                    WHEN total_fees_usdt < 200 THEN 'moderate_costs'
                    WHEN total_fees_usdt < 500 THEN 'high_costs'
                    ELSE 'excessive_costs'
                END as cost_category,
                COUNT(*) as total_count,
                SUM(CASE WHEN passed_validation = 1 THEN 1 ELSE 0 END) as profitable_count,
                AVG(total_profit_usdt) as avg_profit,
                AVG(total_fees_usdt) as avg_fees,
                AVG(total_trades) as avg_trades
            FROM edge_discoveries
            WHERE total_fees_usdt IS NOT NULL AND total_profit_usdt IS NOT NULL
            GROUP BY cost_category
            ORDER BY
                CASE cost_category
                    WHEN 'low_costs' THEN 1
                    WHEN 'moderate_costs' THEN 2
                    WHEN 'high_costs' THEN 3
                    ELSE 4
                END
        """)

        results = {}
        for row in cursor.fetchall():
            category = row['cost_category']
            total = row['total_count']
            profitable = row['profitable_count']
            success_rate = (profitable / total * 100) if total > 0 else 0

            results[category] = {
                'total_count': total,
                'profitable_count': profitable,
                'success_rate': success_rate,
                'avg_profit': row['avg_profit'] or 0,
                'avg_fees': row['avg_fees'] or 0,
                'avg_trades': row['avg_trades'] or 0
            }

        return results

    def _generate_recommendations(self, overall_metrics, timeframe_analysis,
                                 frequency_impact, drawdown_impact, cost_impact) -> List[str]:
        """Generate actionable recommendations based on analysis."""
        recommendations = []

        # Timeframe recommendations
        daily_tf = next((tf for tf in timeframe_analysis if tf.timeframe == '1d'), None)
        if daily_tf and daily_tf.success_rate > 5.0:
            daily_profitable_pct = (daily_tf.profitable_count / overall_metrics.profitable_strategies * 100) if overall_metrics.profitable_strategies > 0 else 0
            recommendations.append(
                f"✓ Daily timeframes dominate profitability: {daily_profitable_pct:.1f}% of profitable strategies"
            )

        # Trading frequency recommendations
        excessive_freq = frequency_impact.get('excessive_frequency', {})
        if excessive_freq.get('total_count', 0) > 0:
            excessive_success_rate = excessive_freq.get('success_rate', 0)
            if excessive_success_rate < 1.0:
                recommendations.append(
                    f"❌ Excessive trading frequency (>1000 trades) has {excessive_success_rate:.1f}% success rate - REJECT"
                )

        # Drawdown recommendations
        poor_control = drawdown_impact.get('poor_control', {})
        if poor_control.get('total_count', 0) > 0:
            poor_success_rate = poor_control.get('success_rate', 0)
            if poor_success_rate < 1.0:
                recommendations.append(
                    f"❌ Poor drawdown control (>10%) has {poor_success_rate:.1f}% success rate - REJECT"
                )

        # Cost recommendations
        excessive_costs = cost_impact.get('excessive_costs', {})
        if excessive_costs.get('total_count', 0) > 0:
            excessive_success_rate = excessive_costs.get('success_rate', 0)
            if excessive_success_rate < 1.0:
                recommendations.append(
                    f"❌ Excessive transaction costs (>$500) has {excessive_success_rate:.1f}% success rate - REJECT"
                )

        # Overall success rate
        if overall_metrics.success_rate < 5.0:
            recommendations.append(
                f"⚠️ Low overall success rate ({overall_metrics.success_rate:.1f}%) - consider tightening validation criteria"
            )

        return recommendations

    def _get_analysis_period(self, cursor) -> int:
        """Get the time period covered by the analysis in days."""
        cursor.execute("""
            SELECT
                MIN(timestamp) as first_discovery,
                MAX(timestamp) as last_discovery
            FROM edge_discoveries
            WHERE timestamp IS NOT NULL
        """)

        row = cursor.fetchone()
        if row['first_discovery'] and row['last_discovery']:
            first = datetime.fromisoformat(row['first_discovery'])
            last = datetime.fromisoformat(row['last_discovery'])
            return (last - first).days
        return 0

    def _save_report(self, report: Dict[str, Any], output_dir: str):
        """Save report to files."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Save JSON report
        json_file = output_path / f'profitability_report_{timestamp}.json'
        with open(json_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        # Save markdown report
        md_file = output_path / f'profitability_report_{timestamp}.md'
        with open(md_file, 'w') as f:
            self._write_markdown_report(f, report)

        logger.info(f"Report saved to {json_file} and {md_file}")

    def _write_markdown_report(self, file, report: Dict[str, Any]):
        """Write markdown formatted report."""
        metrics = report['overall_metrics']

        file.write("# SLATE Profitability Analysis Report\n\n")
        file.write(f"**Generated:** {report['generated_at']}\n")
        file.write(f"**Analysis Period:** {report['analysis_period_days']} days\n")
        file.write(f"**Total Strategies:** {metrics.total_strategies:,}\n\n")

        file.write("## Executive Summary\n\n")
        file.write(f"**Analysis of {metrics.total_strategies:,} strategies:**\n")
        file.write(f"- **{metrics.success_rate:.1f}% profitable** ({metrics.profitable_strategies:,} strategies)\n")
        file.write(f"- **{100 - metrics.success_rate:.1f}% unprofitable** ({metrics.unprofitable_strategies:,} strategies)\n\n")

        file.write("## Timeframe Analysis\n\n")
        file.write("| Timeframe | Success Rate | Profitable | Total |\n")
        file.write("|-----------|--------------|------------|-------|\n")

        for tf in report['timeframe_analysis']:
            file.write(f"| {tf.timeframe} | {tf.success_rate:.1f}% | {tf.profitable_count:,} | {tf.total_count:,} |\n")

        file.write("\n## Recommendations\n\n")
        for rec in report['recommendations']:
            file.write(f"{rec}\n")

        file.write(f"\n---\n\n**Report Generation Time:** {report['generation_time_seconds']:.1f}s\n")


# Global reporter instance
_reporter: Optional[ProfitabilityReporter] = None


def get_profitability_reporter(db_path: str = "slate_core/slate_realistic_discoveries.db") -> ProfitabilityReporter:
    """Get global profitability reporter instance."""
    global _reporter
    if _reporter is None:
        _reporter = ProfitabilityReporter(db_path=db_path)
    return _reporter


if __name__ == "__main__":
    # Quick test
    reporter = get_profitability_reporter()
    report = reporter.generate_comprehensive_report(output_dir="reports")
    print(json.dumps(report, indent=2, default=str))