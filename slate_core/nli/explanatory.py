#!/usr/bin/env python3
"""
SLATE Explanatory Capabilities System

Phase 7: Natural Language Interface (Weeks 25-28)

Implements strategy explanations and insights:
- Strategy explanations
- Performance attribution
- Risk factor explanations
- Recommendation reasoning

Critical for user understanding and trust.

Author: SLATE Evolution
Date: 2026-04-30
Priority: MEDIUM - Explanatory capabilities
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


class ExplanationLevel(Enum):
    """Detail level of explanations."""
    BASIC = "basic"  # Simple, high-level
    INTERMEDIATE = "intermediate"  # Balanced detail
    ADVANCED = "advanced"  # Technical, detailed
    EXPERT = "expert"  # Highly technical, mathematical


@dataclass
class StrategyExplanation:
    """Explanation of a trading strategy."""
    strategy_name: str
    strategy_type: str
    description: str

    # Components
    entry_conditions: List[str]
    exit_conditions: List[str]
    risk_management: List[str]

    # Performance
    historical_performance: Dict[str, float]
    risk_metrics: Dict[str, float]

    # Insights
    strengths: List[str]
    weaknesses: List[str]
    best_market_conditions: List[str]
    worst_market_conditions: List[str]

    # Explanation
    level: ExplanationLevel
    explanation_text: str


class StrategyExplainer:
    """
    Explain trading strategies in natural language.

    Generates human-readable explanations of strategy logic.
    """

    def __init__(self):
        self.explanation_templates = self._load_templates()
        logger.info("StrategyExplainer initialized")

    def _load_templates(self) -> Dict[str, str]:
        """Load explanation templates."""

        return {
            'momentum': """
The Momentum strategy ({name}) identifies assets that are trending strongly and
positions to benefit from continued price movement.

**How it works:**
{logic}

**Entry signals:**
{entry}

**Exit signals:**
{exit}

**Risk management:**
{risk}

**Performance:** The strategy has returned {return:.2%} with a Sharpe ratio of {sharpe:.2f}.
**Max drawdown:** {drawdown:.2%}
""",

            'mean_reversion': """
The Mean Reversion strategy ({name}) identifies assets that have moved too far
from their fair value and positions for a reversal.

**How it works:**
{logic}

**Entry signals:**
{entry}

**Exit signals:**
{exit}

**Risk management:**
{risk}

**Performance:** The strategy has returned {return:.2%} with a Sharpe ratio of {sharpe:.2f}.
**Max drawdown:** {drawdown:.2%}
""",

            'trend_following': """
The Trend Following strategy ({name}) identifies established trends and positions
to ride the trend until evidence of reversal.

**How it works:**
{logic}

**Entry signals:**
{entry}

**Exit signals:**
{exit}

**Risk management:**
{risk}

**Performance:** The strategy has returned {return:.2%} with a Sharpe ratio of {sharpe:.2f}.
**Max drawdown:** {drawdown:.2%}
""",

            'arbitrage': """
The Arbitrage strategy ({name}) identifies price discrepancies between related
assets or markets and positions to profit from convergence.

**How it works:**
{logic}

**Entry signals:**
{entry}

**Exit signals:**
{exit}

**Risk management:**
{risk}

**Performance:** The strategy has returned {return:.2%} with a Sharpe ratio of {sharpe:.2f}.
**Max drawdown:** {drawdown:.2%}
"""
        }

    async def explain_strategy(
        self,
        strategy_data: Dict[str, Any],
        level: ExplanationLevel = ExplanationLevel.INTERMEDIATE
    ) -> StrategyExplanation:
        """
        Generate strategy explanation.

        Args:
            strategy_data: Strategy information
            level: Explanation detail level

        Returns:
            Strategy explanation
        """

        strategy_name = strategy_data.get('name', 'Unknown Strategy')
        strategy_type = strategy_data.get('type', 'momentum')

        # Generate components
        entry_conditions = self._explain_entry_conditions(strategy_data, level)
        exit_conditions = self._explain_exit_conditions(strategy_data, level)
        risk_management = self._explain_risk_management(strategy_data, level)

        # Generate logic explanation
        logic = self._explain_logic(strategy_data, level)

        # Performance insights
        historical_performance = strategy_data.get('performance', {})
        risk_metrics = strategy_data.get('risk_metrics', {})

        # Generate strengths and weaknesses
        strengths = self._identify_strengths(strategy_data, historical_performance)
        weaknesses = self._identify_weaknesses(strategy_data, risk_metrics)

        # Market conditions
        best_conditions = self._identify_best_conditions(strategy_data, strategy_type)
        worst_conditions = self._identify_worst_conditions(strategy_data, strategy_type)

        # Generate explanation text
        template = self.explanation_templates.get(strategy_type, self.explanation_templates['momentum'])
        explanation_text = template.format(
            name=strategy_name,
            logic=logic,
            entry='\n'.join([f"• {e}" for e in entry_conditions]),
            exit='\n'.join([f"• {e}" for e in exit_conditions]),
            risk='\n'.join([f"• {r}" for r in risk_management]),
            return=historical_performance.get('total_return', 0),
            sharpe=historical_performance.get('sharpe_ratio', 0),
            drawdown=risk_metrics.get('max_drawdown', 0)
        )

        return StrategyExplanation(
            strategy_name=strategy_name,
            strategy_type=strategy_type,
            description=strategy_data.get('description', ''),
            entry_conditions=entry_conditions,
            exit_conditions=exit_conditions,
            risk_management=risk_management,
            historical_performance=historical_performance,
            risk_metrics=risk_metrics,
            strengths=strengths,
            weaknesses=weaknesses,
            best_market_conditions=best_conditions,
            worst_market_conditions=worst_conditions,
            level=level,
            explanation_text=explanation_text
        )

    def _explain_entry_conditions(
        self,
        strategy_data: Dict[str, Any],
        level: ExplanationLevel
    ) -> List[str]:
        """Explain entry conditions."""

        conditions = []

        if level == ExplanationLevel.BASIC:
            conditions.append("Buy when the strategy identifies a favorable setup")
            conditions.append("Entry is based on technical indicators")

        elif level in [ExplanationLevel.INTERMEDIATE, ExplanationLevel.ADVANCED, ExplanationLevel.EXPERT]:
            # Extract actual entry conditions
            indicators = strategy_data.get('indicators', {})

            for indicator, params in indicators.items():
                if indicator == 'rsi':
                    conditions.append(f"RSI indicates {'oversold' if params.get('buy_threshold', 30) < 50 else 'overbought'} condition")
                elif indicator == 'macd':
                    conditions.append(f"MACD shows {'bullish' if params.get('signal', 'crossover') == 'bullish' else 'bearish'} crossover")
                elif indicator == 'moving_average':
                    conditions.append(f"Price crosses {'above' if params.get('direction', 'up') == 'up' else 'below'} moving average")
                elif indicator == 'bollinger_bands':
                    conditions.append(f"Price touches {'lower' if params.get('band', 'lower') == 'lower' else 'upper'} Bollinger Band")

        return conditions

    def _explain_exit_conditions(
        self,
        strategy_data: Dict[str, Any],
        level: ExplanationLevel
    ) -> List[str]:
        """Explain exit conditions."""

        conditions = []

        if level == ExplanationLevel.BASIC:
            conditions.append("Exit when profit target is reached")
            conditions.append("Exit when stop-loss is triggered")
            conditions.append("Exit when signal reverses")

        else:
            # Extract actual exit conditions
            exit_rules = strategy_data.get('exit_rules', {})

            if 'take_profit' in exit_rules:
                tp = exit_rules['take_profit']
                conditions.append(f"Take profit at {tp:.2%} gain")

            if 'stop_loss' in exit_rules:
                sl = exit_rules['stop_loss']
                conditions.append(f"Stop loss at {sl:.2%} loss")

            if 'trailing_stop' in exit_rules:
                ts = exit_rules['trailing_stop']
                conditions.append(f"Trailing stop at {ts:.2%} from peak")

            if 'signal_reversal' in exit_rules:
                conditions.append("Exit when primary indicator reverses")

            if 'time_exit' in exit_rules:
                days = exit_rules['time_exit']
                conditions.append(f"Exit after {days} days if no target hit")

        return conditions

    def _explain_risk_management(
        self,
        strategy_data: Dict[str, Any],
        level: ExplanationLevel
    ) -> List[str]:
        """Explain risk management."""

        risk = []

        if level == ExplanationLevel.BASIC:
            risk.append("Position sizes are limited to manage risk")
            risk.append("Stop-losses protect against large losses")

        else:
            risk_params = strategy_data.get('risk_management', {})

            if 'position_size' in risk_params:
                ps = risk_params['position_size']
                risk.append(f"Maximum position size: {ps:.2%} of capital")

            if 'max_drawdown' in risk_params:
                mdd = risk_params['max_drawdown']
                risk.append(f"Maximum drawdown limit: {mdd:.2%}")

            if 'portfolio_heat' in risk_params:
                ph = risk_params['portfolio_heat']
                risk.append(f"Portfolio heat limit: {ph:.2%}")

            if 'correlation_limit' in risk_params:
                cl = risk_params['correlation_limit']
                risk.append(f"Correlation limit: {cl:.2%}")

        return risk

    def _explain_logic(
        self,
        strategy_data: Dict[str, Any],
        level: ExplanationLevel
    ) -> str:
        """Explain strategy logic."""

        strategy_type = strategy_data.get('type', 'momentum')

        if strategy_type == 'momentum':
            return """
The strategy uses technical indicators to identify assets with strong momentum.
It calculates momentum scores using:
- Price rate of change
- Volume confirmation
- Trend strength indicators

When momentum exceeds thresholds and other conditions are met, the strategy enters
a position expecting the trend to continue.
"""

        elif strategy_type == 'mean_reversion':
            return """
The strategy identifies assets that have deviated significantly from their mean
price. It uses:
- Z-score calculations
- Bollinger Bands
- Mean reversion indicators

When prices extend beyond normal ranges (typically 2+ standard deviations),
the strategy expects a reversion to the mean.
"""

        elif strategy_type == 'trend_following':
            return """
The strategy identifies established trends using moving average crossovers and
trend strength indicators. It enters when:
- Short-term MA crosses long-term MA
- Trend is confirmed by volume
- Price momentum is positive

It exits when the trend shows signs of reversal.
"""

        elif strategy_type == 'arbitrage':
            return """
The strategy monitors price relationships between related assets. When prices
deviate beyond historical ranges, it:
- Identifies the mispricing
- Enters positions in both assets
- Exits when prices converge

This profits from statistical relationships without directional market exposure.
"""

        else:
            return "The strategy uses technical analysis to identify trading opportunities."

    def _identify_strengths(
        self,
        strategy_data: Dict[str, Any],
        performance: Dict[str, float]
    ) -> List[str]:
        """Identify strategy strengths."""

        strengths = []

        sharpe = performance.get('sharpe_ratio', 0)
        return_val = performance.get('total_return', 0)
        win_rate = performance.get('win_rate', 0)

        if sharpe > 1.0:
            strengths.append(f"Strong risk-adjusted returns (Sharpe: {sharpe:.2f})")
        if return_val > 0.2:
            strengths.append(f"High total return ({return_val:.2%})")
        if win_rate > 0.55:
            strengths.append(f"Above-average win rate ({win_rate:.1%})")

        strategy_type = strategy_data.get('type', '')
        if strategy_type == 'mean_reversion':
            strengths.append("Profits from market overreactions")
        elif strategy_type == 'momentum':
            strengths.append("Captures sustained trends")
        elif strategy_type == 'arbitrage':
            strengths.append("Market-neutral returns")
            strengths.append("Low correlation to market direction")

        return strengths or ["Strategy has identified positive edge"]

    def _identify_weaknesses(
        self,
        strategy_data: Dict[str, Any],
        risk_metrics: Dict[str, float]
    ) -> List[str]:
        """Identify strategy weaknesses."""

        weaknesses = []

        max_dd = risk_metrics.get('max_drawdown', 0)
        volatility = risk_metrics.get('volatility', 0)

        if max_dd > 0.2:
            weaknesses.append(f"Deep drawdowns ({max_dd:.2%})")
        if volatility > 0.3:
            weaknesses.append(f"High volatility ({volatility:.2%})")

        strategy_type = strategy_data.get('type', '')
        if strategy_type == 'momentum':
            weaknesses.append("Vulnerable to sudden trend reversals")
            weaknesses.append("Underperforms in choppy/sideways markets")
        elif strategy_type == 'mean_reversion':
            weaknesses.append("Suffers during strong trends")
            weaknesses.append("Can be caught in false reversals")
        elif strategy_type == 'trend_following':
            weaknesses.append("Whipsaws in range-bound markets")
            weaknesses.append("Late entry and exit signals")

        return weaknesses or ["No significant weaknesses identified"]

    def _identify_best_conditions(
        self,
        strategy_data: Dict[str, Any],
        strategy_type: str
    ) -> List[str]:
        """Identify best market conditions."""

        if strategy_type == 'momentum':
            return [
                "Strong directional trends",
                "High volatility with clear direction",
                "Volume confirmation"
            ]
        elif strategy_type == 'mean_reversion':
            return [
                "Range-bound markets",
                "Oscillating price action",
                "Clear mean-reverting tendencies"
            ]
        elif strategy_type == 'trend_following':
            return [
                "Sustained trends",
                "Low noise in price action",
                "Trend persistence"
            ]
        elif strategy_type == 'arbitrage':
            return [
                "High market liquidity",
                "Stable correlation relationships",
                "Efficient execution"
            ]
        else:
            return ["Favorable market conditions"]

    def _identify_worst_conditions(
        self,
        strategy_data: Dict[str, Any],
        strategy_type: str
    ) -> List[str]:
        """Identify worst market conditions."""

        if strategy_type == 'momentum':
            return [
                "Sideways/choppy markets",
                "Sudden regime changes",
                "Low volatility"
            ]
        elif strategy_type == 'mean_reversion':
            return [
                "Strong trending markets",
                "Momentum spikes",
                "Breakout conditions"
            ]
        elif strategy_type == 'trend_following':
            return [
                "Whipsaw markets",
                "Frequent trend reversals",
                "High noise"
            ]
        elif strategy_type == 'arbitrage':
            return [
                "Low liquidity",
                "Correlation breakdown",
                "Wide spreads"
            ]
        else:
            return ["Adverse market conditions"]


class PerformanceExplainer:
    """
    Explain performance attribution and drivers.

    Helps users understand why strategies performed as they did.
    """

    def __init__(self):
        logger.info("PerformanceExplainer initialized")

    async def explain_performance(
        self,
        strategy_name: str,
        returns: pd.Series,
        benchmark_returns: pd.Series,
        level: ExplanationLevel = ExplanationLevel.INTERMEDIATE
    ) -> str:
        """
        Explain strategy performance.

        Args:
            strategy_name: Strategy name
            returns: Strategy returns
            benchmark_returns: Benchmark returns
            level: Explanation detail level

        Returns:
            Performance explanation
        """

        # Calculate metrics
        total_return = (1 + returns).prod() - 1
        benchmark_return = (1 + benchmark_returns).prod() - 1
        excess_return = total_return - benchmark_return

        sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        benchmark_sharpe = benchmark_returns.mean() / benchmark_returns.std() * np.sqrt(252) if benchmark_returns.std() > 0 else 0

        # Calculate rolling metrics
        rolling_sharpe = returns.rolling(63).apply(
            lambda x: x.mean() / x.std() * np.sqrt(252) if x.std() > 0 else 0
        )

        # Generate explanation
        if level == ExplanationLevel.BASIC:
            explanation = f"""
**Performance Summary for {strategy_name}:**

The strategy returned {total_return:.2%} vs {benchmark_return:.2%} for the benchmark,
generating {excess_return:.2%} alpha.

Risk-adjusted performance (Sharpe ratio): {sharpe:.2f} vs {benchmark_sharpe:.2f} for benchmark.

**Key Takeaways:**
- {'✓ Outperformed' if excess_return > 0 else '✗ Underperformed'} benchmark by {abs(excess_return):.2%}
- {'✓ Superior' if sharpe > benchmark_sharpe else '✗ Inferior'} risk-adjusted returns
- Volatility: {returns.std() * np.sqrt(252):.2%} annualized
"""

        else:
            # More detailed explanation
            win_rate = (returns > 0).mean()
            avg_win = returns[returns > 0].mean() if win_rate > 0 else 0
            avg_loss = returns[returns < 0].mean() if win_rate < 1 else 0

            # Max drawdown
            cumulative = (1 + returns).cumprod()
            running_max = cumulative.cummax()
            drawdown = (cumulative - running_max) / running_max
            max_dd = abs(drawdown.min())

            # Best and worst periods
            best_month = returns.resample('M').sum().max()
            worst_month = returns.resample('M').sum().min()

            explanation = f"""
**Detailed Performance Analysis: {strategy_name}**

**Return Metrics:**
- Total Return: {total_return:.2%}
- Benchmark Return: {benchmark_return:.2%}
- Alpha (Excess Return): {excess_return:.2%}
- Annualized Return: {returns.mean() * 252:.2%}

**Risk Metrics:**
- Volatility (Annual): {returns.std() * np.sqrt(252):.2%}
- Sharpe Ratio: {sharpe:.2f}
- Benchmark Sharpe: {benchmark_sharpe:.2f}
- Maximum Drawdown: {max_dd:.2%}
- VaR (95%): {returns.quantile(0.05):.4f}

**Trading Statistics:**
- Win Rate: {win_rate:.1%}
- Average Win: {avg_win:.4f}
- Average Loss: {avg_loss:.4f}
- Profit Factor: {abs(avg_win / avg_loss) if avg_loss != 0 else 0:.2f}

**Period Analysis:**
- Best Month: {best_month:.2%}
- Worst Month: {worst_month:.2%}

**Performance Drivers:**
"""

            # Analyze performance drivers
            if excess_return > 0:
                explanation += f"- Positive alpha of {excess_return:.2%} indicates genuine skill\n"
            else:
                explanation += f"- Negative alpha suggests strategy underperformed\n"

            if sharpe > benchmark_sharpe:
                explanation += f"- Superior risk-adjusted returns ({sharpe:.2f} vs {benchmark_sharpe:.2f})\n"

            if max_dd < 0.15:
                explanation += f"- Controlled drawdown ({max_dd:.2%}) indicates good risk management\n"
            else:
                explanation += f"- Large drawdown ({max_dd:.2%}) suggests room for risk improvement\n"

        return explanation


class MetricExplainer:
    """
    Explain financial metrics and concepts.

    Helps users understand complex financial terminology.
    """

    def __init__(self):
        self.metric_definitions = self._load_definitions()
        logger.info("MetricExplainer initialized")

    def _load_definitions(self) -> Dict[str, str]:
        """Load metric definitions."""

        return {
            'sharpe_ratio': """
**Sharpe Ratio:** Measures risk-adjusted returns.

**Formula:** (Return - Risk Free Rate) / Volatility

**Interpretation:**
- > 2.0: Excellent
- 1.0 - 2.0: Good
- 0.5 - 1.0: Fair
- < 0.5: Poor

**What it tells you:** How much return you're getting for each unit of risk taken.
Higher is better. A Sharpe of 1.0 means you're earning 1 unit of return for each
unit of risk.
""",

            'sortino_ratio': """
**Sortino Ratio:** Similar to Sharpe but only penalizes downside risk.

**Formula:** (Return - Risk Free Rate) / Downside Deviation

**Interpretation:** Same scale as Sharpe ratio.

**What it tells you:** Like Sharpe, but focuses only on "bad" volatility (downside).
Useful when returns are skewed (large gains are OK, large losses are bad).
""",

            'var': """
**Value at Risk (VaR):** Maximum expected loss at a confidence level.

**Example:** VaR at 95% = -3% means there's a 5% chance of losing >3% in a period.

**Limitations:**
- Doesn't tell you how bad losses can be beyond VaR
- Assumes normal distribution (often wrong)
- Use CVaR for better tail risk assessment

**What it tells you:** The minimum loss to expect in bad scenarios (worst 5% of cases).
""",

            'cvar': """
**Conditional Value at Risk (CVaR):** Average loss beyond VaR (Expected Shortfall).

**Example:** CVaR at 95% = -5% means when things go bad (worst 5%), average loss is 5%.

**Advantages over VaR:**
- Accounts for tail risk
- Tells you expected loss in worst cases
- Better for risk management

**What it tells you:** In the worst 5% of cases, this is your average loss.
""",

            'max_drawdown': """
**Maximum Drawdown:** Largest peak-to-trough decline.

**Example:** Max DD of 20% means portfolio lost 20% from peak at worst point.

**Interpretation:**
- < 10%: Excellent
- 10% - 20%: Good
- 20% - 30%: Fair
- > 30%: Poor

**What it tells you:** The worst loss you would have experienced if you invested
at the worst possible time (the peak) and sold at the worst possible time (the trough).
""",

            'win_rate': """
**Win Rate:** Percentage of trades that are profitable.

**Formula:** Winning Trades / Total Trades

**Interpretation:**
- > 60%: Excellent
- 55% - 60%: Good
- 50% - 55%: Fair
- < 50%: Poor (but can still be profitable if wins > losses)

**What it tells you:** How often the strategy wins. But win rate alone doesn't
determine profitability — you also need average win vs average loss.
""",

            'profit_factor': """
**Profit Factor:** Ratio of total wins to total losses.

**Formula:** Total Winning Trades / Total Losing Trades

**Interpretation:**
- > 2.0: Excellent
- 1.5 - 2.0: Good
- 1.0 - 1.5: Fair
- < 1.0: Poor (losing money)

**What it tells you:** For every $1 lost, how much is won. Profit factor of 1.5
means winning $1.50 for every $1.00 lost.
""",

            'alpha': """
**Alpha:** Excess return over benchmark.

**Formula:** Strategy Return - Benchmark Return

**Interpretation:**
- > 0: Outperforming benchmark
- < 0: Underperforming benchmark

**What it tells you:** The value added (or lost) by the strategy beyond what
you'd get from simply holding the benchmark. Positive alpha = genuine skill.
""",

            'beta': """
**Beta:** Sensitivity to market movements.

**Formula:** Covariance(Strategy, Market) / Variance(Market)

**Interpretation:**
- 1.0: Moves with market
- > 1.0: More volatile than market
- < 1.0: Less volatile than market
- 0.0: Uncorrelated with market

**What it tells you:** How much the strategy moves when the market moves 1%.
Beta of 1.5 means strategy typically moves 1.5% when market moves 1%.
"""
        }

    def explain_metric(self, metric_name: str) -> str:
        """
        Explain a financial metric.

        Args:
            metric_name: Name of metric

        Returns:
            Metric explanation
        """

        metric_key = metric_name.lower().replace(' ', '_').replace('-', '_')

        if metric_key in self.metric_definitions:
            return self.metric_definitions[metric_key]
        else:
            return f"""
**{metric_name}**

No detailed explanation available for this metric.

For more information, please consult financial documentation or request
explanation of a specific metric from the following list:
{', '.join(sorted(self.metric_definitions.keys()))}
"""


class ExplainerEngine:
    """
    Unified explanatory engine.

    Combines all explanation capabilities.
    """

    def __init__(self):
        self.strategy_explainer = StrategyExplainer()
        self.performance_explainer = PerformanceExplainer()
        self.metric_explainer = MetricExplainer()

        logger.info("ExplainerEngine initialized")

    async def explain(
        self,
        query_type: str,
        data: Dict[str, Any],
        level: ExplanationLevel = ExplanationLevel.INTERMEDIATE
    ) -> str:
        """
        Generate explanation.

        Args:
            query_type: Type of explanation
            data: Data to explain
            level: Detail level

        Returns:
            Explanation text
        """

        if query_type == 'strategy':
            explanation = await self.strategy_explainer.explain_strategy(data, level)
            return explanation.explanation_text

        elif query_type == 'performance':
            return await self.performance_explainer.explain_performance(
                data.get('strategy_name', 'Strategy'),
                data.get('returns', pd.Series()),
                data.get('benchmark_returns', pd.Series()),
                level
            )

        elif query_type == 'metric':
            return self.metric_explainer.explain_metric(data.get('metric_name', ''))

        else:
            return "Unknown explanation type"


# Singleton instance
_explainer_engine = None


def get_explainer_engine() -> ExplainerEngine:
    """Get or create explainer engine instance."""
    global _explainer_engine
    if _explainer_engine is None:
        _explainer_engine = ExplainerEngine()
    return _explainer_engine
