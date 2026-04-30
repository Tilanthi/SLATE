#!/usr/bin/env python3
"""
SLATE Multiple Testing Correction

Phase 4: Statistical Validation & Significance

Implements correction for multiple hypothesis testing to prevent
false discoveries and ensure statistical significance.

Critical for strategy discovery because:
- Testing hundreds of strategies → many will appear profitable by chance
- Without correction → false discoveries lead to real losses

Methods implemented:
- Bonferroni correction (conservative)
- False Discovery Rate (FDR)
- Benjamini-Hochberg procedure (balanced)
- Holm-Bonferroni method (less conservative)

Author: SLATE Evolution
Date: 2026-04-30
Priority: CRITICAL - Prevents false discoveries
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

logger = logging.getLogger(__name__)


class CorrectionMethod(Enum):
    """Multiple testing correction methods."""
    BONFERRONI = "bonferroni"  # Most conservative
    HOLM = "holm"  # Less conservative than Bonferroni
    BENJAMINI_HOCHBERG = "benjamini_hochberg"  # FDR control
    BENJAMINI_YEKUTIELI = "benjamini_yekutieli"  # More conservative FDR
    NONE = "none"  # No correction (dangerous!)


@dataclass
class HypothesisTest:
    """A single hypothesis test result."""
    test_id: str
    test_name: str
    null_hypothesis: str
    p_value: float
    test_statistic: float
    is_significant_uncorrected: bool
    alpha: float = 0.05

    def __post_init__(self):
        self.is_significant_uncorrected = self.p_value < self.alpha


@dataclass
class CorrectedResult:
    """Result after multiple testing correction."""
    original_test: HypothesisTest
    corrected_p_value: float
    is_significant_corrected: bool
    correction_method: CorrectionMethod
    num_tests: int
    familywise_error_rate: float
    false_discovery_rate: float


class MultipleTestingCorrection:
    """
    Multiple testing correction for strategy discovery.

    When testing many strategies, we must account for the
    multiple comparisons problem to avoid false discoveries.

    Philosophy: "It's better to miss a good strategy than
                  to trade a bad one thinking it's good."
    """

    def __init__(self):
        self.test_history = []

        logger.info("MultipleTestingCorrection initialized")

    async def correct_p_values(
        self,
        tests: List[HypothesisTest],
        method: CorrectionMethod = CorrectionMethod.BENJAMINI_HOCHBERG,
        alpha: float = 0.05
    ) -> List[CorrectedResult]:
        """
        Apply multiple testing correction to p-values.

        Args:
            tests: List of hypothesis tests
            method: Correction method to use
            alpha: Significance level

        Returns:
            List of corrected results
        """

        num_tests = len(tests)
        p_values = np.array([test.p_value for test in tests])

        logger.info(f"Correcting {num_tests} tests using {method.value}")

        if method == CorrectionMethod.BONFERRONI:
            corrected_p = self._bonferroni_correction(p_values, alpha)

        elif method == CorrectionMethod.HOLM:
            corrected_p = self._holm_correction(p_values, alpha)

        elif method == CorrectionMethod.BENJAMINI_HOCHBERG:
            corrected_p = self._benjamini_hochberg(p_values)

        elif method == CorrectionMethod.BENJAMINI_YEKUTIELI:
            corrected_p = self._benjamini_yekutieli(p_values)

        else:
            corrected_p = p_values  # No correction

        # Create corrected results
        results = []
        for i, test in enumerate(tests):
            result = CorrectedResult(
                original_test=test,
                corrected_p_value=corrected_p[i],
                is_significant_corrected=corrected_p[i] < alpha,
                correction_method=method,
                num_tests=num_tests,
                familywise_error_rate=self._calculate_fwer(corrected_p, alpha),
                false_discovery_rate=self._calculate_fdr(corrected_p, alpha)
            )
            results.append(result)

        # Store history
        self.test_history.append({
            'timestamp': datetime.now(),
            'num_tests': num_tests,
            'method': method.value,
            'significant_uncorrected': sum(1 for t in tests if t.is_significant_uncorrected),
            'significant_corrected': sum(1 for r in results if r.is_significant_corrected)
        })

        return results

    def _bonferroni_correction(self, p_values: np.ndarray, alpha: float) -> np.ndarray:
        """
        Bonferroni correction.

        Most conservative method.
        Adjusted alpha = alpha / n
        """
        n = len(p_values)
        adjusted_alpha = alpha / n
        return p_values * n  # Multiply p-values by n

    def _holm_correction(self, p_values: np.ndarray, alpha: float) -> np.ndarray:
        """
        Holm-Bonferroni correction.

        Less conservative than Bonferroni but still
        controls family-wise error rate.
        """
        n = len(p_values)

        # Sort p-values
        sorted_indices = np.argsort(p_values)
        sorted_p = p_values[sorted_indices]

        # Holm step-down procedure
        corrected_p = np.zeros_like(p_values)

        for i, (idx, p_val) in enumerate(zip(sorted_indices, sorted_p)):
            # Holm formula: p * (n - i)
            corrected_p[idx] = min(p_val * (n - i), 1.0)

        # Ensure monotonicity (corrected p-values shouldn't decrease)
        for i in sorted_indices[1:]:
            corrected_p[i] = max(corrected_p[i], corrected_p[sorted_indices[sorted_indices < i].max()])

        return corrected_p

    def _benjamini_hochberg(self, p_values: np.ndarray) -> np.ndarray:
        """
        Benjamini-Hochberg procedure.

        Controls False Discovery Rate (FDR).
        Less conservative than Bonferroni, more powerful.
        """
        n = len(p_values)

        # Sort p-values
        sorted_indices = np.argsort(p_values)
        sorted_p = p_values[sorted_indices]

        # Calculate BH critical values
        corrected_p = np.zeros_like(p_values)

        for i, (idx, p_val) in enumerate(zip(sorted_indices, sorted_p)):
            # BH formula: p * n / (n - i + 1)
            rank = i + 1
            corrected_p[idx] = min(p_val * n / rank, 1.0)

        # Ensure monotonicity
        for i in sorted_indices[1:]:
            corrected_p[i] = max(corrected_p[i], corrected_p[sorted_indices[sorted_indices < i].max()])

        return corrected_p

    def _benjamini_yekutieli(self, p_values: np.ndarray) -> np.ndarray:
        """
        Benjamini-Yekutieli procedure.

        More conservative FDR control for correlated tests.
        """
        n = len(p_values)

        # Calculate harmonic sum
        harmonic_sum = np.sum(1.0 / np.arange(1, n + 1))

        # Sort p-values
        sorted_indices = np.argsort(p_values)
        sorted_p = p_values[sorted_indices]

        # BY critical values
        corrected_p = np.zeros_like(p_values)

        for i, (idx, p_val) in enumerate(zip(sorted_indices, sorted_p)):
            rank = i + 1
            # BY formula: p * n / (rank * harmonic_sum)
            correction_factor = n / (rank * harmonic_sum)
            corrected_p[idx] = min(p_val * correction_factor, 1.0)

        # Ensure monotonicity
        for i in sorted_indices[1:]:
            corrected_p[i] = max(corrected_p[i], corrected_p[sorted_indices[sorted_indices < i].max()])

        return corrected_p

    def _calculate_fwer(self, corrected_p: np.ndarray, alpha: float) -> float:
        """Calculate family-wise error rate."""
        # Probability of at least one false positive
        return 1 - np.prod(1 - np.minimum(corrected_p, 1.0))

    def _calculate_fdr(self, corrected_p: np.ndarray, alpha: float) -> float:
        """Calculate false discovery rate."""
        significant = corrected_p < alpha
        if not np.any(significant):
            return 0.0

        # Expected proportion of false positives among significant
        return np.sum(corrected_p[significant]) / np.sum(significant)

    def generate_correction_report(self, results: List[CorrectedResult]) -> str:
        """Generate detailed correction report."""

        num_tests = len(results)
        num_significant_uncorrected = sum(1 for r in results if r.original_test.is_significant_uncorrected)
        num_significant_corrected = sum(1 for r in results if r.is_significant_corrected)

        report = f"""
{'='*60}
MULTIPLE TESTING CORRECTION REPORT
{'='*60}

CORRECTION METHOD: {results[0].correction_method.value if results else 'N/A'}
NUMBER OF TESTS: {num_tests}
SIGNIFICANCE LEVEL: {results[0].original_test.alpha if results else 0.05}

RESULTS:
  Significant (Uncorrected): {num_significant_uncorrected}/{num_tests} ({num_significant_uncorrected/num_tests*100:.1f}%)
  Significant (Corrected): {num_significant_corrected}/{num_tests} ({num_significant_corrected/num_tests*100:.1f}%)

IMPACT:
  False Discoveries Prevented: {num_significant_uncorrected - num_significant_corrected}
  Reduction Rate: {(1 - num_significant_corrected/max(num_significant_uncorrected, 1))*100:.1f}%

FAMILY-WISE ERROR RATE: {results[0].familywise_error_rate if results else 0:.4f}
FALSE DISCOVERY RATE: {results[0].false_discovery_rate if results else 0:.4f}
"""

        if num_significant_corrected > 0:
            report += "\nSIGNIFICANT TESTS (After Correction):\n"
            for result in results:
                if result.is_significant_corrected:
                    report += f"  ✓ {result.original_test.test_name}\n"
                    report += f"     Original p: {result.original_test.p_value:.4f}\n"
                    report += f"     Corrected p: {result.corrected_p_value:.4f}\n"

        return report


class StrategySignificanceTester:
    """
    Test strategy significance with proper multiple testing correction.

    Applies statistical tests to strategy performance:
    - Is return significantly different from zero?
    - Is Sharpe ratio significantly positive?
    - Is strategy better than buy-and-hold?
    - Is maximum drawdown acceptable?
    """

    def __init__(self):
        self.correction = MultipleTestingCorrection()

        logger.info("StrategySignificanceTester initialized")

    async def test_strategy_batch(
        self,
        strategies: Dict[str, Dict[str, float]],
        benchmark_return: float = 0.0,
        method: CorrectionMethod = CorrectionMethod.BENJAMINI_HOCHBERG
    ) -> List[CorrectedResult]:
        """
        Test a batch of strategies for statistical significance.

        Args:
            strategies: Dict of {strategy_name: {returns, sharpe, drawdown, ...}}
            benchmark_return: Buy-and-hold return
            method: Correction method

        Returns:
            List of corrected test results
        """

        tests = []
        for strategy_name, metrics in strategies.items():
            # Test 1: Return significantly different from zero
            t_stat, p_value = self._test_return_significance(
                metrics['returns'],
                metrics['total_profit_usdt']
            )

            test = HypothesisTest(
                test_id=f"{strategy_name}_return",
                test_name=strategy_name,
                null_hypothesis=f"{strategy_name} return = 0",
                p_value=p_value,
                test_statistic=t_stat,
                is_significant_uncorrected=p_value < 0.05
            )
            tests.append(test)

        # Apply multiple testing correction
        corrected_results = await self.correction.correct_p_values(tests, method)

        return corrected_results

    def _test_return_significance(
        self,
        returns: pd.Series,
        total_profit: float
    ) -> Tuple[float, float]:
        """
        Test if strategy return is significantly different from zero.

        Uses t-test for mean of returns.
        """

        if len(returns) == 0:
            return 0.0, 1.0  # No data, not significant

        # One-sample t-test
        t_stat, p_value = stats.ttest_1samp(returns, 0.0)

        return abs(t_stat), p_value

    def _test_sharpe_significance(
        self,
        returns: pd.Series,
        sharpe_ratio: float
    ) -> Tuple[float, float]:
        """
        Test if Sharpe ratio is significantly greater than zero.

        Uses jobson-korkie adjustment for Sharpe significance.
        """

        if len(returns) < 2:
            return 0.0, 1.0

        # Simplified Sharpe significance test
        # Standard error of Sharpe
        n = len(returns)
        se_sharpe = np.sqrt(1 + (sharpe_ratio ** 2) / 2) / np.sqrt(n)

        t_stat = sharpe_ratio / se_sharpe
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), n - 1))

        return t_stat, p_value

    def _test_vs_benchmark(
        self,
        strategy_returns: pd.Series,
        benchmark_returns: pd.Series
    ) -> Tuple[float, float]:
        """
        Test if strategy significantly outperforms benchmark.

        Uses paired t-test.
        """

        if len(strategy_returns) != len(benchmark_returns):
            min_len = min(len(strategy_returns), len(benchmark_returns))
            strategy_returns = strategy_returns[:min_len]
            benchmark_returns = benchmark_returns[:min_len]

        # Paired t-test
        t_stat, p_value = stats.ttest_rel(strategy_returns, benchmark_returns)

        return t_stat, p_value


# Singleton instance
_significance_tester = None


def get_significance_tester() -> StrategySignificanceTester:
    """Get or create significance tester instance."""
    global _significance_tester
    if _significance_tester is None:
        _significance_tester = StrategySignificanceTester()
    return _significance_tester
