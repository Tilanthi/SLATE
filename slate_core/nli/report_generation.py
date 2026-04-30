#!/usr/bin/env python3
"""
SLATE Report Generation System

Phase 7: Natural Language Interface (Weeks 25-28)

Implements automated report generation:
- Research reports
- Performance dashboards
- Market summaries
- Strategy comparisons

Critical for communicating insights and decisions.

Author: SLATE Evolution
Date: 2026-04-30
Priority: MEDIUM - Report generation
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import json

logger = logging.getLogger(__name__)


class ReportType(Enum):
    """Types of reports."""
    RESEARCH = "research"  # Research findings
    PERFORMANCE = "performance"  # Performance summary
    MARKET = "market"  # Market conditions
    STRATEGY_COMPARISON = "strategy_comparison"  # Strategy comparison
    RISK = "risk"  # Risk analysis
    DAILY = "daily"  # Daily summary
    WEEKLY = "weekly"  # Weekly summary
    MONTHLY = "monthly"  # Monthly summary


@dataclass
class ReportSection:
    """A section of a report."""
    title: str
    content: str
    priority: int  # 1-10, higher = more important
    data: Optional[Dict[str, Any]] = None


@dataclass
class Report:
    """A generated report."""
    report_type: ReportType
    title: str
    generated_at: datetime
    period_start: Optional[datetime]
    period_end: Optional[datetime]

    sections: List[ReportSection]
    summary: str
    recommendations: List[str]

    # Metadata
    author: str = "SLATE System"
    version: str = "1.0"


class ResearchReportGenerator:
    """
    Generate research reports.

    Documents research findings and discoveries.
    """

    def __init__(self):
        logger.info("ResearchReportGenerator initialized")

    async def generate_research_report(
        self,
        research_data: Dict[str, Any],
        discoveries: List[Dict[str, Any]],
        hypotheses: List[Dict[str, Any]]
    ) -> Report:
        """
        Generate research report.

        Args:
            research_data: Research metadata
            discoveries: Strategy discoveries
            hypotheses: Hypothesis test results

        Returns:
            Research report
        """

        sections = []

        # Executive Summary
        summary = self._generate_research_summary(research_data, discoveries, hypotheses)
        sections.append(ReportSection(
            title="Executive Summary",
            content=summary,
            priority=10
        ))

        # Discovery Summary
        if discoveries:
            discovery_section = self._generate_discovery_section(discoveries)
            sections.append(discovery_section)

        # Hypothesis Testing
        if hypotheses:
            hypothesis_section = self._generate_hypothesis_section(hypotheses)
            sections.append(hypothesis_section)

        # Methodology
        methodology_section = self._generate_methodology_section(research_data)
        sections.append(methodology_section)

        # Recommendations
        recommendations = self._generate_research_recommendations(discoveries, hypotheses)

        return Report(
            report_type=ReportType.RESEARCH,
            title=f"Research Report: {research_data.get('title', 'Strategy Discovery')}",
            generated_at=datetime.now(),
            period_start=research_data.get('start_date'),
            period_end=research_data.get('end_date'),
            sections=sections,
            summary=summary,
            recommendations=recommendations
        )

    def _generate_research_summary(
        self,
        research_data: Dict[str, Any],
        discoveries: List[Dict[str, Any]],
        hypotheses: List[Dict[str, Any]]
    ) -> str:
        """Generate research summary."""

        total_strategies = len(discoveries)
        profitable_strategies = sum(1 for d in discoveries if d.get('return', 0) > 0)
        confirmed_hypotheses = sum(1 for h in hypotheses if h.get('status') == 'confirmed')

        summary = f"""
**Research Summary**

This report documents findings from the research period spanning
{research_data.get('start_date', 'N/A')} to {research_data.get('end_date', 'N/A')}.

**Key Findings:**
- Total strategies discovered: {total_strategies}
- Profitable strategies: {profitable_strategies} ({profitable_strategies/max(total_strategies, 1)*100:.1f}%)
- Hypotheses confirmed: {confirmed_hypotheses}/{len(hypotheses)}
- Research hours: {research_data.get('hours_spent', 'N/A')}

**Status:** {'✓ Successful' if profitable_strategies > 0 else '✗ No profitable discoveries'}
"""

        return summary

    def _generate_discovery_section(self, discoveries: List[Dict[str, Any]]) -> ReportSection:
        """Generate discovery section."""

        content = "**Top Discoveries:**\n\n"

        # Sort by return
        sorted_discoveries = sorted(discoveries, key=lambda d: d.get('return', 0), reverse=True)

        for i, discovery in enumerate(sorted_discoveries[:10], 1):
            name = discovery.get('name', 'Unknown')
            return_val = discovery.get('return', 0)
            sharpe = discovery.get('sharpe', 0)
            max_dd = discovery.get('max_drawdown', 0)

            content += f"""
{i}. **{name}**
   - Return: {return_val:.2%}
   - Sharpe: {sharpe:.2f}
   - Max DD: {max_dd:.2%}
"""

        return ReportSection(
            title="Strategy Discoveries",
            content=content,
            priority=9,
            data={'discoveries': discoveries}
        )

    def _generate_hypothesis_section(self, hypotheses: List[Dict[str, Any]]) -> ReportSection:
        """Generate hypothesis section."""

        content = "**Hypothesis Testing Results:**\n\n"

        for hypothesis in hypotheses:
            name = hypothesis.get('name', 'Unknown')
            status = hypothesis.get('status', 'unknown')
            confidence = hypothesis.get('confidence', 0)
            posterior = hypothesis.get('posterior_prob', 0.5)

            status_symbol = "✓" if status == 'confirmed' else "✗" if status == 'rejected' else "?"

            content += f"""
**{status_symbol} {name}**
- Status: {status.upper()}
- Confidence: {confidence:.1%}
- Posterior Probability: {posterior:.3f}
"""

        return ReportSection(
            title="Hypothesis Testing",
            content=content,
            priority=8,
            data={'hypotheses': hypotheses}
        )

    def _generate_methodology_section(self, research_data: Dict[str, Any]) -> ReportSection:
        """Generate methodology section."""

        content = f"""
**Research Methodology**

**Data Sources:**
- Markets: {', '.join(research_data.get('markets', ['BTC']))}
- Timeframe: {research_data.get('timeframe', '1h')}
- Data points: {research_data.get('data_points', 'N/A'):,}

**Methods:**
- Pattern recognition: {research_data.get('pattern_method', 'ML-based')}
- Validation: {research_data.get('validation', 'Walk-forward')}
- Execution model: {research_data.get('execution_model', 'Realistic')}

**Parameters:**
- Search space: {research_data.get('search_space', 'N/A')} combinations
- Validation periods: {research_data.get('validation_periods', 'N/A')}
- Confidence level: {research_data.get('confidence_level', 95)}%
"""

        return ReportSection(
            title="Methodology",
            content=content,
            priority=5
        )

    def _generate_research_recommendations(
        self,
        discoveries: List[Dict[str, Any]],
        hypotheses: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate research recommendations."""

        recommendations = []

        # Analyze discoveries
        if discoveries:
            top_discovery = max(discoveries, key=lambda d: d.get('return', 0))
            if top_discovery.get('return', 0) > 0.1:
                recommendations.append(f"Deploy {top_discovery.get('name', 'top strategy')} for live paper trading")

            profitable_count = sum(1 for d in discoveries if d.get('return', 0) > 0)
            if profitable_count > 1:
                recommendations.append(f"Consider ensemble of top {min(3, profitable_count)} strategies")

        # Analyze hypotheses
        confirmed = [h for h in hypotheses if h.get('status') == 'confirmed']
        if confirmed:
            recommendations.append(f"Follow up on {len(confirmed)} confirmed hypotheses with deeper research")

        # General recommendations
        if not discoveries or all(d.get('return', 0) <= 0 for d in discoveries):
            recommendations.append("Review discovery parameters — no profitable strategies found")

        recommendations.append("Continue monitoring market conditions")
        recommendations.append("Update research based on new data")

        return recommendations


class PerformanceReportGenerator:
    """
    Generate performance reports.

    Summarizes strategy and portfolio performance.
    """

    def __init__(self):
        logger.info("PerformanceReportGenerator initialized")

    async def generate_performance_report(
        self,
        performance_data: Dict[str, Any],
        period: str = "daily"
    ) -> Report:
        """
        Generate performance report.

        Args:
            performance_data: Performance metrics
            period: Report period

        Returns:
            Performance report
        """

        sections = []

        # Performance Summary
        summary = self._generate_performance_summary(performance_data)
        sections.append(ReportSection(
            title="Performance Summary",
            content=summary,
            priority=10
        ))

        # Strategy Performance
        if 'strategies' in performance_data:
            strategy_section = self._generate_strategy_section(performance_data['strategies'])
            sections.append(strategy_section)

        # Risk Analysis
        risk_section = self._generate_risk_section(performance_data)
        sections.append(risk_section)

        # Attribution
        if 'attribution' in performance_data:
            attribution_section = self._generate_attribution_section(performance_data['attribution'])
            sections.append(attribution_section)

        # Recommendations
        recommendations = self._generate_performance_recommendations(performance_data)

        return Report(
            report_type=ReportType.PERFORMANCE,
            title=f"{period.capitalize()} Performance Report",
            generated_at=datetime.now(),
            period_start=performance_data.get('period_start'),
            period_end=performance_data.get('period_end'),
            sections=sections,
            summary=summary,
            recommendations=recommendations
        )

    def _generate_performance_summary(self, data: Dict[str, Any]) -> str:
        """Generate performance summary."""

        total_return = data.get('total_return', 0)
        benchmark_return = data.get('benchmark_return', 0)
        alpha = total_return - benchmark_return
        sharpe = data.get('sharpe', 0)
        max_dd = data.get('max_drawdown', 0)

        return f"""
**Performance Summary**

**Period:** {data.get('period_start', 'N/A')} to {data.get('period_end', 'N/A')}

**Returns:**
- Total Return: {total_return:.2%}
- Benchmark Return: {benchmark_return:.2%}
- Alpha: {alpha:.2%}

**Risk Metrics:**
- Sharpe Ratio: {sharpe:.2f}
- Maximum Drawdown: {max_dd:.2%}
- Volatility: {data.get('volatility', 0):.2%}

**Assessment:** {'✓ Strong performance' if alpha > 0 and sharpe > 1 else '✗ Underperforming' if alpha < 0 else '~ Neutral'}
"""

    def _generate_strategy_section(self, strategies: Dict[str, Any]) -> ReportSection:
        """Generate strategy section."""

        content = "**Strategy Performance:**\n\n"

        for strategy_name, metrics in strategies.items():
            return_val = metrics.get('return', 0)
            sharpe = metrics.get('sharpe', 0)
            active = metrics.get('active', False)

            status = "🟢 Active" if active else "⚪ Inactive"

            content += f"""
**{strategy_name}** ({status})
- Return: {return_val:.2%}
- Sharpe: {sharpe:.2f}
- Trades: {metrics.get('trades', 'N/A')}
"""

        return ReportSection(
            title="Strategy Details",
            content=content,
            priority=8,
            data={'strategies': strategies}
        )

    def _generate_risk_section(self, data: Dict[str, Any]) -> ReportSection:
        """Generate risk section."""

        content = f"""
**Risk Analysis**

**Value at Risk:**
- VaR (95%): {data.get('var_95', 0):.4f}
- CVaR (95%): {data.get('cvar_95', 0):.4f}

**Drawdown Analysis:**
- Max Drawdown: {data.get('max_drawdown', 0):.2%}
- Current Drawdown: {data.get('current_drawdown', 0):.2%}
- Average Drawdown: {data.get('avg_drawdown', 0):.2%}

**Position Risk:**
- Max Position Size: {data.get('max_position_size', 0):.2%}
- Portfolio Heat: {data.get('portfolio_heat', 0):.2%}
"""

        return ReportSection(
            title="Risk Analysis",
            content=content,
            priority=7
        )

    def _generate_attribution_section(self, attribution: Dict[str, Any]) -> ReportSection:
        """Generate attribution section."""

        luck_skill = attribution.get('luck_vs_skill', {})
        attribution_type = luck_skill.get('type', 'unknown')
        skill = luck_skill.get('skill_component', 0)

        content = f"""
**Performance Attribution**

**Luck vs Skill:** {attribution_type.upper()}
- Skill Component: {skill:.2%}
- Luck Component: {luck_skill.get('luck_component', 0):.2%}
- Confidence: {luck_skill.get('confidence', 0):.1%}

**Interpretation:** {'Performance appears to be genuine skill' if attribution_type == 'skill' else 'Performance may be due to luck'}

**Factor Exposure:**
"""
        factors = attribution.get('factor_attribution', {})
        for factor, value in factors.items():
            content += f"- {factor}: {value:.3f}\n"

        return ReportSection(
            title="Performance Attribution",
            content=content,
            priority=6
        )

    def _generate_performance_recommendations(self, data: Dict[str, Any]) -> List[str]:
        """Generate performance recommendations."""

        recommendations = []

        if data.get('total_return', 0) < 0:
            recommendations.append("Review underperforming strategies")
            recommendations.append("Consider reducing exposure")

        if data.get('sharpe', 0) < 0.5:
            recommendations.append("Improve risk-adjusted returns")
            recommendations.append("Review position sizing")

        if data.get('max_drawdown', 0) > 0.2:
            recommendations.append("Implement tighter risk controls")
            recommendations.append("Review stop-loss levels")

        recommendations.append("Monitor market regime changes")
        recommendations.append("Update strategy parameters if needed")

        return recommendations


class MarketReportGenerator:
    """
    Generate market condition reports.

    Summarizes current market state and opportunities.
    """

    def __init__(self):
        logger.info("MarketReportGenerator initialized")

    async def generate_market_report(
        self,
        market_data: Dict[str, Any],
        alerts: List[Dict[str, Any]]
    ) -> Report:
        """
        Generate market report.

        Args:
            market_data: Market information
            alerts: Active alerts

        Returns:
            Market report
        """

        sections = []

        # Market Summary
        summary = self._generate_market_summary(market_data)
        sections.append(ReportSection(
            title="Market Summary",
            content=summary,
            priority=10
        ))

        # Regime Analysis
        regime_section = self._generate_regime_section(market_data)
        sections.append(regime_section)

        # Opportunities
        if alerts:
            opportunity_section = self._generate_opportunity_section(alerts)
            sections.append(opportunity_section)

        # Recommendations
        recommendations = self._generate_market_recommendations(market_data, alerts)

        return Report(
            report_type=ReportType.MARKET,
            title="Market Conditions Report",
            generated_at=datetime.now(),
            period_start=datetime.now() - timedelta(hours=24),
            period_end=datetime.now(),
            sections=sections,
            summary=summary,
            recommendations=recommendations
        )

    def _generate_market_summary(self, data: Dict[str, Any]) -> str:
        """Generate market summary."""

        regime = data.get('regime', 'UNKNOWN')
        volatility = data.get('volatility', 0)
        trend = data.get('trend', 'NEUTRAL')

        return f"""
**Market Summary**

**Current Regime:** {regime}
**Volatility:** {volatility:.2%} annualized
**Trend:** {trend}

**Market State:** {'Elevated volatility — exercise caution' if volatility > 0.4 else 'Normal conditions'}

**Key Levels:**
"""

        for symbol, levels in data.get('key_levels', {}).items():
            content = f"- **{symbol}**: Support {levels.get('support', 'N/A')}, Resistance {levels.get('resistance', 'N/A')}\n"

        return content

    def _generate_regime_section(self, data: Dict[str, Any]) -> ReportSection:
        """Generate regime section."""

        regime = data.get('regime', 'UNKNOWN')
        regime_confidence = data.get('regime_confidence', 0)

        content = f"""
**Regime Analysis**

**Current Market Regime:** {regime}
**Confidence:** {regime_confidence:.1%}

**Regime Characteristics:**
"""

        characteristics = data.get('regime_characteristics', {})
        for key, value in characteristics.items():
            content += f"- {key}: {value}\n"

        content += f"""

**Expected Strategy Performance:**
"""

        strategy_performance = data.get('expected_strategy_performance', {})
        for strategy, perf in strategy_performance.items():
            symbol = "✓" if perf > 0 else "✗"
            content += f"{symbol} {strategy}: {perf:.2%}\n"

        return ReportSection(
            title="Regime Analysis",
            content=content,
            priority=9
        )

    def _generate_opportunity_section(self, alerts: List[Dict[str, Any]]) -> ReportSection:
        """Generate opportunity section."""

        content = "**Active Opportunities:**\n\n"

        for alert in sorted(alerts, key=lambda a: a.get('severity', 'LOW'), reverse=True)[:10]:
            title = alert.get('title', 'Unknown')
            severity = alert.get('severity', 'LOW')
            description = alert.get('description', '')

            symbol = "🔴" if severity == 'CRITICAL' else "🟠" if severity == 'HIGH' else "🟡"

            content += f"""
**{symbol} {title}**
- Severity: {severity}
- Description: {description}
"""

        return ReportSection(
            title="Trading Opportunities",
            content=content,
            priority=8,
            data={'alerts': alerts}
        )

    def _generate_market_recommendations(
        self,
        market_data: Dict[str, Any],
        alerts: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate market recommendations."""

        recommendations = []

        regime = market_data.get('regime', 'UNKNOWN')
        volatility = market_data.get('volatility', 0)

        if regime == 'HIGH_VOLATILITY':
            recommendations.append("Reduce position sizes due to elevated volatility")
            recommendations.append("Consider volatility-based strategies")
        elif regime == 'BEAR_MARKET':
            recommendations.append("Focus on defensive strategies")
            recommendations.append("Consider short-selling or hedging")
        elif regime == 'BULL_MARKET':
            recommendations.append("Increase exposure to momentum strategies")
            recommendations.append("Consider trend-following approaches")

        critical_alerts = [a for a in alerts if a.get('severity') in ['CRITICAL', 'HIGH']]
        if critical_alerts:
            recommendations.append(f"Review {len(critical_alerts)} high-priority alerts")

        recommendations.append("Monitor for regime changes")

        return recommendations


class ReportGenerator:
    """
    Unified report generation system.

    Coordinates all report types.
    """

    def __init__(self):
        self.research_generator = ResearchReportGenerator()
        self.performance_generator = PerformanceReportGenerator()
        self.market_generator = MarketReportGenerator()

        logger.info("ReportGenerator initialized")

    async def generate_report(
        self,
        report_type: ReportType,
        data: Dict[str, Any],
        **kwargs
    ) -> Report:
        """
        Generate report.

        Args:
            report_type: Type of report
            data: Report data
            **kwargs: Additional parameters

        Returns:
            Generated report
        """

        if report_type == ReportType.RESEARCH:
            return await self.research_generator.generate_research_report(
                data,
                data.get('discoveries', []),
                data.get('hypotheses', [])
            )

        elif report_type in [ReportType.PERFORMANCE, ReportType.DAILY, ReportType.WEEKLY, ReportType.MONTHLY]:
            return await self.performance_generator.generate_performance_report(
                data,
                kwargs.get('period', 'daily')
            )

        elif report_type == ReportType.MARKET:
            return await self.market_generator.generate_market_report(
                data,
                data.get('alerts', [])
            )

        elif report_type == ReportType.STRATEGY_COMPARISON:
            return await self._generate_strategy_comparison_report(data)

        elif report_type == ReportType.RISK:
            return await self._generate_risk_report(data)

        else:
            raise ValueError(f"Unknown report type: {report_type}")

    async def _generate_strategy_comparison_report(self, data: Dict[str, Any]) -> Report:
        """Generate strategy comparison report."""

        strategies = data.get('strategies', {})

        content = "**Strategy Comparison:**\n\n"

        # Create comparison table
        content += "| Strategy | Return | Sharpe | Max DD | Win Rate |\n"
        content += "|---------|--------|--------|--------|----------|\n"

        for name, metrics in strategies.items():
            content += f"| {name} | {metrics.get('return', 0):.2%} | {metrics.get('sharpe', 0):.2f} | {metrics.get('max_drawdown', 0):.2%} | {metrics.get('win_rate', 0):.1%} |\n"

        # Recommendations
        recommendations = [
            "Select strategies based on risk tolerance",
            "Consider diversifying across strategy types",
            "Monitor for regime-dependent performance"
        ]

        return Report(
            report_type=ReportType.STRATEGY_COMPARISON,
            title="Strategy Comparison Report",
            generated_at=datetime.now(),
            period_start=data.get('period_start'),
            period_end=data.get('period_end'),
            sections=[ReportSection("Comparison", content, 10)],
            summary=content,
            recommendations=recommendations
        )

    async def _generate_risk_report(self, data: Dict[str, Any]) -> Report:
        """Generate risk report."""

        tail_metrics = data.get('tail_metrics', {})
        stress_results = data.get('stress_test_results', {})

        content = f"""
**Risk Assessment Report**

**Tail Risk Metrics:**
- VaR (95%): {tail_metrics.get('var_95', 0):.4f}
- CVaR (95%): {tail_metrics.get('cvar_95', 0):.4f}
- Max Drawdown: {tail_metrics.get('max_drawdown', 0):.2%}
- Tail Index: {tail_metrics.get('tail_index', 0):.3f}

**Stress Test Results:**
"""

        for scenario, results in stress_results.items():
            content += f"- {scenario}: {results.get('loss_pct', 0):.2%} loss\n"

        recommendations = [
            "Review position sizes",
            "Consider tail hedges if appropriate",
            "Monitor for regime changes"
        ]

        return Report(
            report_type=ReportType.RISK,
            title="Risk Assessment Report",
            generated_at=datetime.now(),
            period_start=data.get('period_start'),
            period_end=data.get('period_end'),
            sections=[ReportSection("Risk Analysis", content, 10)],
            summary=content,
            recommendations=recommendations
        )

    def format_report(self, report: Report, format_type: str = "markdown") -> str:
        """
        Format report for output.

        Args:
            report: Report to format
            format_type: Output format (markdown, html, text)

        Returns:
            Formatted report
        """

        if format_type == "markdown":
            return self._format_markdown(report)
        elif format_type == "html":
            return self._format_html(report)
        elif format_type == "text":
            return self._format_text(report)
        else:
            raise ValueError(f"Unknown format: {format_type}")

    def _format_markdown(self, report: Report) -> str:
        """Format report as Markdown."""

        output = f"# {report.title}\n\n"
        output += f"**Generated:** {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        output += f"**Author:** {report.author}\n"
        output += f"**Version:** {report.version}\n\n"

        if report.period_start and report.period_end:
            output += f"**Period:** {report.period_start.strftime('%Y-%m-%d')} to {report.period_end.strftime('%Y-%m-%d')}\n\n"

        output += "## Summary\n\n"
        output += report.summary
        output += "\n\n"

        # Sort sections by priority
        sorted_sections = sorted(report.sections, key=lambda s: s.priority, reverse=True)

        for section in sorted_sections:
            output += f"## {section.title}\n\n"
            output += section.content
            output += "\n\n"

        if report.recommendations:
            output += "## Recommendations\n\n"
            for rec in report.recommendations:
                output += f"- {rec}\n"
            output += "\n\n"

        return output

    def _format_html(self, report: Report) -> str:
        """Format report as HTML."""

        html = f"<html><head><title>{report.title}</title></head><body>\n"
        html += f"<h1>{report.title}</h1>\n"
        html += f"<p><strong>Generated:</strong> {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}<br>\n"
        html += f"<strong>Author:</strong> {report.author}</p>\n"

        html += "<h2>Summary</h2>\n"
        html += f"<p>{report.summary.replace(chr(10), '<br>')}</p>\n"

        for section in sorted(report.sections, key=lambda s: s.priority, reverse=True):
            html += f"<h2>{section.title}</h2>\n"
            html += f"<p>{section.content.replace(chr(10), '<br>')}</p>\n"

        if report.recommendations:
            html += "<h2>Recommendations</h2>\n<ul>\n"
            for rec in report.recommendations:
                html += f"<li>{rec}</li>\n"
            html += "</ul>\n"

        html += "</body></html>"
        return html

    def _format_text(self, report: Report) -> str:
        """Format report as plain text."""

        output = f"{report.title}\n"
        output += "=" * 60 + "\n\n"
        output += f"Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        output += f"Author: {report.author}\n\n"

        output += "SUMMARY\n"
        output += "-" * 60 + "\n"
        output += report.summary + "\n\n"

        for section in sorted(report.sections, key=lambda s: s.priority, reverse=True):
            output += f"{section.title.upper()}\n"
            output += "-" * 60 + "\n"
            output += section.content + "\n\n"

        if report.recommendations:
            output += "RECOMMENDATIONS\n"
            output += "-" * 60 + "\n"
            for rec in report.recommendations:
                output += f"• {rec}\n"
            output += "\n"

        return output


# Singleton instance
_report_generator = None


def get_report_generator() -> ReportGenerator:
    """Get or create report generator instance."""
    global _report_generator
    if _report_generator is None:
        _report_generator = ReportGenerator()
    return _report_generator
