#!/usr/bin/env python3
"""Test script to debug validation issues with enhanced logging"""

import sys
import logging

# Set up logging to see output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Import after logging setup
from slate_core.discovery.closed_loop_discovery import (
    HypothesisTestResult, StrategyHypothesis, HypothesisType
)

def test_validation_calculation():
    """Test the validation score calculation with different scenarios"""

    print("\n" + "="*80)
    print("TEST 1: Strategy with negative Sharpe (like the one that passed)")
    print("="*80)

    # Simulate the actual strategy that passed
    result_negative_sharpe = {
        'total_trades': 68,
        'win_rate': 0.456,
        'sharpe_ratio': -0.874,
        'max_drawdown': 0.15,
        'total_return': 0.0
    }

    # Expected outcomes for mean reversion strategy (REALISTIC)
    expected_outcomes = {
        'min_trades': 5,
        'min_win_rate': 0.42,  # Realistic with costs
        'min_sharpe': -0.2,    # Allow slightly negative
        'max_drawdown': 0.25,  # Higher tolerance
        'expected_return': 'positive_after_costs'
    }

    # Create a mock hypothesis test result
    from slate_core.discovery.closed_loop_discovery import HypothesisValidationSystem
    validator = HypothesisValidationSystem()

    validation_score = validator.calculate_validation_score(
        result_negative_sharpe, {}, expected_outcomes
    )

    print(f"\nValidation Score: {validation_score:.2f}")
    print(f"Pass threshold: 0.3")
    print(f"Result: {'✅ PASS' if validation_score >= 0.3 else '❌ FAIL'}")

    print("\n" + "="*80)
    print("TEST 2: Strategy with moderate positive performance")
    print("="*80)

    result_moderate = {
        'total_trades': 45,
        'win_rate': 0.42,
        'sharpe_ratio': 0.1,
        'max_drawdown': 0.18,
        'total_return': 0.02
    }

    validation_score_moderate = validator.calculate_validation_score(
        result_moderate, {}, expected_outcomes
    )

    print(f"\nValidation Score: {validation_score_moderate:.2f}")
    print(f"Pass threshold: 0.3")
    print(f"Result: {'✅ PASS' if validation_score_moderate >= 0.3 else '❌ FAIL'}")

    print("\n" + "="*80)
    print("TEST 3: Strategy with momentum criteria (more relaxed)")
    print("="*80)

    momentum_outcomes = {
        'min_trades': 15,
        'min_win_rate': 0.38,  # Realistic with costs
        'min_sharpe': -0.3,    # Allow negative
        'max_drawdown': 0.30,  # Higher tolerance
        'expected_return': 'positive_after_costs'
    }

    validation_score_momentum = validator.calculate_validation_score(
        result_moderate, {}, momentum_outcomes
    )

    print(f"\nValidation Score: {validation_score_momentum:.2f}")
    print(f"Pass threshold: 0.3")
    print(f"Result: {'✅ PASS' if validation_score_momentum >= 0.3 else '❌ FAIL'}")

    print("\n" + "="*80)
    print("ANALYSIS: Why negative Sharpe strategy might have passed")
    print("="*80)

    print("\nThe issue is likely:")
    print("1. Strategy-specific criteria vs. default criteria mismatch")
    print("2. Different validation code paths in the system")
    print("3. The negative Sharpe strategy may have used different criteria")

if __name__ == '__main__':
    test_validation_calculation()
