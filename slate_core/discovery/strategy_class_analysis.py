"""
COMPREHENSIVE STRATEGY CLASS ANALYSIS
Analysis of 33,226 discovery tests to identify profitable classes and improvements
"""

import sqlite3
import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class StrategyClassAnalyzer:
    """Analyze 33,000+ strategy tests to identify profitable classes and improvements."""

    def __init__(self, db_path: str = "slate_core/slate_realistic_discoveries.db"):
        self.db_path = db_path
        self.analysis_results = {}

    def get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def analyze_overall_performance(self) -> Dict:
        """Analyze overall performance across all strategy classes."""
        conn = self.get_connection()

        query = """
        SELECT
            strategy_type,
            COUNT(*) as total_tests,
            SUM(CASE WHEN total_return > 0 THEN 1 ELSE 0 END) as profitable_tests,
            AVG(total_return) as avg_return,
            MAX(total_return) as max_return,
            AVG(sharpe_ratio) as avg_sharpe,
            MAX(sharpe_ratio) as max_sharpe,
            AVG(max_drawdown) as avg_drawdown,
            MIN(max_drawdown) as min_drawdown,
            AVG(total_return) / NULLIF(AVG(max_drawdown), 0) as return_drawdown_ratio
        FROM discovery_results
        WHERE total_return IS NOT NULL
        GROUP BY strategy_type
        ORDER BY max_return DESC
        """

        df = pd.read_sql_query(query, conn)
        conn.close()

        logger.info("Overall Performance by Strategy Class:")
        logger.info("=" * 80)
        for _, row in df.iterrows():
            logger.info(f"\n{row['strategy_type'].upper()}:")
            logger.info(f"  Tests: {row['total_tests']:,}")
            logger.info(f"  Profitable: {row['profitable_tests']:,} ({row['profitable_tests']/row['total_tests']*100:.1f}%)")
            logger.info(f"  Avg Return: {row['avg_return']*100:.3f}%")
            logger.info(f"  Max Return: {row['max_return']*100:.2f}%")
            logger.info(f"  Avg Sharpe: {row['avg_sharpe']:.2f}")
            logger.info(f"  Max Sharpe: {row['max_sharpe']:.2f}")
            logger.info(f"  Avg Drawdown: {row['avg_drawdown']*100:.2f}%")
            logger.info(f"  Return/DD Ratio: {row['return_drawdown_ratio']:.4f}")

        return df.to_dict('records')

    def analyze_top_performers(self, limit: int = 100) -> List[Dict]:
        """Analyze top performers across all classes."""
        conn = self.get_connection()

        query = """
        SELECT
            strategy_name,
            strategy_type,
            total_return,
            sharpe_ratio,
            max_drawdown,
            total_return / NULLIF(max_drawdown, 0) as return_drawdown_ratio,
            parameters
        FROM discovery_results
        WHERE total_return > 0.005
        ORDER BY total_return DESC
        LIMIT ?
        """

        df = pd.read_sql_query(query, conn, params=(limit,))
        conn.close()

        # Parse parameters for analysis
        df['parsed_params'] = df['parameters'].apply(json.loads)

        logger.info(f"\nTop {limit} Performers Analysis:")
        logger.info("=" * 80)

        # Analyze common patterns
        timeframes = {}
        position_biases = {}
        weighting_methods = {}

        for _, row in df.iterrows():
            params = row['parsed_params']

            # Count timeframes
            if 'timeframes' in params:
                tf_key = str(params['timeframes'])
                timeframes[tf_key] = timeframes.get(tf_key, 0) + 1

            # Count position biases
            if 'position_bias' in params:
                bias = params['position_bias']
                position_biases[bias] = position_biases.get(bias, 0) + 1

            # Count weighting methods
            if 'weighting' in params:
                method = params['weighting']
                weighting_methods[method] = weighting_methods.get(method, 0) + 1

        logger.info("\nCommon Timeframes (in top performers):")
        for tf, count in sorted(timeframes.items(), key=lambda x: x[1], reverse=True)[:5]:
            logger.info(f"  {tf}: {count} times")

        logger.info("\nPosition Bias Distribution:")
        for bias, count in sorted(position_biases.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {bias}: {count} times")

        logger.info("\nWeighting Methods:")
        for method, count in sorted(weighting_methods.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {method}: {count} times")

        return df.to_dict('records')

    def analyze_threshold_patterns(self) -> Dict:
        """Analyze threshold patterns across profitable strategies."""
        conn = self.get_connection()

        query = """
        SELECT
            strategy_type,
            parameters,
            total_return,
            sharpe_ratio,
            max_drawdown
        FROM discovery_results
        WHERE total_return > 0.01
        ORDER BY total_return DESC
        """

        df = pd.read_sql_query(query, conn)
        conn.close()

        df['parsed_params'] = df['parameters'].apply(json.loads)
        df['threshold_values'] = df['parsed_params'].apply(
            lambda x: x.get('threshold', 0)
        )

        logger.info("\nThreshold Analysis:")
        logger.info("=" * 80)

        for strategy_type in df['strategy_type'].unique():
            type_df = df[df['strategy_type'] == strategy_type]
            logger.info(f"\n{strategy_type.upper()}:")
            logger.info(f"  Threshold range: {type_df['threshold_values'].min():.2e} to {type_df['threshold_values'].max():.2e}")
            logger.info(f"  Median threshold: {type_df['threshold_values'].median():.2e}")
            logger.info(f"  Avg threshold: {type_df['threshold_values'].mean():.2e}")

        return df.to_dict('records')

    def identify_improvement_opportunities(self) -> Dict:
        """Identify specific improvement opportunities for each class."""
        conn = self.get_connection()

        # Get baseline performance
        query = """
        SELECT
            strategy_type,
            AVG(total_return) as avg_return,
            MAX(total_return) as max_return,
            AVG(max_drawdown) as avg_drawdown,
            AVG(sharpe_ratio) as avg_sharpe,
            COUNT(*) as test_count
        FROM discovery_results
        WHERE total_return IS NOT NULL
        GROUP BY strategy_type
        """

        df = pd.read_sql_query(query, conn)
        conn.close()

        improvements = {}

        for _, row in df.iterrows():
            strategy_type = row['strategy_type']

            improvements[strategy_type] = {
                'current_best_return': row['max_return'],
                'current_avg_return': row['avg_return'],
                'current_avg_drawdown': row['avg_drawdown'],
                'current_avg_sharpe': row['avg_sharpe'],
                'test_count': row['test_count'],
                'potential_improvements': self._generate_improvements(strategy_type, row)
            }

        return improvements

    def _generate_improvements(self, strategy_type: str, performance: pd.Series) -> List[str]:
        """Generate specific improvement suggestions for a strategy type."""
        improvements = []

        # Common improvements based on low performance
        if performance['max_return'] < 0.05:  # Less than 5% max return
            improvements.append("CRITICAL: Current max return is very low (<5%)")
            improvements.append("→ Add machine learning layer for signal filtering")
            improvements.append("→ Implement volatility-adjusted position sizing")
            improvements.append("→ Add risk management (stop loss, take profit)")

        if performance['avg_drawdown'] > 0.10:  # More than 10% avg drawdown
            improvements.append("HIGH RISK: Average drawdown exceeds 10%")
            improvements.append("→ Implement dynamic position sizing based on volatility")
            improvements.append("→ Add maximum drawdown limits (system shutdown)")
            improvements.append("→ Add daily loss limits to protect capital")

        if performance['avg_sharpe'] < 1.0:
            improvements.append("LOW RISK-ADJUSTED RETURNS: Sharpe < 1.0")
            improvements.append("→ Improve signal quality with feature engineering")
            improvements.append("→ Add regime detection to avoid choppy markets")
            improvements.append("→ Implement ensemble of multiple strategies")

        # Strategy-specific improvements
        if strategy_type == 'multi_timeframe':
            improvements.append("MULTI-TIMEFRAME SPECIFIC:")
            improvements.append("→ Current: 5m/10m/15m - Add hourly timeframe for trend context")
            improvements.append("→ Add machine learning to weigh timeframes dynamically")
            improvements.append("→ Implement walk-forward validation instead of fixed windows")

        elif strategy_type == 'regime_switching':
            improvements.append("REGIME SWITCHING SPECIFIC:")
            improvements.append("→ Current: HMM detection - Add ML confirmation")
            improvements.append("→ Implement ensemble of regime detection methods")
            improvements.append("→ Add confidence-weighted position sizing per regime")

        elif strategy_type == 'statistical_arb':
            improvements.append("STATISTICAL ARB SPECIFIC:")
            improvements.append("→ Current: Mean reversion - Add momentum filter")
            improvements.append("→ Implement co-integration analysis")
            improvements.append("→ Add fundamental filters (funding rates, open interest)")

        elif strategy_type == 'trend_following':
            improvements.append("TREND FOLLOWING SPECIFIC:")
            improvements.append("→ CRITICAL: Only 2/4,231 tests profitable!")
            improvements.append("→ Complete redesign needed - consider ML approach")
            improvements.append("→ Add regime filtering to avoid choppy markets")

        return improvements

    def generate_improvement_report(self) -> str:
        """Generate comprehensive improvement report."""
        logger.info("\n" + "=" * 80)
        logger.info("COMPREHENSIVE STRATEGY CLASS ANALYSIS REPORT")
        logger.info("=" * 80)

        # Overall performance
        overall = self.analyze_overall_performance()

        # Top performers
        top_performers = self.analyze_top_performers(50)

        # Threshold patterns
        threshold_analysis = self.analyze_threshold_patterns()

        # Improvement opportunities
        improvements = self.identify_improvement_opportunities()

        # Generate report
        report = "\n\nSTRATEGY CLASS IMPROVEMENT REPORT\n"
        report += "=" * 80 + "\n\n"

        for strategy_type, data in improvements.items():
            report += f"\n{strategy_type.upper()}\n"
            report += "-" * 80 + "\n"
            report += f"Current Performance:\n"
            report += f"  Tests: {data['test_count']:,}\n"
            report += f"  Max Return: {data['current_best_return']*100:.2f}%\n"
            report += f"  Avg Return: {data['current_avg_return']*100:.3f}%\n"
            report += f"  Avg Drawdown: {data['current_avg_drawdown']*100:.2f}%\n"
            report += f"  Avg Sharpe: {data['current_avg_sharpe']:.2f}\n\n"

            report += "Recommended Improvements:\n"
            for improvement in data['potential_improvements']:
                report += f"  {improvement}\n"

            report += "\n"

        # Save report
        report_path = Path("strategy_class_improvement_report.txt")
        with open(report_path, 'w') as f:
            f.write(report)

        logger.info(f"\n✓ Improvement report saved to {report_path}")

        return report


if __name__ == "__main__":
    analyzer = StrategyClassAnalyzer()
    report = analyzer.generate_improvement_report()
    print(report)
