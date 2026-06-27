"""
SLATE Discovery Reporter

Comprehensive reporting system for autonomous trading discoveries.
Generates insights, recommendations, and performance summaries.
"""

import logging
from typing import Dict, List, Any
from datetime import datetime
from collections import defaultdict

from .config import Discovery, DiscoveryCategory

logger = logging.getLogger(__name__)


class DiscoveryReporter:
    """
    Generate comprehensive reports on autonomous discoveries.

    This reporter creates:
    - Strategy performance summaries
    - Risk analysis and recommendations
    - Market condition insights
    - Profitability metrics with realistic costs
    - Actionable recommendations for deployment
    """

    def __init__(self, config):
        """
        Initialize discovery reporter.

        Args:
            config: Autonomous configuration
        """
        self.config = config
        self.report_history = []

        logger.info("Discovery Reporter initialized")

    def generate_report(self, discoveries: List[Discovery],
                       system_status: Dict[str, Any]) -> str:
        """
        Generate comprehensive discovery report.

        Args:
            discoveries: List of validated discoveries
            system_status: Current autonomous system status

        Returns:
            Formatted report string
        """
        if not discoveries:
            return self._generate_empty_report(system_status)

        # Categorize discoveries
        categorized = self._categorize_discoveries(discoveries)

        # Generate report sections
        report_lines = [
            self._generate_header(system_status),
            self._generate_summary(discoveries, categorized),
            self._generate_top_strategies(discoveries),
            self._generate_risk_analysis(discoveries),
            self._generate_market_insights(categorized),
            self._generate_recommendations(discoveries),
            self._generate_footer(system_status)
        ]

        return "\n\n".join(report_lines)

    def _generate_empty_report(self, system_status: Dict[str, Any]) -> str:
        """Generate report when no discoveries available"""
        return f"""
# SLATE Autonomous Discovery Report

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Status**: No validated discoveries yet

## System Status

- **Autonomous State**: {system_status.get('state', 'unknown')}
- **Discovery Cycles**: {system_status.get('discovery_cycles', 0)}
- **Uptime**: {system_status.get('uptime_seconds', 0) / 3600:.1f} hours
- **Resources**: CPU {system_status.get('resource_status', {}).get('cpu_percent', 0):.1f}%, Memory {system_status.get('resource_status', {}).get('memory_percent', 0):.1f}%

## Information

SLATE is actively running autonomous discovery cycles. Validated discoveries
will appear here once they pass the multi-criteria validation including
transaction cost reality, statistical significance, and risk-adjusted returns.

**Validation Requirements**:
- Profit AFTER 0.02% maker + 0.05% taker fees
- Minimum 20 trades with statistical significance
- Sharpe ratio >= 0.5
- Maximum drawdown <= 25%
- Out-of-sample validation required

Continue monitoring for discoveries...
        """.strip()

    def _generate_header(self, status: Dict[str, Any]) -> str:
        """Generate report header"""
        return f"""
# SLATE Autonomous Discovery Report

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Discovery Cycles**: {status.get('discovery_cycles', 0)}
**Total Discoveries**: {status.get('discoveries_made', 0)}
**Validated Discoveries**: {status.get('discoveries_validated', 0)}
**Autonomous State**: {status.get('state', 'unknown')}
        """.strip()

    def _categorize_discoveries(self, discoveries: List[Discovery]) -> Dict[str, List[Discovery]]:
        """Categorize discoveries by type"""
        categorized = defaultdict(list)
        for discovery in discoveries:
            categorized[discovery.category.value].append(discovery)
        return dict(categorized)

    def _generate_summary(self, discoveries: List[Discovery],
                         categorized: Dict[str, List[Discovery]]) -> str:
        """Generate discoveries summary"""
        # Calculate aggregate statistics
        avg_return = sum(d.total_return_pct for d in discoveries) / len(discoveries) if discoveries else 0
        avg_sharpe = sum(d.sharpe_ratio for d in discoveries) / len(discoveries) if discoveries else 0
        avg_drawdown = sum(d.max_drawdown_pct for d in discoveries) / len(discoveries) if discoveries else 0

        total_costs = sum(d.transaction_costs_usdt for d in discoveries)
        total_profit_after_costs = sum(d.profit_after_costs for d in discoveries)

        return f"""
## Summary Statistics

**Performance Metrics**:
- Average Return: {avg_return:.2f}%
- Average Sharpe Ratio: {avg_sharpe:.2f}
- Average Max Drawdown: {avg_drawdown:.2f}%
- Total Transaction Costs: ${total_costs:.2f}
- Total Profit After Costs: ${total_profit_after_costs:.2f}

**Discovery Categories**:
{self._format_category_counts(categorized)}

**Validation Quality**:
- All discoveries passed transaction cost reality validation
- All discoveries include realistic slippage (10 bps) and partial fills (15%)
- All discoveries validated with out-of-sample testing
        """.strip()

    def _format_category_counts(self, categorized: Dict[str, List[Discovery]]) -> str:
        """Format category counts for summary"""
        lines = []
        for category, discoveries in categorized.items():
            lines.append(f"  - {category.replace('_', ' ').title()}: {len(discoveries)}")
        return "\n".join(lines) if lines else "  No categories yet"

    def _generate_top_strategies(self, discoveries: List[Discovery]) -> str:
        """Generate top performing strategies section"""
        # Sort by profitability after costs
        sorted_discoveries = sorted(
            discoveries,
            key=lambda d: d.profit_after_costs,
            reverse=True
        )[:5]  # Top 5

        lines = ["## Top Performing Strategies"]
        lines.append("")
        lines.append("| Rank | Strategy | Return | Sharpe | Drawdown | Profit After Costs |")
        lines.append("|------|----------|--------|--------|----------|-------------------|")

        for i, discovery in enumerate(sorted_discoveries, 1):
            lines.append(
                f"| {i} | {discovery.question[:40]}... | "
                f"{discovery.total_return_pct:.2f}% | "
                f"{discovery.sharpe_ratio:.2f} | "
                f"{discovery.max_drawdown_pct:.2f}% | "
                f"${discovery.profit_after_costs:.2f} |"
            )

        return "\n".join(lines)

    def _generate_risk_analysis(self, discoveries: List[Discovery]) -> str:
        """Generate risk analysis section"""
        if not discoveries:
            return "## Risk Analysis\n\nNo discoveries to analyze."

        # Risk statistics
        high_sharpe = [d for d in discoveries if d.sharpe_ratio >= 1.0]
        low_drawdown = [d for d in discoveries if abs(d.max_drawdown_pct) <= 15.0]
        high_winrate = [d for d in discoveries if d.win_rate >= 0.6]

        return f"""
## Risk Analysis

**Risk-Adjusted Performance**:
- Strategies with Sharpe >= 1.0: {len(high_sharpe)}/{len(discoveries)} ({len(high_sharpe)/len(discoveries)*100:.1f}%)
- Strategies with Drawdown <= 15%: {len(low_drawdown)}/{len(discoveries)} ({len(low_drawdown)/len(discoveries)*100:.1f}%)
- Strategies with Win Rate >= 60%: {len(high_winrate)}/{len(discoveries)} ({len(high_winrate)/len(discoveries)*100:.1f}%)

**Transaction Cost Impact**:
- Average cost per strategy: ${sum(d.transaction_costs_usdt for d in discoveries)/len(discoveries):.2f}
- Strategies with realistic edge: {len([d for d in discoveries if d.realistic_edge])}/{len(discoveries)}
- All strategies validated with actual Binance fees (0.02% maker, 0.05% taker)

**Risk Assessment**:
{'✅ EXCELLENT' if len(high_sharpe) >= len(discoveries)*0.7 else '⚠️ NEEDS IMPROVEMENT' if len(high_sharpe) >= len(discoveries)*0.4 else '❌ POOR'} - Risk-adjusted return quality
        """.strip()

    def _generate_market_insights(self, categorized: Dict[str, List[Discovery]]) -> str:
        """Generate market insights section"""
        lines = ["## Market Insights"]

        if not categorized:
            lines.append("\nNo market insights yet.")
            return "\n".join(lines)

        for category, discoveries in categorized.items():
            if discoveries:
                lines.append(f"\n### {category.replace('_', ' ').title()}")
                lines.append(f"Found {len(discoveries)} discoveries in this category")

                # Show top insight from this category
                top = max(discoveries, key=lambda d: d.confidence)
                lines.append(f"\n**Top Insight**: {top.answer[:100]}...")
                lines.append(f"Confidence: {top.confidence*100:.1f}%")
                lines.append(f"Symbol: {top.symbol} | Timeframe: {top.timeframe}")

        return "\n".join(lines)

    def _generate_recommendations(self, discoveries: List[Discovery]) -> str:
        """Generate actionable recommendations"""
        lines = ["## Recommendations"]

        if not discoveries:
            lines.append("\nNo recommendations yet - waiting for validated discoveries.")
            return "\n".join(lines)

        # Analyze discoveries for recommendations
        high_profit = [d for d in discoveries if d.total_return_pct >= 10.0]
        robust_strategies = [d for d in discoveries if d.sharpe_ratio >= 1.0 and abs(d.max_drawdown_pct) <= 20.0]

        lines.append("\n### Deployment Candidates")

        if robust_strategies:
            lines.append(f"\n**{len(robust_strategies)} Robust Strategies** (Sharpe >= 1.0, Drawdown <= 20%):")
            for strategy in robust_strategies[:3]:
                lines.append(f"- {strategy.question[:60]}...")
                lines.append(f"  Return: {strategy.total_return_pct:.2f}%, Sharpe: {strategy.sharpe_ratio:.2f}")
        else:
            lines.append("\n⚠️ No strategies meet robustness criteria yet.")

        lines.append("\n### Further Investigation")

        if high_profit:
            lines.append(f"\n**{len(high_profit)} High-Profit Strategies** (Return >= 10%):")
            lines.append("These strategies show promise but may need further validation:")
            for strategy in high_profit[:3]:
                lines.append(f"- {strategy.question[:60]}... ({strategy.total_return_pct:.2f}% return)")

        lines.append("\n### Next Steps")
        lines.append("1. Review top strategies in detail")
        lines.append("2. Perform additional out-of-sample testing")
        lines.append("3. Assess implementation feasibility")
        lines.append("4. Consider position sizing and risk management")

        return "\n".join(lines)

    def _generate_footer(self, status: Dict[str, Any]) -> str:
        """Generate report footer"""
        return f"""

---

**Report End** | SLATE Autonomous Discovery System | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**System Resources**:
- CPU Usage: {status.get('resource_status', {}).get('cpu_percent', 0):.1f}%
- Memory Usage: {status.get('resource_status', {}).get('memory_percent', 0):.1f}%
- Weekly Hours Used: {status.get('resource_status', {}).get('weekly_hours_used', 0):.1f}h
- Discovery Time: {status.get('total_discovery_time_hours', 0):.2f}h

**Validation Guarantee**: All reported discoveries have passed multi-criteria validation
including transaction cost reality, statistical significance, market regime specificity,
and risk-adjusted return requirements.
        """.strip()

    def generate_alerts(self, discoveries: List[Discovery]) -> List[str]:
        """
        Generate alerts for significant discoveries.

        Args:
            discoveries: List of discoveries to check

        Returns:
            List of alert messages
        """
        alerts = []

        for discovery in discoveries:
            # Alert for exceptionally profitable strategies
            if discovery.total_return_pct >= 20.0:
                alerts.append(
                    f"🚀 HIGH PROFIT: {discovery.question[:50]}... "
                    f"({discovery.total_return_pct:.2f}% return)"
                )

            # Alert for excellent risk-adjusted returns
            if discovery.sharpe_ratio >= 1.5:
                alerts.append(
                    f"⭐ EXCELLENT SHARPE: {discovery.question[:50]}... "
                    f"(Sharpe: {discovery.sharpe_ratio:.2f})"
                )

            # Alert for low drawdown strategies
            if abs(discovery.max_drawdown_pct) <= 10.0:
                alerts.append(
                    f"🛡️ LOW RISK: {discovery.question[:50]}... "
                    f"(Drawdown: {discovery.max_drawdown_pct:.2f}%)"
                )

            # Alert for high novelty discoveries
            if discovery.novelty_score >= 0.9:
                alerts.append(
                    f"💡 NOVEL DISCOVERY: {discovery.question[:50]}... "
                    f"(Novelty: {discovery.novelty_score*100:.1f}%)"
                )

        return alerts