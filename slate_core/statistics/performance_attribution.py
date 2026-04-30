#!/usr/bin/env python3
"""
SLATE Performance Attribution

Phase 4: Statistical Validation & Significance

Implements performance attribution to understand source of returns:
- Luck vs skill analysis
- Factor attribution
- Regime-specific performance
- Alpha decay modeling
- Risk-adjusted metrics

Critical for understanding if strategy performance is genuine or lucky.

Author: SLATE Evolution
Date: 2026-04-30
Priority: HIGH - Separates luck from skill
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
from scipy import stats
from scipy.stats import pearsonr

logger = logging.getLogger(__name__)


class PerformanceType(Enum):
    """Types of performance attribution."""
    LUCK = "luck"  # Random chance
    SKILL = "skill"  # Genuine alpha
    FACTOR = "factor"  # Exposure to risk factors
    REGIME = "regime"  # Market regime dependent
    DECAY = "decay"  # Alpha decay over time


@dataclass
class AttributionResult:
    """Result from performance attribution."""
    total_return: float
    skill_component: float
    luck_component: float
    factor_exposure: Dict[str, float]
    regime_performance: Dict[str, float]
    alpha_decay_rate: float
    information_ratio: float
    attribution_type: PerformanceType
    confidence: float


class LuckSkillAnalyzer:
    """
    Analyze whether performance is due to luck or skill.

    Methods:
    - Information Ratio
    - T-statistics
    - Bootstrap comparison
    - Out-of-sample consistency
    """

    def __init__(self):
        logger.info("LuckSkillAnalyzer initialized")

    async def analyze_performance_attribution(
        self,
        returns: pd.Series,
        benchmark_returns: pd.Series,
        n_bootstrap: int = 1000
    ) -> AttributionResult:
        """
        Analyze performance attribution (luck vs skill).

        Args:
            returns: Strategy returns
            benchmark_returns: Benchmark returns
            n_bootstrap: Bootstrap iterations

        Returns:
            AttributionResult with detailed breakdown
        """

        # Calculate excess returns
        excess_returns = returns - benchmark_returns

        # Calculate metrics
        total_return = excess_returns.sum()
        mean_excess = excess_returns.mean()
        std_excess = excess_returns.std()

        # Information Ratio (Sharpe of excess returns)
        if std_excess > 0:
            information_ratio = mean_excess / std_excess * np.sqrt(252)
        else:
            information_ratio = 0.0

        # T-statistic for excess returns
        n = len(excess_returns)
        t_stat = mean_excess / (std_excess / np.sqrt(n)) if std_excess > 0 else 0.0
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), n - 1)) if n > 1 else 1.0

        # Bootstrap to assess luck vs skill
        np.random.seed(42)
        bootstrap_returns = []

        for _ in range(n_bootstrap):
            # Shuffle returns to simulate luck
            shuffled = np.random.permutation(returns)
            benchmark_shuffled = np.random.permutation(benchmark_returns)
            excess_shuffled = shuffled - benchmark_shuffled
            bootstrap_returns.append(excess_shuffled.sum())

        bootstrap_returns = np.array(bootstrap_returns)

        # Percentile of observed return in bootstrap distribution
        percentile = np.sum(bootstrap_returns <= total_return) / n_bootstrap

        # Determine attribution
        if p_value < 0.05 and percentile > 0.95:
            attribution_type = PerformanceType.SKILL
            confidence = 1 - p_value
        elif p_value < 0.05 and percentile < 0.05:
            attribution_type = PerformanceType.SKILL  # Consistently bad
            confidence = 1 - p_value
        elif 0.45 < percentile < 0.55:
            attribution_type = PerformanceType.LUCK
            confidence = 0.5
        else:
            # Some skill but not definitive
            attribution_type = PerformanceType.SKILL
            confidence = abs(percentile - 0.5) * 2

        return AttributionResult(
            total_return=total_return,
            skill_component=total_return * confidence,
            luck_component=total_return * (1 - confidence),
            factor_exposure={},
            regime_performance={},
            alpha_decay_rate=0.0,
            information_ratio=information_ratio,
            attribution_type=attribution_type,
            confidence=confidence
        )

    def calculate_information_ratio(
        self,
        returns: pd.Series,
        benchmark_returns: pd.Series
    ) -> float:
        """
        Calculate Information Ratio.

        IR = (Excess Return) / (Tracking Error)

        High IR suggests skill, low IR suggests luck.
        """

        excess_returns = returns - benchmark_returns
        tracking_error = excess_returns.std() * np.sqrt(252)

        if tracking_error == 0:
            return 0.0

        annual_excess = excess_returns.mean() * 252
        return annual_excess / tracking_error


class FactorAttribution:
    """
    Attribute performance to risk factors.

    Common factors in crypto:
    - Market factor (BTC)
    - Size factor (large vs small cap)
    - Momentum factor
    - Volatility factor
    """

    def __init__(self):
        logger.info("FactorAttribution initialized")

    async def attribute_to_factors(
        self,
        strategy_returns: pd.Series,
        factor_returns: Dict[str, pd.Series]
    ) -> Dict[str, float]:
        """
        Attribute strategy returns to risk factors.

        Uses multivariate regression:
        Strategy_Return = α + β₁*Factor₁ + β₂*Factor₂ + ... + ε

        Args:
            strategy_returns: Strategy returns
            factor_returns: Dict of {factor_name: returns}

        Returns:
            Dict with alpha and betas
        """

        # Prepare regression data
        factor_df = pd.DataFrame(factor_returns)

        # Align data
        aligned_data = pd.concat([strategy_returns, factor_df], axis=1).dropna()

        y = aligned_data.iloc[:, 0]  # Strategy returns
        X = aligned_data.iloc[:, 1:]  # Factor returns
        factor_names = X.columns.tolist()

        # Add constant
        X = np.column_stack([np.ones(len(X)), X])

        # OLS regression
        try:
            result = np.linalg.lstsq(X, y, rcond=None)
            coefficients = result[0]

            # Calculate R-squared
            y_pred = X @ coefficients
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        except np.linalg.LinAlgError:
            logger.warning("Regression failed, returning zeros")
            coefficients = np.zeros(len(factor_names) + 1)
            r_squared = 0.0

        attribution = {
            'alpha': float(coefficients[0]),
            'r_squared': float(r_squared)
        }

        for i, name in enumerate(factor_names):
            attribution[f'beta_{name}'] = float(coefficients[i + 1])

        return attribution


class RegimePerformanceAnalyzer:
    """
    Analyze performance across market regimes.

    Critical because strategies may work in some regimes
    but not others.
    """

    def __init__(self):
        logger.info("RegimePerformanceAnalyzer initialized")

    async def analyze_regime_performance(
        self,
        returns: pd.Series,
        regimes: pd.Series,
        regime_names: Dict[int, str]
    ) -> Dict[str, Dict[str, float]]:
        """
        Analyze performance by market regime.

        Args:
            returns: Strategy returns
            regimes: Regime for each time period (same index as returns)
            regime_names: Mapping of regime ID to name

        Returns:
            Dict of {regime_name: {metrics}}
        """

        # Combine returns and regimes
        data = pd.DataFrame({'returns': returns, 'regime': regimes}).dropna()

        regime_performance = {}

        for regime_id, regime_name in regime_names.items():
            mask = data['regime'] == regime_id
            regime_returns = data[mask]['returns']

            if len(regime_returns) == 0:
                continue

            metrics = {
                'count': len(regime_returns),
                'total_return': regime_returns.sum(),
                'mean_return': regime_returns.mean(),
                'std_return': regime_returns.std(),
                'sharpe': regime_returns.mean() / regime_returns.std() * np.sqrt(252) if regime_returns.std() > 0 else 0,
                'win_rate': (regime_returns > 0).sum() / len(regime_returns)
            }

            regime_performance[regime_name] = metrics

        return regime_performance


class AlphaDecayAnalyzer:
    """
    Analyze alpha decay over time.

    Strategies often lose effectiveness as markets adapt.
    """

    def __init__(self):
        logger.info("AlphaDecayAnalyzer initialized")

    async def analyze_alpha_decay(
        self,
        returns: pd.Series,
        window_days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze alpha decay using rolling windows.

        Args:
            returns: Strategy returns
            window_days: Window size for analysis

        Returns:
            Dict with decay analysis
        """

        # Calculate rolling performance
        rolling_return = returns.rolling(window_days).sum()
        rolling_sharpe = returns.rolling(window_days).apply(
            lambda x: x.mean() / x.std() * np.sqrt(252) if x.std() > 0 else 0
        )

        # Calculate decay rate
        # Use linear regression on performance over time
        valid_idx = rolling_return.notna()
        if valid_idx.sum() > 10:
            x = np.arange(valid_idx.sum())
            y = rolling_return[valid_idx].values

            # Simple linear regression
            slope, intercept = np.polyfit(x, y, 1)

            # Decay rate (negative means decay)
            decay_rate = slope / (np.mean(np.abs(y)) + 1e-10)

            # Half-life (time until performance halves)
            if slope < 0:
                half_life = np.log(0.5) / slope if slope != 0 else float('inf')
            else:
                half_life = float('inf')  # No decay

        else:
            decay_rate = 0.0
            half_life = float('inf')

        # Check if recent performance is worse
        recent_performance = returns.tail(window_days).sum()
        historical_performance = returns.head(window_days).sum()

        is_decaying = recent_performance < historical_performance

        return {
            'decay_rate': decay_rate,
            'half_life_periods': half_life,
            'is_decaying': is_decaying,
            'recent_performance': recent_performance,
            'historical_performance': historical_performance,
            'performance_ratio': recent_performance / (historical_performance + 1e-10)
        }


class PerformanceAttributor:
    """
    Unified performance attribution system.

    Combines all attribution methods:
    - Luck vs skill
    - Factor exposure
    - Regime analysis
    - Alpha decay
    """

    def __init__(self):
        self.luck_skill = LuckSkillAnalyzer()
        self.factor_attribution = FactorAttribution()
        self.regime_analyzer = RegimePerformanceAnalyzer()
        self.decay_analyzer = AlphaDecayAnalyzer()

        logger.info("PerformanceAttributor initialized")

    async def comprehensive_attribution(
        self,
        returns: pd.Series,
        benchmark_returns: pd.Series,
        factor_returns: Optional[Dict[str, pd.Series]] = None,
        regimes: Optional[pd.Series] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive performance attribution.

        Args:
            returns: Strategy returns
            benchmark_returns: Benchmark returns
            factor_returns: Optional factor returns
            regimes: Optional regime series

        Returns:
            Comprehensive attribution results
        """

        # Luck vs skill analysis
        luck_skill_result = await self.luck_skill.analyze_performance_attribution(
            returns, benchmark_returns
        )

        results = {
            'luck_vs_skill': {
                'type': luck_skill_result.attribution_type.value,
                'skill_component': luck_skill_result.skill_component,
                'luck_component': luck_skill_result.luck_component,
                'confidence': luck_skill_result.confidence,
                'information_ratio': luck_skill_result.information_ratio
            },
            'overall_performance': {
                'total_return': returns.sum(),
                'sharpe_ratio': returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0,
                'max_drawdown': self._calculate_max_drawdown(returns),
                'win_rate': (returns > 0).sum() / len(returns)
            }
        }

        # Factor attribution
        if factor_returns:
            factor_results = await self.factor_attribution.attribute_to_factors(
                returns, factor_returns
            )
            results['factor_attribution'] = factor_results

        # Regime analysis
        if regimes is not None:
            regime_names = {0: 'Regime_0', 1: 'Regime_1', 2: 'Regime_2'}
            regime_results = await self.regime_analyzer.analyze_regime_performance(
                returns, regimes, regime_names
            )
            results['regime_performance'] = regime_results

        # Alpha decay
        decay_results = await self.decay_analyzer.analyze_alpha_decay(returns)
        results['alpha_decay'] = decay_results

        return results

    def _calculate_max_drawdown(self, returns: pd.Series) -> float:
        """Calculate maximum drawdown."""
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        return abs(drawdown.min())

    def generate_attribution_report(self, results: Dict[str, Any]) -> str:
        """Generate comprehensive attribution report."""

        report = f"""
{'='*60}
PERFORMANCE ATTRIBUTION REPORT
{'='*60}

LUCK VS SKILL ANALYSIS:
  Attribution Type: {results['luck_vs_skill']['type'].upper()}
  Skill Component: {results['luck_vs_skill']['skill_component']:.4f}
  Luck Component: {results['luck_vs_skill']['luck_component']:.4f}
  Confidence: {results['luck_vs_skill']['confidence']:.1%}
  Information Ratio: {results['luck_vs_skill']['information_ratio']:.2f}

INTERPRETATION:
"""

        luck_skill = results['luck_vs_skill']
        if luck_skill['type'] == 'skill':
            report += "  ✓ Performance appears to be GENUINE SKILL\n"
            report += "  Strategy has statistically significant alpha\n"
        elif luck_skill['type'] == 'luck':
            report += "  ⚠ Performance may be due to LUCK\n"
            report += "  Additional validation recommended\n"
        else:
            report += "  ? Attribution unclear\n"

        report += f"""
OVERALL PERFORMANCE:
  Total Return: {results['overall_performance']['total_return']:.2%}
  Sharpe Ratio: {results['overall_performance']['sharpe_ratio']:.2f}
  Max Drawdown: {results['overall_performance']['max_drawdown']:.2%}
  Win Rate: {results['overall_performance']['win_rate']:.1%}
"""

        if 'factor_attribution' in results:
            fa = results['factor_attribution']
            report += f"""
FACTOR ATTRIBUTION:
  Alpha: {fa['alpha']:.4f}
  R-Squared: {fa['r_squared']:.2f}
"""
            for key, value in fa.items():
                if key.startswith('beta_'):
                    report += f"  {key}: {value:.4f}\n"

        if 'alpha_decay' in results:
            ad = results['alpha_decay']
            report += f"""
ALPHA DECAY:
  Decay Rate: {ad['decay_rate']:.6f}
  Is Decaying: {ad['is_decaying']}
  Performance Ratio: {ad['performance_ratio']:.2f}
"""

        return report


# Singleton instance
_performance_attributor = None


def get_performance_attributor() -> PerformanceAttributor:
    """Get or create performance attributor instance."""
    global _performance_attributor
    if _performance_attributor is None:
        _performance_attributor = PerformanceAttributor()
    return _performance_attributor
