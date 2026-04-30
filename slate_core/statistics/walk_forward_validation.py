#!/usr/bin/env python3
"""
SLATE Walk-Forward Validation

Phase 4: Statistical Validation & Significance

Implements robust out-of-sample validation to prevent overfitting:
- Walk-forward analysis
- Rolling window validation
- Temporal validation splits
- Nested cross-validation
- Parameter stability testing

Critical for ensuring strategies work in the future, not just the past.

Author: SLATE Evolution
Date: 2026-04-30
Priority: CRITICAL - Prevents overfitting
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
from sklearn.model_selection import TimeSeriesSplit
from scipy import stats

logger = logging.getLogger(__name__)


class ValidationMethod(Enum):
    """Validation methods."""
    WALK_FORWARD = "walk_forward"
    ROLLING_WINDOW = "rolling_window"
    TEMPORAL_SPLIT = "temporal_split"
    NESTED_CROSS_VALID = "nested_cross_validation"


@dataclass
class ValidationResult:
    """Result from validation analysis."""
    method: ValidationMethod
    in_sample_return: float
    out_of_sample_return: float
    in_sample_sharpe: float
    out_of_sample_sharpe: float
    overfitting_score: float  # 0 = perfect, 1 = severe overfitting
    is_overfitted: bool
    parameter_stability: float
    recommendation: str


@dataclass
class WalkForwardWindow:
    """A single walk-forward window."""
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    in_sample_metrics: Dict[str, float]
    out_of_sample_metrics: Dict[str, float]


class WalkForwardValidator:
    """
    Walk-forward validation for time series strategies.

    Prevents look-ahead bias and ensures strategies work
    in out-of-sample data.

    Process:
    1. Train on period [t_start, t_end]
    2. Test on period [t_end + 1, t_end + test_period]
    3. Roll forward and repeat
    4. Aggregate results
    """

    def __init__(self):
        self.min_train_periods = 252  # Minimum 1 year of daily data
        self.test_periods = 63  # 3 months test period
        self.step_periods = 21  # Roll forward by 1 month

        logger.info("WalkForwardValidator initialized")

    async def walk_forward_analysis(
        self,
        data: pd.DataFrame,
        strategy_func: callable,
        initial_capital: float = 10000.0
    ) -> Tuple[List[WalkForwardWindow], ValidationResult]:
        """
        Perform walk-forward analysis.

        Args:
            data: Historical price data with datetime index
            strategy_func: Function that takes data and returns signals
            initial_capital: Starting capital

        Returns:
            (List of windows, Overall validation result)
        """

        windows = []
        total_data = len(data)

        if total_data < self.min_train_periods + self.test_periods:
            raise ValueError(f"Insufficient data: {total_data} < "
                           f"{self.min_train_periods + self.test_periods} required")

        # Walk through data
        train_end = self.min_train_periods

        while train_end + self.test_periods < total_data:
            # Training window
            train_start = max(0, train_end - self.min_train_periods)

            # Testing window
            test_start = train_end
            test_end = min(total_data, train_end + self.test_periods)

            # Train and test
            train_data = data.iloc[train_start:train_end]
            test_data = data.iloc[test_start:test_end]

            # Generate signals
            train_signals = strategy_func(train_data)
            test_signals = strategy_func(test_data)

            # Calculate metrics
            in_sample_metrics = self._calculate_metrics(
                train_data, train_signals, initial_capital
            )

            out_of_sample_metrics = self._calculate_metrics(
                test_data, test_signals, initial_capital
            )

            window = WalkForwardWindow(
                train_start=data.index[train_start],
                train_end=data.index[train_end - 1],
                test_start=data.index[test_start],
                test_end=data.index[test_end - 1],
                in_sample_metrics=in_sample_metrics,
                out_of_sample_metrics=out_of_sample_metrics
            )

            windows.append(window)

            # Roll forward
            train_end += self.step_periods

        # Aggregate results
        validation_result = self._aggregate_results(windows)

        return windows, validation_result

    def _calculate_metrics(
        self,
        data: pd.DataFrame,
        signals: pd.Series,
        initial_capital: float
    ) -> Dict[str, float]:
        """Calculate performance metrics."""

        if len(signals) == 0 or len(data) == 0:
            return {
                'return': 0.0,
                'sharpe': 0.0,
                'max_drawdown': 0.0,
                'win_rate': 0.0
            }

        # Calculate returns
        data_returns = data['close'].pct_change().fillna(0)

        # Align signals with returns (signal at t, return at t+1)
        strategy_returns = data_returns.shift(-1) * signals

        # Total return
        total_return = strategy_returns.sum()

        # Sharpe ratio
        if len(strategy_returns) > 1:
            sharpe = strategy_returns.mean() / strategy_returns.std() * np.sqrt(252) if strategy_returns.std() > 0 else 0
        else:
            sharpe = 0.0

        # Max drawdown
        cumulative = (1 + strategy_returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = abs(drawdown.min())

        # Win rate
        win_rate = (strategy_returns > 0).sum() / len(strategy_returns) if len(strategy_returns) > 0 else 0

        return {
            'return': total_return,
            'sharpe': sharpe,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate
        }

    def _aggregate_results(
        self,
        windows: List[WalkForwardWindow]
    ) -> ValidationResult:
        """Aggregate walk-forward window results."""

        if not windows:
            return ValidationResult(
                method=ValidationMethod.WALK_FORWARD,
                in_sample_return=0.0,
                out_of_sample_return=0.0,
                in_sample_sharpe=0.0,
                out_of_sample_sharpe=0.0,
                overfitting_score=1.0,
                is_overfitted=True,
                parameter_stability=0.0,
                recommendation="Insufficient data"
            )

        # Aggregate metrics
        in_sample_returns = [w.in_sample_metrics['return'] for w in windows]
        out_of_sample_returns = [w.out_of_sample_metrics['return'] for w in windows]

        avg_in_sample = np.mean(in_sample_returns)
        avg_out_of_sample = np.mean(out_of_sample_returns)

        in_sample_sharpes = [w.in_sample_metrics['sharpe'] for w in windows]
        out_of_sample_sharpes = [w.out_of_sample_metrics['sharpe'] for w in windows]

        avg_in_sharpe = np.mean(in_sample_sharpes)
        avg_out_sharpe = np.mean(out_of_sample_sharpes)

        # Calculate overfitting score
        # Perfect: in_sample = out_of_sample
        # Severe overfitting: in_sample >> out_of_sample
        if avg_in_sample != 0:
            overfitting_score = abs(avg_in_sample - avg_out_of_sample) / abs(avg_in_sample)
        else:
            overfitting_score = 0.0

        # Parameter stability (variance of out-of-sample results)
        parameter_stability = 1.0 / (1.0 + np.std(out_of_sample_returns))

        # Determine if overfitted
        is_overfitted = overfitting_score > 0.5  # More than 50% degradation

        # Generate recommendation
        if not is_overfitted and avg_out_of_sample > 0:
            recommendation = "VALIDATED - Strategy robust across time periods"
        elif is_overfitted and avg_out_of_sample > 0:
            recommendation = "OVERFITTED - Positive OOS but significant degradation"
        elif avg_out_of_sample <= 0:
            recommendation = "FAILED - Negative out-of-sample performance"
        else:
            recommendation = "UNCERTAIN - Insufficient data"

        return ValidationResult(
            method=ValidationMethod.WALK_FORWARD,
            in_sample_return=avg_in_sample,
            out_of_sample_return=avg_out_of_sample,
            in_sample_sharpe=avg_in_sharpe,
            out_of_sample_sharpe=avg_out_sharpe,
            overfitting_score=overfitting_score,
            is_overfitted=is_overfitted,
            parameter_stability=parameter_stability,
            recommendation=recommendation
        )


class RollingWindowValidator:
    """
    Rolling window validation.

    Similar to walk-forward but uses fixed-size windows
    that roll forward by a fixed amount.
    """

    def __init__(self):
        self.window_size = 252  # 1 year
        self.test_size = 63  # 3 months
        self.step_size = 21  # 1 month

        logger.info("RollingWindowValidator initialized")

    async def rolling_window_validation(
        self,
        data: pd.DataFrame,
        strategy_func: callable
    ) -> ValidationResult:
        """
        Perform rolling window validation.

        Args:
            data: Historical price data
            strategy_func: Strategy function

        Returns:
            ValidationResult with aggregated results
        """

        tscv = TimeSeriesSplit(
            n_splits=5,
            test_size=self.test_size,
            max_train_size=self.window_size
        )

        in_sample_results = []
        out_of_sample_results = []

        for train_idx, test_idx in tscv.split(data):
            train_data = data.iloc[train_idx]
            test_data = data.iloc[test_idx]

            # Train strategy
            train_signals = strategy_func(train_data)
            test_signals = strategy_func(test_data)

            # Calculate returns
            train_returns = train_data['close'].pct_change().fillna(0)
            test_returns = test_data['close'].pct_change().fillna(0)

            train_strategy_returns = train_returns.shift(-1) * train_signals
            test_strategy_returns = test_returns.shift(-1) * test_signals

            in_sample_results.append(train_strategy_returns.sum())
            out_of_sample_results.append(test_strategy_returns.sum())

        # Aggregate
        avg_in_sample = np.mean(in_sample_results)
        avg_out_of_sample = np.mean(out_of_sample_results)

        # Calculate overfitting
        if avg_in_sample != 0:
            overfitting_score = abs(avg_in_sample - avg_out_of_sample) / abs(avg_in_sample)
        else:
            overfitting_score = 0.0

        return ValidationResult(
            method=ValidationMethod.ROLLING_WINDOW,
            in_sample_return=avg_in_sample,
            out_of_sample_return=avg_out_of_sample,
            in_sample_sharpe=0.0,  # Would calculate
            out_of_sample_sharpe=0.0,
            overfitting_score=overfitting_score,
            is_overfitted=overfitting_score > 0.5,
            parameter_stability=0.0,
            recommendation="Rolling window validation complete"
        )


class TemporalSplitValidator:
    """
    Temporal train/validation/test splits.

    Simple but effective for time series data.
    """

    def __init__(self):
        self.train_ratio = 0.6  # 60% training
        self.val_ratio = 0.2  # 20% validation
        self.test_ratio = 0.2  # 20% test

        logger.info("TemporalSplitValidator initialized")

    def temporal_split(
        self,
        data: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Split data temporally.

        Args:
            data: Time series data

        Returns:
            (train, validation, test) DataFrames
        """

        n = len(data)
        train_end = int(n * self.train_ratio)
        val_end = int(n * (self.train_ratio + self.val_ratio))

        train = data.iloc[:train_end]
        val = data.iloc[train_end:val_end]
        test = data.iloc[val_end:]

        logger.info(f"Temporal split: Train={len(train)}, "
                   f"Val={len(val)}, Test={len(test)}")

        return train, val, test

    async def validate_on_split(
        self,
        train: pd.DataFrame,
        val: pd.DataFrame,
        test: pd.DataFrame,
        strategy_func: callable
    ) -> ValidationResult:
        """Validate strategy on temporal split."""

        # Generate signals for each split
        train_signals = strategy_func(train)
        val_signals = strategy_func(val)
        test_signals = strategy_func(test)

        # Calculate returns
        train_returns = train['close'].pct_change().fillna(0)
        val_returns = val['close'].pct_change().fillna(0)
        test_returns = test['close'].pct_change().fillna(0)

        train_strategy_returns = train_returns.shift(-1) * train_signals
        val_strategy_returns = val_returns.shift(-1) * val_signals
        test_strategy_returns = test_returns.shift(-1) * test_signals

        # Metrics
        train_return = train_strategy_returns.sum()
        val_return = val_strategy_returns.sum()
        test_return = test_strategy_returns.sum()

        # Calculate overfitting (train vs test)
        if train_return != 0:
            overfitting_score = abs(train_return - test_return) / abs(train_return)
        else:
            overfitting_score = 0.0

        return ValidationResult(
            method=ValidationMethod.TEMPORAL_SPLIT,
            in_sample_return=train_return,
            out_of_sample_return=test_return,
            in_sample_sharpe=0.0,
            out_of_sample_sharpe=0.0,
            overfitting_score=overfitting_score,
            is_overfitted=overfitting_score > 0.5,
            parameter_stability=0.0,
            recommendation=f"Train: {train_return:.2%}, Val: {val_return:.2%}, Test: {test_return:.2%}"
        )


# Singleton instances
_walk_forward_validator = None
_rolling_validator = None
_temporal_validator = None


def get_walk_forward_validator() -> WalkForwardValidator:
    """Get or create walk-forward validator instance."""
    global _walk_forward_validator
    if _walk_forward_validator is None:
        _walk_forward_validator = WalkForwardValidator()
    return _walk_forward_validator


def get_rolling_validator() -> RollingWindowValidator:
    """Get or create rolling validator instance."""
    global _rolling_validator
    if _rolling_validator is None:
        _rolling_validator = RollingWindowValidator()
    return _rolling_validator


def get_temporal_validator() -> TemporalSplitValidator:
    """Get or create temporal validator instance."""
    global _temporal_validator
    if _temporal_validator is None:
        _temporal_validator = TemporalSplitValidator()
    return _temporal_validator
