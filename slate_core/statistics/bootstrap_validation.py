#!/usr/bin/env python3
"""
SLATE Bootstrap Validation

Phase 4: Statistical Validation & Significance

Implements bootstrap methods for robust statistical inference:
- Bootstrap confidence intervals
- Permutation testing for significance
- Monte Carlo simulation
- Stationarity testing

Critical for understanding uncertainty in strategy performance.

Author: SLATE Evolution
Date: 2026-04-30
Priority: HIGH - Quantifies uncertainty
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import json
from scipy import stats
from scipy.stats import permutation_test

logger = logging.getLogger(__name__)


class BootstrapMethod(Enum):
    """Bootstrap methods."""
    PERCENTILE = "percentile"  # Standard percentile method
    BCa = "bca"  # Bias-corrected and accelerated
    STUDENTIZED = "studentized"  # Studentized bootstrap


@dataclass
class BootstrapResult:
    """Result from bootstrap analysis."""
    metric_name: str
    observed_value: float
    confidence_level: float
    confidence_interval: Tuple[float, float]
    bootstrap_samples: np.ndarray
    standard_error: float
    bias: float
    p_value: Optional[float] = None
    is_significant: bool = False


@dataclass
class PermutationTestResult:
    """Result from permutation testing."""
    test_statistic: float
    null_distribution: np.ndarray
    p_value: float
    is_significant: bool
    n_permutations: int


class BootstrapValidator:
    """
    Bootstrap validation for strategy metrics.

    Bootstrap methods provide:
    - Confidence intervals
    - Standard error estimation
    - Bias estimation
    - Significance testing

    Non-parametric and makes minimal assumptions.
    """

    def __init__(self, n_bootstrap: int = 10000):
        self.n_bootstrap = n_bootstrap
        self.random_seed = 42

        logger.info(f"BootstrapValidator initialized with {n_bootstrap} iterations")

    async def bootstrap_confidence_interval(
        self,
        returns: pd.Series,
        metric_func: callable = None,
        confidence_level: float = 0.95,
        method: BootstrapMethod = BootstrapMethod.PERCENTILE
    ) -> BootstrapResult:
        """
        Calculate bootstrap confidence interval for a metric.

        Args:
            returns: Strategy returns
            metric_func: Function to calculate metric (default: total return)
            confidence_level: Confidence level (0-1)
            method: Bootstrap method

        Returns:
            BootstrapResult with CI and statistics
        """

        if metric_func is None:
            metric_func = lambda x: x.sum()  # Total return

        # Calculate observed metric
        observed_value = metric_func(returns)

        # Bootstrap resampling
        np.random.seed(self.random_seed)
        bootstrap_metrics = []

        for i in range(self.n_bootstrap):
            # Resample with replacement
            sample = returns.sample(n=len(returns), replace=True)
            metric = metric_func(sample)
            bootstrap_metrics.append(metric)

        bootstrap_metrics = np.array(bootstrap_metrics)

        # Calculate confidence interval
        alpha = 1 - confidence_level
        lower_percentile = (alpha / 2) * 100
        upper_percentile = (1 - alpha / 2) * 100

        ci_lower = np.percentile(bootstrap_metrics, lower_percentile)
        ci_upper = np.percentile(bootstrap_metrics, upper_percentile)

        # Calculate statistics
        standard_error = np.std(bootstrap_metrics)
        bias = observed_value - np.mean(bootstrap_metrics)

        # P-value (two-sided test if 0 is in CI)
        if ci_lower <= 0 <= ci_upper:
            p_value = None
            is_significant = False
        else:
            # Approximate p-value from bootstrap distribution
            p_value = 2 * min(
                np.sum(bootstrap_metrics <= 0),
                np.sum(bootstrap_metrics >= 0)
            ) / self.n_bootstrap
            is_significant = p_value < 0.05

        return BootstrapResult(
            metric_name="strategy_return",
            observed_value=observed_value,
            confidence_level=confidence_level,
            confidence_interval=(ci_lower, ci_upper),
            bootstrap_samples=bootstrap_metrics,
            standard_error=standard_error,
            bias=bias,
            p_value=p_value,
            is_significant=is_significant
        )

    async def bootstrap_sharpe_ratio(
        self,
        returns: pd.Series,
        confidence_level: float = 0.95
    ) -> BootstrapResult:
        """
        Bootstrap confidence interval for Sharpe ratio.

        Args:
            returns: Strategy returns
            confidence_level: Confidence level

        Returns:
            BootstrapResult for Sharpe ratio
        """

        def calculate_sharpe(ret):
            """Calculate Sharpe ratio."""
            if len(ret) == 0:
                return 0.0
            mean = ret.mean()
            std = ret.std()
            return mean / std * np.sqrt(252) if std > 0 else 0.0

        return await self.bootstrap_confidence_interval(
            returns, calculate_sharpe, confidence_level
        )

    async def bootstrap_max_drawdown(
        self,
        returns: pd.Series,
        confidence_level: float = 0.95
    ) -> BootstrapResult:
        """
        Bootstrap confidence interval for maximum drawdown.

        Args:
            returns: Strategy returns
            confidence_level: Confidence level

        Returns:
            BootstrapResult for max drawdown
        """

        def calculate_max_drawdown(ret):
            """Calculate maximum drawdown."""
            if len(ret) == 0:
                return 0.0
            cumulative = (1 + ret).cumprod()
            running_max = cumulative.cummax()
            drawdown = (cumulative - running_max) / running_max
            return abs(drawdown.min())

        return await self.bootstrap_confidence_interval(
            returns, calculate_max_drawdown, confidence_level
        )


class PermutationTester:
    """
    Permutation testing for statistical significance.

    Tests if strategy performance is significantly different
    from random chance.

    Null hypothesis: Strategy has no predictive power
    Alternative: Strategy has genuine predictive power
    """

    def __init__(self, n_permutations: int = 1000):
        self.n_permutations = n_permutations
        self.random_seed = 42

        logger.info(f"PermutationTester initialized with {n_permutations} iterations")

    async def test_return_significance(
        self,
        returns: pd.Series,
        signals: pd.Series,
        benchmark_returns: Optional[pd.Series] = None
    ) -> PermutationTestResult:
        """
        Test if strategy returns are significantly better than random.

        Args:
            returns: Asset returns
            signals: Strategy signals (-1, 0, 1)
            benchmark_returns: Optional benchmark returns

        Returns:
            PermutationTestResult with significance test
        """

        # Calculate observed test statistic
        strategy_returns = returns.shift(-1) * signals
        observed_stat = strategy_returns.sum()

        # Permutation test
        null_distribution = []

        np.random.seed(self.random_seed)

        for _ in range(self.n_permutations):
            # Shuffle signals (break relationship with returns)
            shuffled_signals = np.random.permutation(signals)

            # Calculate metric with shuffled signals
            permuted_returns = returns.shift(-1) * shuffled_signals
            permuted_stat = permuted_returns.sum()

            null_distribution.append(permuted_stat)

        null_distribution = np.array(null_distribution)

        # Calculate p-value
        # Two-sided test
        p_value = np.sum(np.abs(null_distribution) >= np.abs(observed_stat)) / self.n_permutations

        return PermutationTestResult(
            test_statistic=observed_stat,
            null_distribution=null_distribution,
            p_value=p_value,
            is_significant=p_value < 0.05,
            n_permutations=self.n_permutations
        )

    async def test_sharpe_significance(
        self,
        returns: pd.Series,
        n_permutations: int = 500
    ) -> PermutationTestResult:
        """
        Test if Sharpe ratio is significantly greater than zero.

        Args:
            returns: Strategy returns
            n_permutations: Number of permutations

        Returns:
            PermutationTestResult
        """

        # Calculate observed Sharpe
        observed_sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0

        # Permutation test
        null_distribution = []

        np.random.seed(self.random_seed)

        for _ in range(n_permutations):
            # Shuffle returns
            shuffled_returns = np.random.permutation(returns)

            # Calculate Sharpe
            mean = shuffled_returns.mean()
            std = shuffled_returns.std()
            sharpe = mean / std * np.sqrt(252) if std > 0 else 0

            null_distribution.append(sharpe)

        null_distribution = np.array(null_distribution)

        # P-value (one-sided: Sharpe > 0)
        p_value = np.sum(null_distribution >= observed_sharpe) / n_permutations

        return PermutationTestResult(
            test_statistic=observed_sharpe,
            null_distribution=null_distribution,
            p_value=p_value,
            is_significant=p_value < 0.05,
            n_permutations=n_permutations
        )


class MonteCarloSimulator:
    """
    Monte Carlo simulation for strategy validation.

    Simulates strategy performance under thousands of
    random price paths to assess robustness.
    """

    def __init__(self, n_simulations: int = 1000):
        self.n_simulations = n_simulations
        self.random_seed = 42

        logger.info(f"MonteCarloSimulator initialized with {n_simulations} paths")

    async def simulate_strategy_paths(
        self,
        initial_price: float,
        drift: float,
        volatility: float,
        days: int,
        strategy_func: callable,
        initial_capital: float = 10000.0
    ) -> Dict[str, Any]:
        """
        Simulate strategy over multiple price paths.

        Args:
            initial_price: Starting price
            drift: Expected daily return
            volatility: Daily volatility
            days: Number of days to simulate
            strategy_func: Strategy function that takes prices and returns signals
            initial_capital: Starting capital

        Returns:
            Dictionary with simulation results
        """

        np.random.seed(self.random_seed)

        final_capitals = []
        total_returns = []
        max_drawdowns = []

        dt = 1.0  # Daily time step

        for i in range(self.n_simulations):
            # Generate price path (Geometric Brownian Motion)
            random_shocks = np.random.normal(0, 1, days)
            price_path = np.zeros(days + 1)
            price_path[0] = initial_price

            for t in range(1, days + 1):
                price_path[t] = price_path[t-1] * np.exp(
                    (drift - 0.5 * volatility ** 2) * dt +
                    volatility * np.sqrt(dt) * random_shocks[t-1]
                )

            # Calculate returns
            returns = pd.Series(price_path[1:]).pct_change()
            returns = returns.fillna(0)

            # Generate signals
            signals = strategy_func(returns, price_path)

            # Calculate performance
            strategy_returns = returns.shift(-1) * signals
            total_return = strategy_returns.sum()

            # Calculate capital path
            capital_path = initial_capital * (1 + strategy_returns).cumprod()
            final_capital = capital_path.iloc[-1] if len(capital_path) > 0 else initial_capital

            # Max drawdown
            running_max = capital_path.cummax()
            drawdown = (capital_path - running_max) / running_max
            max_drawdown = abs(drawdown.min())

            final_capitals.append(final_capital)
            total_returns.append(total_return)
            max_drawdowns.append(max_drawdown)

        # Calculate statistics
        final_capitals = np.array(final_capitals)
        total_returns = np.array(total_returns)
        max_drawdowns = np.array(max_drawdowns)

        # Confidence intervals
        ci_5 = np.percentile(final_capitals, 5)
        ci_95 = np.percentile(final_capitals, 95)

        # Probability of profit
        prob_profit = np.sum(final_capitals > initial_capital) / self.n_simulations

        # Probability of meeting targets
        prob_10pct_return = np.sum(total_returns > 0.10) / self.n_simulations
        prob_max_dd_25 = np.sum(max_drawdowns < 0.25) / self.n_simulations

        return {
            'final_capitals': final_capitals,
            'total_returns': total_returns,
            'max_drawdowns': max_drawdowns,
            'mean_final_capital': np.mean(final_capitals),
            'median_final_capital': np.median(final_capitals),
            'std_final_capital': np.std(final_capitals),
            'ci_5_percentile': ci_5,
            'ci_95_percentile': ci_95,
            'prob_profit': prob_profit,
            'prob_10pct_return': prob_10pct_return,
            'prob_max_dd_25': prob_max_dd_25,
            'worst_case': final_capitals.min(),
            'best_case': final_capitals.max()
        }


class StationarityTester:
    """
    Test for stationarity in time series.

    Critical because many statistical methods assume stationarity.
    """

    def __init__(self):
        logger.info("StationarityTester initialized")

    def test_stationarity(
        self,
        series: pd.Series,
        test: str = "adf"
    ) -> Dict[str, Any]:
        """
        Test if time series is stationary.

        Args:
            series: Time series data
            test: 'adf' (Augmented Dickey-Fuller) or 'kpss'

        Returns:
            Dictionary with test results
        """

        if test == "adf":
            # Augmented Dickey-Fuller test
            # H0: Series has unit root (non-stationary)
            # H1: Series is stationary
            try:
                from statsmodels.tsa.stattools import adfuller

                result = adfuller(series, maxlag=1, regression='ct')

                return {
                    'test': 'ADF',
                    'statistic': result[0],
                    'p_value': result[1],
                    'used_lag': result[2],
                    'n_observations': result[3],
                    'critical_values_5pct': result[4]['5%'],
                    'is_stationary': result[1] < 0.05,
                    'interpretation': 'Stationary' if result[1] < 0.05 else 'Non-stationary'
                }
            except ImportError:
                # Fallback to scipy
                logger.warning("statsmodels not available, using simple test")
                return self._simple_stationarity_test(series)

        elif test == "kpss":
            # KPSS test
            # H0: Series is stationary
            # H1: Series has unit root
            try:
                from statsmodels.tsa.stattools import kpss

                result = kpss(series, regression='c')

                return {
                    'test': 'KPSS',
                    'statistic': result[0],
                    'p_value': result[1],
                    'used_lag': result[2],
                    'critical_values_5pct': result[3]['5%'],
                    'is_stationary': result[1] > 0.05,
                    'interpretation': 'Stationary' if result[1] > 0.05 else 'Non-stationary'
                }
            except ImportError:
                return self._simple_stationarity_test(series)

        else:
            raise ValueError(f"Unknown test: {test}")

    def _simple_stationarity_test(self, series: pd.Series) -> Dict[str, Any]:
        """Simple stationarity test (fallback)."""

        # Calculate variance of first half vs second half
        n = len(series)
        mid = n // 2

        var_first = series.iloc[:mid].var()
        var_second = series.iloc[mid:].var()

        # Simple test: if variance changes significantly, non-stationary
        var_ratio = var_second / var_first if var_first > 0 else 1.0

        # Very rough heuristic
        is_stationary = 0.5 < var_ratio < 2.0

        return {
            'test': 'Simple Variance Ratio',
            'statistic': var_ratio,
            'p_value': None,
            'is_stationary': is_stationary,
            'interpretation': 'Stationary' if is_stationary else 'Non-stationary'
        }


# Singleton instances
_bootstrap_validator = None
_permutation_tester = None
_monte_carlo = None
_stationarity_tester = None


def get_bootstrap_validator() -> BootstrapValidator:
    """Get or create bootstrap validator instance."""
    global _bootstrap_validator
    if _bootstrap_validator is None:
        _bootstrap_validator = BootstrapValidator()
    return _bootstrap_validator


def get_permutation_tester() -> PermutationTester:
    """Get or create permutation tester instance."""
    global _permutation_tester
    if _permutation_tester is None:
        _permutation_tester = PermutationTester()
    return _permutation_tester


def get_monte_carlo_simulator() -> MonteCarloSimulator:
    """Get or create Monte Carlo simulator instance."""
    global _monte_carlo
    if _monte_carlo is None:
        _monte_carlo = MonteCarloSimulator()
    return _monte_carlo


def get_stationarity_tester() -> StationarityTester:
    """Get or create stationarity tester instance."""
    global _stationarity_tester
    if _stationarity_tester is None:
        _stationarity_tester = StationarityTester()
    return _stationarity_tester
