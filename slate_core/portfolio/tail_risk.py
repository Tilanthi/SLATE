#!/usr/bin/env python3
"""
SLATE Tail Risk Management System

Phase 6: PnL Portfolio Management (Weeks 21-24)

Implements tail risk protection:
- Extreme Value Theory (EVT)
- Stress testing
- Black swan protection
- Crash protection strategies

Critical for surviving extreme market events.

Author: SLATE Evolution
Date: 2026-04-30
Priority: HIGH - Tail risk protection
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
from scipy.stats import genpareto, norm

logger = logging.getLogger(__name__)


class RiskEvent(Enum):
    """Types of risk events."""
    NORMAL = "normal"  # Normal market conditions
    STRESS = "stress"  # Stress conditions
    CRASH = "crash"  # Market crash
    BLACK_SWAN = "black_swan"  # Extreme outlier


@dataclass
class TailRiskMetrics:
    """Tail risk metrics."""
    var_95: float  # Value at Risk at 95%
    var_99: float  # Value at Risk at 99%
    cvar_95: float  # Conditional VaR at 95%
    cvar_99: float  # Conditional VaR at 99%
    expected_shortfall: float  # Expected shortfall
    max_drawdown: float  # Maximum historical drawdown

    # EVT-specific
    evt_var_99: float  # EVT-based VaR
    evt_cvar_99: float  # EVT-based CVaR
    extreme_threshold: float  # Threshold for extreme values

    # Risk indicators
    tail_index: float  # Heavy-tailedness (<0.5 = very heavy)
    skewness: float  # Return skewness
    kurtosis: float  # Return kurtosis (excess)

    # Current status
    current_regime: RiskEvent
    probability_of_crash: float


class StressTest:
    """
    Stress testing for extreme scenarios.

    Tests portfolio resilience under adverse conditions.
    """

    def __init__(self):
        self.scenarios = self._default_scenarios()
        logger.info("StressTest initialized")

    def _default_scenarios(self) -> Dict[str, Dict[str, float]]:
        """Default stress test scenarios."""

        return {
            'flash_crash_1987': {
                'description': '1987 Black Monday',
                'equity_drop': -0.22,
                'volatility_spike': 3.0,
                'correlation_increase': 0.9
            },
            'dot_com_bubble': {
                'description': '2000 Dot-com crash',
                'equity_drop': -0.15,
                'volatility_spike': 2.0,
                'correlation_increase': 0.8
            },
            'financial_crisis_2008': {
                'description': '2008 Financial Crisis',
                'equity_drop': -0.20,
                'volatility_spike': 2.5,
                'correlation_increase': 0.95
            },
            'covid_crash_2020': {
                'description': '2020 COVID Crash',
                'equity_drop': -0.30,
                'volatility_spike': 4.0,
                'correlation_increase': 0.95
            },
            'crypto_winter': {
                'description': 'Crypto bear market',
                'equity_drop': -0.50,
                'volatility_spike': 2.0,
                'correlation_increase': 0.85
            },
            'liquidity_crisis': {
                'description': 'Liquidity crisis',
                'equity_drop': -0.10,
                'volatility_spike': 3.0,
                'correlation_increase': 1.0,
                'spread_widening': 5.0  # Bps
            }
        }

    async def run_stress_test(
        self,
        portfolio_value: float,
        returns: pd.DataFrame,
        weights: np.ndarray,
        custom_scenarios: Optional[Dict[str, Dict[str, float]]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Run stress tests on portfolio.

        Args:
            portfolio_value: Current portfolio value
            returns: Historical returns
            weights: Portfolio weights
            custom_scenarios: Custom stress scenarios

        Returns:
            Stress test results
        """

        scenarios = custom_scenarios or self.scenarios
        results = {}

        # Calculate portfolio statistics
        portfolio_returns = returns @ weights
        portfolio_vol = portfolio_returns.std() * np.sqrt(252)

        for scenario_name, scenario in scenarios.items():
            # Apply scenario shocks
            equity_shock = scenario['equity_drop']
            vol_spike = scenario['volatility_spike']

            # Calculate stressed returns
            stressed_vol = portfolio_vol * vol_spike
            stressed_return = equity_shock

            # Calculate portfolio impact
            stressed_value = portfolio_value * (1 + stressed_return)

            # Additional correlation effect
            if 'correlation_increase' in scenario:
                # Higher correlation → higher portfolio vol
                corr_effect = scenario['correlation_increase']
                stressed_vol *= (1 + corr_effect * 0.2)  # 20% additional vol

            # Calculate VaR under stress
            stressed_var_95 = stressed_value * (1 - 1.645 * stressed_vol / np.sqrt(252))

            results[scenario_name] = {
                'description': scenario['description'],
                'portfolio_value': portfolio_value,
                'stressed_value': stressed_value,
                'loss': portfolio_value - stressed_value,
                'loss_pct': (portfolio_value - stressed_value) / portfolio_value,
                'stressed_volatility': stressed_vol,
                'stressed_var_95': stressed_var_95,
                'worst_case_loss': stressed_value * 0.5  # Additional 50% drop
            }

        return results

    def generate_stress_test_report(
        self,
        results: Dict[str, Dict[str, Any]]
    ) -> str:
        """Generate stress test report."""

        report = f"""
{'='*60}
STRESS TEST RESULTS
{'='*60}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

SCENARIOS TESTED: {len(results)}

"""

        for scenario_name, result in results.items():
            report += f"""
{scenario_name.upper().replace('_', ' ')}:
  Description: {result['description']}
  Current Value: ${result['portfolio_value']:,.2f}
  Stressed Value: ${result['stressed_value']:,.2f}
  Loss: ${result['loss']:,.2f} ({result['loss_pct']:.2%})
  Stressed Vol: {result['stressed_volatility']:.2%}
  Stressed VaR (95%): ${result['stressed_var_95']:,.2f}
  Worst Case: ${result['worst_case_loss']:,.2f}
"""

        return report


class ExtremeValueTheory:
    """
    Extreme Value Theory for tail risk estimation.

    Uses Generalized Pareto Distribution to model tails.
    More accurate than normal distribution for extreme events.
    """

    def __init__(self, threshold_percentile: float = 0.90):
        self.threshold_percentile = threshold_percentile
        logger.info(f"EVT initialized (threshold={threshold_percentile:.2%})")

    def fit_tail(
        self,
        returns: pd.Series
    ) -> Tuple[float, float, float]:
        """
        Fit Generalized Pareto Distribution to tail.

        Args:
            returns: Return series

        Returns:
            (threshold, shape, scale) parameters
        """

        # Calculate threshold
        threshold = np.percentile(np.abs(returns), self.threshold_percentile * 100)

        # Extract exceedances
        exceedances = returns[np.abs(returns) > threshold].values
        exceedances = np.abs(exceedances) - threshold

        if len(exceedances) < 10:
            # Not enough data for EVT
            return threshold, 0.1, threshold * 0.5

        # Fit GPD
        try:
            shape, loc, scale = genpareto.fit(exceedances, floc=0)
            return threshold, shape, scale
        except Exception as e:
            logger.warning(f"EVT fit failed: {e}")
            return threshold, 0.1, threshold * 0.5

    def calculate_evt_var(
        self,
        threshold: float,
        shape: float,
        scale: float,
        n_exceedances: int,
        n_total: int,
        alpha: float = 0.99
    ) -> float:
        """
        Calculate EVT-based VaR.

        Args:
            threshold: Threshold parameter
            shape: Shape parameter (xi)
            scale: Scale parameter (beta)
            n_exceedances: Number of exceedances
            n_total: Total observations
            alpha: Confidence level

        Returns:
            EVT-based VaR
        """

        # Probability of exceedance
        p_exceed = n_exceedances / n_total

        try:
            if abs(shape) < 1e-6:
                # Exponential case (shape = 0)
                var = threshold + (scale * np.log((1 - alpha) / p_exceed))
            else:
                # GPD case
                var = threshold + (scale / shape) * (((p_exceed / (1 - alpha)) ** shape) - 1)

            return var
        except Exception as e:
            logger.warning(f"EVT VaR calculation failed: {e}")
            return threshold * 2

    def calculate_tail_metrics(
        self,
        returns: pd.Series
    ) -> TailRiskMetrics:
        """
        Calculate comprehensive tail risk metrics.

        Args:
            returns: Return series

        Returns:
            Tail risk metrics
        """

        # Fit EVT
        threshold, shape, scale = self.fit_tail(returns)
        n_exceedances = np.sum(np.abs(returns) > threshold)
        n_total = len(returns)

        # Calculate EVT-based VaR and CVaR
        evt_var_99 = self.calculate_evt_var(threshold, shape, scale, n_exceedances, n_total, 0.99)
        evt_var_95 = self.calculate_evt_var(threshold, shape, scale, n_exceedances, n_total, 0.95)

        # EVT-based CVaR (simplified)
        evt_cvar_99 = evt_var_99 * 1.5  # Rough approximation

        # Standard metrics
        var_95 = np.percentile(returns, 5)
        var_99 = np.percentile(returns, 1)
        cvar_95 = returns[returns <= var_95].mean()
        cvar_99 = returns[returns <= var_99].mean()

        # Maximum drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = abs(drawdown.min())

        # Distribution properties
        tail_index = abs(shape) if shape is not None else 0.5
        skewness = stats.skew(returns)
        kurtosis = stats.kurtosis(returns)  # Excess kurtosis

        # Current regime assessment
        current_return = returns.iloc[-1] if len(returns) > 0 else 0
        if abs(current_return) > threshold:
            current_regime = RiskEvent.CRASH if current_return < 0 else RiskEvent.BLACK_SWAN
        elif returns.std() * np.sqrt(252) > 0.4:
            current_regime = RiskEvent.STRESS
        else:
            current_regime = RiskEvent.NORMAL

        # Probability of crash (simplified)
        probability_of_crash = min(1.0, max(0.0, tail_index * 0.3))

        return TailRiskMetrics(
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            expected_shortfall=cvar_95,
            max_drawdown=max_drawdown,
            evt_var_99=evt_var_99,
            evt_cvar_99=evt_cvar_99,
            extreme_threshold=threshold,
            tail_index=tail_index,
            skewness=skewness,
            kurtosis=kurtosis,
            current_regime=current_regime,
            probability_of_crash=probability_of_crash
        )


class CrashProtection:
    """
    Crash protection strategies.

    Implements protection against extreme market moves.
    """

    def __init__(self):
        self.protection_level = 0.95  # Protect 95% of capital
        logger.info("CrashProtection initialized")

    async def calculate_hedge_ratio(
        self,
        portfolio_value: float,
        portfolio_volatility: float,
        protection_level: float = 0.95
    ) -> Dict[str, float]:
        """
        Calculate hedge ratios for crash protection.

        Args:
            portfolio_value: Current portfolio value
            portfolio_volatility: Portfolio volatility
            protection_level: Target protection level

        Returns:
            Hedge recommendations
        """

        # Calculate tail risk
        tail_risk = portfolio_volatility * 2.33  # 99% one-sided
        expected_loss = portfolio_value * tail_risk

        # Protection needed
        protection_needed = portfolio_value * (1 - protection_level)

        # Hedge ratio
        hedge_ratio = protection_needed / (expected_loss + 1e-10)
        hedge_ratio = min(1.0, max(0.0, hedge_ratio))

        return {
            'portfolio_value': portfolio_value,
            'protection_level': protection_level,
            'floor_value': portfolio_value * protection_level,
            'expected_tail_loss': expected_loss,
            'hedge_ratio': hedge_ratio,
            'hedge_notional': portfolio_value * hedge_ratio
        }

    def generate_protection_strategy(
        self,
        tail_metrics: TailRiskMetrics,
        portfolio_value: float
    ) -> Dict[str, Any]:
        """
        Generate crash protection strategy.

        Args:
            tail_metrics: Tail risk metrics
            portfolio_value: Portfolio value

        Returns:
            Protection strategy
        """

        # Assess risk level
        if tail_metrics.current_regime == RiskEvent.CRASH:
            risk_level = "CRITICAL"
            action = "REDUCE_POSITIONS"
        elif tail_metrics.current_regime == RiskEvent.STRESS:
            risk_level = "HIGH"
            action = "ACTIVATE_HEDGES"
        elif tail_metrics.probability_of_crash > 0.3:
            risk_level = "ELEVATED"
            action = "PREPARE_HEDGES"
        else:
            risk_level = "NORMAL"
            action = "MONITOR"

        # Protection recommendations
        if risk_level == "CRITICAL":
            recommendations = [
                "Reduce position sizes by 50%",
                "Activate protective puts",
                "Increase cash allocation to 40%",
                "Consider market-neutral strategies"
            ]
        elif risk_level == "HIGH":
            recommendations = [
                "Reduce position sizes by 25%",
                "Buy out-of-the-money puts",
                "Increase cash allocation to 20%",
                "Hedge with inverse ETFs"
            ]
        elif risk_level == "ELEVATED":
            recommendations = [
                "Review stop-loss levels",
                "Consider limited hedging",
                "Monitor for deterioration",
                "Prepare contingency plans"
            ]
        else:
            recommendations = [
                "Maintain current positions",
                "Regular monitoring",
                "Rebalance if needed",
                "Review risk limits"
            ]

        return {
            'risk_level': risk_level,
            'action': action,
            'recommendations': recommendations,
            'tail_risk_metrics': tail_metrics,
            'portfolio_value': portfolio_value
        }


class TailRiskManager:
    """
    Unified tail risk management system.

    Combines stress testing, EVT, and crash protection.
    """

    def __init__(self):
        self.evt = ExtremeValueTheory()
        self.stress_test = StressTest()
        self.crash_protection = CrashProtection()

        self.historical_metrics: List[TailRiskMetrics] = []

        logger.info("TailRiskManager initialized")

    async def assess_tail_risk(
        self,
        returns: pd.DataFrame,
        portfolio_value: float,
        weights: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive tail risk assessment.

        Args:
            returns: Historical returns
            portfolio_value: Current portfolio value
            weights: Portfolio weights

        Returns:
            Tail risk assessment
        """

        # Calculate portfolio returns
        if weights is not None:
            portfolio_returns = returns @ weights
        else:
            portfolio_returns = returns.mean(axis=1)

        # Calculate tail metrics
        tail_metrics = self.evt.calculate_tail_metrics(portfolio_returns)

        # Store in history
        self.historical_metrics.append(tail_metrics)
        if len(self.historical_metrics) > 1000:
            self.historical_metrics.pop(0)

        # Run stress tests
        stress_results = await self.stress_test.run_stress_test(
            portfolio_value, returns, weights or np.ones(len(returns.columns)) / len(returns.columns)
        )

        # Generate protection strategy
        protection_strategy = self.crash_protection.generate_protection_strategy(
            tail_metrics, portfolio_value
        )

        return {
            'tail_metrics': tail_metrics,
            'stress_test_results': stress_results,
            'protection_strategy': protection_strategy,
            'assessment_time': datetime.now().isoformat()
        }

    def get_tail_risk_report(
        self,
        assessment: Dict[str, Any]
    ) -> str:
        """Generate tail risk report."""

        tail_metrics = assessment['tail_metrics']
        protection = assessment['protection_strategy']

        report = f"""
{'='*60}
TAIL RISK ASSESSMENT
{'='*60}
Generated: {assessment['assessment_time']}

CURRENT REGIME: {tail_metrics.current_regime.value.upper()}
RISK LEVEL: {protection['risk_level']}
ACTION: {protection['action']}

TAIL RISK METRICS:
  VaR (95%): {tail_metrics.var_95:.4f}
  VaR (99%): {tail_metrics.var_99:.4f}
  CVaR (95%): {tail_metrics.cvar_95:.4f}
  CVaR (99%): {tail_metrics.cvar_99:.4f}
  EVT VaR (99%): {tail_metrics.evt_var_99:.4f}
  Max Drawdown: {tail_metrics.max_drawdown:.2%}

DISTRIBUTION PROPERTIES:
  Tail Index: {tail_metrics.tail_index:.3f}
  Skewness: {tail_metrics.skewness:.3f}
  Kurtosis: {tail_metrics.kurtosis:.3f}

CRASH PROBABILITY: {tail_metrics.probability_of_crash:.1%}

RECOMMENDATIONS:
"""
        for rec in protection['recommendations']:
            report += f"  • {rec}\n"

        report += self.stress_test.generate_stress_test_report(assessment['stress_test_results'])

        return report

    def get_crash_probability(self) -> float:
        """Get current crash probability."""
        if not self.historical_metrics:
            return 0.0
        return self.historical_metrics[-1].probability_of_crash


# Singleton instance
_tail_risk_manager = None


def get_tail_risk_manager() -> TailRiskManager:
    """Get or create tail risk manager instance."""
    global _tail_risk_manager
    if _tail_risk_manager is None:
        _tail_risk_manager = TailRiskManager()
    return _tail_risk_manager
