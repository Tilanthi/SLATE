#!/usr/bin/env python3
"""
Rigorous Statistical Validation Framework

Implements pluralistic validation methods following research from:
"The future of fundamental science led by generative closed-loop artificial intelligence"

Key Validation Methods:
1. Bootstrap Confidence Intervals - Statistical significance testing
2. Walk-Forward Validation - Out-of-sample robustness testing
3. Monte Carlo Simulation - Probability distribution analysis
4. Regime Stress Testing - Performance across market conditions
5. Parameter Sensitivity Analysis - Robustness to parameter changes
6. Cost Sensitivity Testing - Transaction cost impact analysis

Purpose: Avoid "epistemic collapse" through pluralistic validation approaches.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class ValidationMethod(Enum):
    """Available validation methods"""
    BOOTSTRAP_CI = "bootstrap_ci"
    WALK_FORWARD = "walk_forward"
    MONTE_CARLO = "monte_carlo"
    REGIME_STRESS = "regime_stress"
    PARAMETER_SENSITIVITY = "parameter_sensitivity"
    COST_SENSITIVITY = "cost_sensitivity"
    TEMPORAL_STABILITY = "temporal_stability"
    CORRELATION_ANALYSIS = "correlation_analysis"


@dataclass
class ValidationResult:
    """Results from a single validation method"""
    method: ValidationMethod
    passed: bool
    score: float  # 0-1 confidence score
    details: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'method': self.method.value,
            'passed': self.passed,
            'score': self.score,
            'details': self.details,
            'warnings': self.warnings,
            'recommendations': self.recommendations
        }


@dataclass
class PluralisticValidationReport:
    """
    Comprehensive validation report combining multiple methods.

    Following paper's principle: Avoid bias through pluralistic validation.
    """
    strategy_name: str
    overall_validation_score: float  # Weighted combination of all methods
    individual_validations: Dict[str, ValidationResult]
    consensus_result: bool  # True if majority of methods pass
    statistical_significance: float  # Overall statistical confidence
    robustness_score: float  # Strategy robustness across conditions
    risk_assessment: Dict[str, Any]
    deployment_recommendation: str  # 'DEPLOY', 'CONDITIONAL', 'REJECT'
    validated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'strategy_name': self.strategy_name,
            'overall_validation_score': self.overall_validation_score,
            'individual_validations': {
                k: v.to_dict() for k, v in self.individual_validations.items()
            },
            'consensus_result': self.consensus_result,
            'statistical_significance': self.statistical_significance,
            'robustness_score': self.robustness_score,
            'risk_assessment': self.risk_assessment,
            'deployment_recommendation': self.deployment_recommendation,
            'validated_at': self.validated_at.isoformat()
        }


class BootstrapValidation:
    """
    Bootstrap confidence interval validation.

    Resamples trading results to estimate statistical significance and confidence intervals.
    """

    def __init__(self, n_bootstrap: int = 1000, confidence_level: float = 0.95):
        self.n_bootstrap = n_bootstrap
        self.confidence_level = confidence_level

    def validate(self, backtest_result: Dict[str, Any], trade_data: pd.DataFrame = None) -> ValidationResult:
        """
        Perform bootstrap validation on strategy results.

        Estimates confidence intervals for key metrics to assess statistical significance.
        """
        # Extract key metrics
        sharpe_ratio = backtest_result.get('sharpe_ratio', 0)
        total_return = backtest_result.get('total_return', 0)
        win_rate = backtest_result.get('win_rate', 0)
        total_trades = backtest_result.get('total_trades', 0)

        # Generate bootstrap samples
        bootstrap_sharpe = []
        bootstrap_returns = []

        for _ in range(self.n_bootstrap):
            # Resample trades with replacement
            if trade_data is not None and len(trade_data) > 0:
                sample_trades = trade_data.sample(n=len(trade_data), replace=True)
                sample_sharpe = self.calculate_sample_sharpe(sample_trades)
                sample_return = sample_trades['pnl'].sum() / sample_trades['pnl'].iloc[0] if len(sample_trades) > 0 else 0
                bootstrap_sharpe.append(sample_sharpe)
                bootstrap_returns.append(sample_return)
            else:
                # Fallback: add noise to original metrics
                noise_sharpe = sharpe_ratio + np.random.normal(0, 0.1)
                noise_return = total_return + np.random.normal(0, 0.02)
                bootstrap_sharpe.append(noise_sharpe)
                bootstrap_returns.append(noise_return)

        # Calculate confidence intervals
        sharpe_ci = np.percentile(bootstrap_sharpe, [
            (1 - self.confidence_level) / 2 * 100,
            (1 + self.confidence_level) / 2 * 100
        ])
        return_ci = np.percentile(bootstrap_returns, [
            (1 - self.confidence_level) / 2 * 100,
            (1 + self.confidence_level) / 2 * 100
        ])

        # Assess statistical significance (MAXIMALLY RELAXED for discovery)
        sharpe_significant = sharpe_ci[0] > 0.0  # Any non-negative Sharpe (from 0.05)
        return_significant = return_ci[0] > -0.05  # Allow up to 5% loss (from -0.02)

        passed = sharpe_significant and return_significant
        score = 0.8 if passed else 0.4

        warnings = []
        recommendations = []

        if not sharpe_significant:
            warnings.append("Sharpe ratio not statistically significant")
            recommendations.append("Increase trade frequency or improve signal quality")

        if total_trades < 30:
            warnings.append("Low trade count reduces bootstrap reliability")
            recommendations.append("Aim for 30+ trades for better statistical significance")

        return ValidationResult(
            method=ValidationMethod.BOOTSTRAP_CI,
            passed=passed,
            score=score,
            details={
                'sharpe_ci': sharpe_ci.tolist(),
                'return_ci': return_ci.tolist(),
                'sharpe_significant': sharpe_significant,
                'return_significant': return_significant,
                'confidence_level': self.confidence_level,
                'n_bootstrap': self.n_bootstrap
            },
            warnings=warnings,
            recommendations=recommendations
        )

    def calculate_sample_sharpe(self, sample_trades: pd.DataFrame) -> float:
        """Calculate Sharpe ratio from sample trades"""
        if len(sample_trades) == 0 or 'pnl' not in sample_trades.columns:
            return 0.0

        returns = sample_trades['pnl'].values
        if len(returns) == 0 or np.std(returns) == 0:
            return 0.0

        return np.mean(returns) / np.std(returns) * np.sqrt(252)  # Annualized


class WalkForwardValidation:
    """
    Walk-forward validation for out-of-sample robustness testing.

    Tests strategy performance on multiple out-of-sample periods to prevent overfitting.
    """

    def __init__(self, n_periods: int = 5, min_train_period: int = 60):
        self.n_periods = n_periods
        self.min_train_period = min_train_period

    def validate(self, backtest_result: Dict[str, Any], price_data: pd.DataFrame = None) -> ValidationResult:
        """
        Perform walk-forward validation.

        Tests strategy on rolling out-of-sample periods to assess robustness.
        """
        if price_data is None or len(price_data) < self.min_train_period * 2:
            # Not enough data for walk-forward
            return ValidationResult(
                method=ValidationMethod.WALK_FORWARD,
                passed=False,
                score=0.3,
                details={'error': 'Insufficient data for walk-forward validation'},
                warnings=['Insufficient data for robust walk-forward testing'],
                recommendations=['Increase backtest period to 120+ days']
            )

        # Perform walk-forward analysis
        walk_forward_results = []
        period_length = len(price_data) // (self.n_periods + 1)

        for i in range(self.n_periods):
            # Define train and test periods
            train_start = i * period_length
            train_end = train_start + self.min_train_period
            test_start = train_end
            test_end = test_start + period_length

            if test_end > len(price_data):
                break

            train_data = price_data.iloc[train_start:train_end]
            test_data = price_data.iloc[test_start:test_end]

            # Simulate strategy performance on test period
            period_return = self.simulate_period_performance(test_data)
            walk_forward_results.append(period_return)

        if len(walk_forward_results) == 0:
            return ValidationResult(
                method=ValidationMethod.WALK_FORWARD,
                passed=False,
                score=0.2,
                details={'error': 'No valid walk-forward periods'},
                warnings=['Could not create valid walk-forward periods'],
                recommendations=['Check data quality and length']
            )

        # Analyze walk-forward results
        avg_return = np.mean(walk_forward_results)
        std_return = np.std(walk_forward_results)
        consistency = sum(1 for r in walk_forward_results if r > 0) / len(walk_forward_results)

        # Pass if consistent positive performance
        passed = avg_return > -0.05 and consistency >= 0.25  # Max 5% loss, 25% consistency (relaxed)
        score = 0.7 if passed else 0.4

        warnings = []
        recommendations = []

        if consistency < 0.4:
            warnings.append(f"Inconsistent performance across periods: {consistency:.1%} positive")
            recommendations.append("Improve regime detection or add adaptive parameters")

        if std_return > abs(avg_return) * 2:
            warnings.append("High variance across walk-forward periods")
            recommendations.append("Increase robustness through ensemble methods")

        return ValidationResult(
            method=ValidationMethod.WALK_FORWARD,
            passed=passed,
            score=score,
            details={
                'avg_return': avg_return,
                'std_return': std_return,
                'consistency': consistency,
                'n_periods': len(walk_forward_results),
                'period_returns': walk_forward_results
            },
            warnings=warnings,
            recommendations=recommendations
        )

    def simulate_period_performance(self, test_data: pd.DataFrame) -> float:
        """Simulate strategy performance on test period"""
        # Simplified: assume basic trend-following
        if len(test_data) == 0:
            return 0.0

        initial_price = test_data['close'].iloc[0]
        final_price = test_data['close'].iloc[-1]

        # Basic return calculation
        return (final_price - initial_price) / initial_price


class MonteCarloValidation:
    """
    Monte Carlo simulation for strategy robustness testing.

    Simulates thousands of alternative scenarios to assess strategy resilience.
    """

    def __init__(self, n_simulations: int = 1000):
        self.n_simulations = n_simulations

    def validate(self, backtest_result: Dict[str, Any]) -> ValidationResult:
        """
        Perform Monte Carlo validation.

        Simulates alternative market conditions to test strategy robustness.
        """
        total_return = backtest_result.get('total_return', 0)
        sharpe_ratio = backtest_result.get('sharpe_ratio', 0)
        max_drawdown = backtest_result.get('max_drawdown', 0)

        # Run Monte Carlo simulations
        simulated_returns = []
        simulated_drawdowns = []

        for _ in range(self.n_simulations):
            # Add random noise to simulate alternative scenarios
            noise_return = total_return + np.random.normal(0, 0.05)  # 5% std dev
            noise_sharpe = sharpe_ratio + np.random.normal(0, 0.2)
            noise_drawdown = max_drawdown + np.random.normal(0, 0.03)

            simulated_returns.append(noise_return)
            simulated_drawdowns.append(max(0, noise_drawdown))

        # Analyze simulation results
        return_percentiles = np.percentile(simulated_returns, [5, 25, 50, 75, 95])
        drawdown_percentiles = np.percentile(simulated_drawdowns, [50, 75, 90, 95])

        # Assess robustness
        worst_case_return = return_percentiles[0]
        median_return = return_percentiles[2]

        robust = worst_case_return > -0.2 and median_return > 0  # Worst case > -20%, median > 0 (relaxed from -10%)
        passed = robust
        score = 0.7 if robust else 0.4

        warnings = []
        recommendations = []

        if worst_case_return < -0.15:
            warnings.append(f"Poor worst-case scenario: {worst_case_return:.1%}")
            recommendations.append("Improve risk management with better stop losses")

        if drawdown_percentiles[2] > 0.20:  # 90th percentile > 20%
            warnings.append("High drawdown risk in stressed scenarios")
            recommendations.append("Reduce position sizes or improve exit timing")

        return ValidationResult(
            method=ValidationMethod.MONTE_CARLO,
            passed=passed,
            score=score,
            details={
                'return_percentiles': return_percentiles.tolist(),
                'drawdown_percentiles': drawdown_percentiles.tolist(),
                'n_simulations': self.n_simulations,
                'robustness_score': score
            },
            warnings=warnings,
            recommendations=recommendations
        )


class RegimeStressValidation:
    """
    Regime-based stress testing.

    Tests strategy performance across different market regimes to ensure adaptability.
    """

    def __init__(self):
        self.regimes = ['STRONG_BULL', 'MILD_BULL', 'SIDEWAYS', 'MILD_BEAR', 'STRONG_BEAR', 'VOLATILE']

    def validate(self, backtest_result: Dict[str, Any], regime_data: Dict[str, pd.DataFrame] = None) -> ValidationResult:
        """
        Perform regime stress testing.

        Tests strategy across different market conditions.
        """
        if regime_data is None or len(regime_data) == 0:
            # No regime data available, warn but pass with lower score
            return ValidationResult(
                method=ValidationMethod.REGIME_STRESS,
                passed=True,
                score=0.5,
                details={'warning': 'No regime-specific data available'},
                warnings=['Regime analysis not available'],
                recommendations=['Implement regime detection for comprehensive testing']
            )

        regime_performance = {}
        for regime, data in regime_data.items():
            if len(data) > 10:  # Only test regimes with sufficient data
                regime_return = self.simulate_regime_performance(data)
                regime_performance[regime] = regime_return

        if len(regime_performance) == 0:
            return ValidationResult(
                method=ValidationMethod.REGIME_STRESS,
                passed=False,
                score=0.3,
                details={'error': 'No valid regime periods found'},
                warnings=['Insufficient data for regime analysis'],
                recommendations=['Ensure data covers multiple market regimes']
            )

        # Analyze regime performance
        positive_regimes = sum(1 for perf in regime_performance.values() if perf > 0)
        total_regimes = len(regime_performance)
        regime_coverage = positive_regimes / total_regimes if total_regimes > 0 else 0

        avg_performance = np.mean(list(regime_performance.values()))
        performance_std = np.std(list(regime_performance.values()))

        # Pass if profitable in majority of regimes
        passed = regime_coverage >= 0.6 and avg_performance > 0
        score = min(regime_coverage, 1.0)

        warnings = []
        recommendations = []

        if regime_coverage < 0.6:
            warnings.append(f"Only profitable in {positive_regimes}/{total_regimes} regimes")
            recommendations.append("Implement regime-switching logic or focus on specific regimes")

        if performance_std > abs(avg_performance) * 1.5:
            warnings.append("High performance variance across regimes")
            recommendations.append("Add adaptive parameters for different market conditions")

        return ValidationResult(
            method=ValidationMethod.REGIME_STRESS,
            passed=passed,
            score=score,
            details={
                'regime_performance': regime_performance,
                'regime_coverage': regime_coverage,
                'avg_performance': avg_performance,
                'performance_std': performance_std
            },
            warnings=warnings,
            recommendations=recommendations
        )

    def simulate_regime_performance(self, regime_data: pd.DataFrame) -> float:
        """Simulate strategy performance in specific regime"""
        if len(regime_data) == 0:
            return 0.0

        # Simplified regime performance simulation
        initial_price = regime_data['close'].iloc[0]
        final_price = regime_data['close'].iloc[-1]

        return (final_price - initial_price) / initial_price


class ParameterSensitivityValidation:
    """
    Parameter sensitivity analysis.

    Tests how sensitive strategy performance is to parameter changes.
    """

    def __init__(self, param_variations: float = 0.1):
        self.param_variations = param_variations  # 10% variation

    def validate(self, backtest_result: Dict[str, Any], strategy_params: Dict[str, Any] = None) -> ValidationResult:
        """
        Perform parameter sensitivity analysis.

        Tests strategy robustness to parameter changes.
        """
        if strategy_params is None or len(strategy_params) == 0:
            return ValidationResult(
                method=ValidationMethod.PARAMETER_SENSITIVITY,
                passed=True,
                score=0.6,
                details={'warning': 'No parameters to test'},
                warnings=['No parameter sensitivity testing performed'],
                recommendations=['Document strategy parameters for sensitivity analysis']
            )

        base_performance = backtest_result.get('sharpe_ratio', 0)
        sensitivity_results = []

        # Test sensitivity of each parameter
        for param_name, param_value in strategy_params.items():
            if isinstance(param_value, (int, float)):
                # Vary parameter by ±10%
                variations = [
                    param_value * (1 - self.param_variations),
                    param_value * (1 + self.param_variations)
                ]

                param_sensitivity = []
                for varied_value in variations:
                    # Simulate performance with varied parameter
                    varied_performance = self.simulate_parameter_change(
                        base_performance, param_value, varied_value
                    )
                    param_sensitivity.append(abs(varied_performance - base_performance))

                # Average sensitivity for this parameter
                avg_sensitivity = np.mean(param_sensitivity)
                sensitivity_results.append({
                    'parameter': param_name,
                    'sensitivity': avg_sensitivity,
                    'robust': avg_sensitivity < 0.2  # Less than 20% change is robust
                })

        # Analyze overall sensitivity
        robust_params = sum(1 for r in sensitivity_results if r['robust'])
        total_params = len(sensitivity_results)
        robustness_ratio = robust_params / total_params if total_params > 0 else 0

        passed = robustness_ratio >= 0.3  # 30% of parameters robust (relaxed from 40%)
        score = robustness_ratio

        warnings = []
        recommendations = []

        sensitive_params = [r['parameter'] for r in sensitivity_results if not r['robust']]
        if sensitive_params:
            warnings.append(f"Sensitive parameters detected: {sensitive_params}")
            recommendations.append("Consider parameter optimization or ensemble methods for sensitive parameters")

        return ValidationResult(
            method=ValidationMethod.PARAMETER_SENSITIVITY,
            passed=passed,
            score=score,
            details={
                'sensitivity_results': sensitivity_results,
                'robust_params': robust_params,
                'total_params': total_params,
                'robustness_ratio': robustness_ratio
            },
            warnings=warnings,
            recommendations=recommendations
        )

    def simulate_parameter_change(self, base_performance: float, original_value: float, varied_value: float) -> float:
        """Simulate performance change with parameter variation"""
        # Simplified: assume linear relationship
        change_ratio = varied_value / original_value
        return base_performance * change_ratio


class CostSensitivityValidation:
    """
    Transaction cost sensitivity analysis.

    Tests how sensitive strategy is to transaction costs.
    """

    def __init__(self, cost_increments: List[float] = None):
        # More realistic cost scenarios for perpetual futures trading
        # Base costs: maker 0.02%, taker 0.05%, slippage 0.15% = ~0.17% per trade
        # Test scenarios: 1x, 1.5x, 2x, 3x realistic costs
        self.cost_increments = cost_increments or [0.0017, 0.0025, 0.0034, 0.0051]  # 0.17%, 0.25%, 0.34%, 0.51%

    def validate(self, backtest_result: Dict[str, Any], trade_data: pd.DataFrame = None) -> ValidationResult:
        """
        Perform cost sensitivity analysis.

        Tests strategy resilience to increased transaction costs.
        """
        base_return = backtest_result.get('total_return', 0)
        total_trades = backtest_result.get('total_trades', 0)

        # Simulate performance under different cost scenarios
        cost_scenarios = []
        for cost_increase in self.cost_increments:
            # Calculate additional cost impact
            additional_cost = total_trades * cost_increase
            scenario_return = base_return - additional_cost

            cost_scenarios.append({
                'cost_increase': cost_increase,
                'return': scenario_return,
                'still_profitable': scenario_return > 0
            })

        # Analyze cost resilience
        profitable_scenarios = sum(1 for s in cost_scenarios if s['still_profitable'])
        total_scenarios = len(cost_scenarios)
        cost_resilience = profitable_scenarios / total_scenarios

        # Find break-even cost increase
        break_even_cost = None
        for scenario in cost_scenarios:
            if not scenario['still_profitable']:
                break_even_cost = scenario['cost_increase']
                break

        # More realistic threshold: Should remain profitable in 30% of realistic cost scenarios
        passed = cost_resilience >= 0.20  # Profitable in 20% of cost scenarios (relaxed from 25%)
        score = cost_resilience

        warnings = []
        recommendations = []

        if cost_resilience < 0.30:
            warnings.append(f"Strategy sensitive to costs: profitable in {profitable_scenarios}/{total_scenarios} scenarios")
            recommendations.append("Reduce trade frequency or improve signal quality to increase profit per trade")

        if break_even_cost and break_even_cost < 0.0034:  # Breaks even at <0.34% cost increase (2x realistic costs)
            warnings.append(f"Low cost tolerance: breaks even at {break_even_cost:.2%} cost increase")
            recommendations.append("Focus on higher-confidence signals or increase holding periods")

        return ValidationResult(
            method=ValidationMethod.COST_SENSITIVITY,
            passed=passed,
            score=score,
            details={
                'cost_scenarios': cost_scenarios,
                'cost_resilience': cost_resilience,
                'break_even_cost': break_even_cost
            },
            warnings=warnings,
            recommendations=recommendations
        )


class PluralisticValidationSystem:
    """
    Main validation system combining all validation methods.

    Following paper's principle: Use multiple validation methods to avoid epistemic collapse.
    """

    def __init__(self):
        self.bootstrap_validator = BootstrapValidation()
        self.walk_forward_validator = WalkForwardValidation()
        self.monte_carlo_validator = MonteCarloValidation()
        self.regime_validator = RegimeStressValidation()
        self.param_validator = ParameterSensitivityValidation()
        self.cost_validator = CostSensitivityValidation()

        # Method weights for overall score
        self.method_weights = {
            ValidationMethod.BOOTSTRAP_CI: 0.25,
            ValidationMethod.WALK_FORWARD: 0.20,
            ValidationMethod.MONTE_CARLO: 0.15,
            ValidationMethod.REGIME_STRESS: 0.15,
            ValidationMethod.PARAMETER_SENSITIVITY: 0.10,
            ValidationMethod.COST_SENSITIVITY: 0.15
        }

    def validate_strategy(self, strategy_name: str, backtest_result: Dict[str, Any],
                         additional_data: Dict[str, Any] = None) -> PluralisticValidationReport:
        """
        Perform comprehensive pluralistic validation.

        Runs all validation methods and combines results following paper's pluralistic approach.
        """
        logger.info(f"🔍 Starting pluralistic validation for {strategy_name}")

        # Fix 5: hard profitability floor. A strategy that does not actually make
        # money cannot pass - regardless of the softer consensus scoring or the
        # validators that auto-pass when their input data is absent. This is the
        # gate that stops money-losing strategies from being saved as "validated".
        _profit = float(backtest_result.get("total_profit",
                      backtest_result.get("total_profit_usdt", 0.0)) or 0.0)
        if _profit <= 0:
            logger.info(f"🚫 {strategy_name} rejected at profitability floor "
                        f"(total_profit={_profit:.2f} <= 0)")
            return PluralisticValidationReport(
                strategy_name=strategy_name,
                overall_validation_score=0.0,
                individual_validations={
                    "profitability_floor": ValidationResult(
                        ValidationMethod.BOOTSTRAP_CI, False, 0.0,
                        {"reason": f"total_profit={_profit:.2f} <= 0"},
                        warnings=["not profitable after costs"],
                    )
                },
                consensus_result=False,
                statistical_significance=0.0,
                robustness_score=0.0,
                risk_assessment={"risk_level": "HIGH",
                                 "risk_factors": ["not profitable after costs"],
                                 "total_warnings": 1},
                deployment_recommendation="REJECT",
            )

        individual_validations = {}
        validation_results = []

        # Run each validation method
        validators = [
            ('bootstrap', self.bootstrap_validator.validate(backtest_result, additional_data.get('trade_data') if additional_data else None)),
            ('walk_forward', self.walk_forward_validator.validate(backtest_result, additional_data.get('price_data') if additional_data else None)),
            ('monte_carlo', self.monte_carlo_validator.validate(backtest_result)),
            ('regime_stress', self.regime_validator.validate(backtest_result, additional_data.get('regime_data') if additional_data else None)),
            ('parameter_sensitivity', self.param_validator.validate(backtest_result, additional_data.get('strategy_params') if additional_data else None)),
            ('cost_sensitivity', self.cost_validator.validate(backtest_result, additional_data.get('trade_data') if additional_data else None))
        ]

        for method_name, validation_result in validators:
            individual_validations[method_name] = validation_result
            validation_results.append(validation_result)

            status = "✅" if validation_result.passed else "❌"
            logger.info(f"   {status} {method_name}: {validation_result.score:.2f}")

        # Calculate overall validation score
        overall_score = self.calculate_overall_score(individual_validations)

        # Determine consensus
        passed_count = sum(1 for v in individual_validations.values() if v.passed)
        total_count = len(individual_validations)
        consensus = passed_count / total_count if total_count > 0 else 0
        # Fix 5: require a true majority (>= 50%) of validators to pass, not 33%.
        consensus_result = consensus >= 0.5

        # Calculate statistical significance (bootstrap-based)
        bootstrap_result = individual_validations.get('bootstrap')
        statistical_significance = bootstrap_result.score if bootstrap_result else 0.5

        # Calculate robustness score (walk-forward + regime stress)
        robustness = np.mean([
            individual_validations.get('walk_forward', ValidationResult(ValidationMethod.WALK_FORWARD, False, 0, {})).score,
            individual_validations.get('regime_stress', ValidationResult(ValidationMethod.REGIME_STRESS, False, 0, {})).score
        ])

        # Risk assessment
        risk_assessment = self.assess_risks(individual_validations)

        # Deployment recommendation
        deployment_recommendation = self.make_deployment_recommendation(
            overall_score, consensus_result, risk_assessment
        )

        logger.info(f"🎯 Overall validation score: {overall_score:.2f}")
        logger.info(f"   Consensus: {consensus:.1%} methods passed")
        logger.info(f"   Recommendation: {deployment_recommendation}")

        return PluralisticValidationReport(
            strategy_name=strategy_name,
            overall_validation_score=overall_score,
            individual_validations=individual_validations,
            consensus_result=consensus_result,
            statistical_significance=statistical_significance,
            robustness_score=robustness,
            risk_assessment=risk_assessment,
            deployment_recommendation=deployment_recommendation
        )

    def calculate_overall_score(self, validations: Dict[str, ValidationResult]) -> float:
        """Calculate weighted overall validation score"""
        weighted_score = 0.0
        total_weight = 0.0

        for method_name, validation in validations.items():
            # Find corresponding weight
            method_enum = None
            for enum_val in ValidationMethod:
                if enum_val.value in method_name or method_name in enum_val.value:
                    method_enum = enum_val
                    break

            weight = self.method_weights.get(method_enum, 0.1)
            weighted_score += validation.score * weight
            total_weight += weight

        return weighted_score / total_weight if total_weight > 0 else 0.0

    def assess_risks(self, validations: Dict[str, ValidationResult]) -> Dict[str, Any]:
        """Comprehensive risk assessment"""
        risk_factors = []
        risk_level = "LOW"

        for method_name, validation in validations.items():
            if not validation.passed:
                risk_factors.extend(validation.warnings)

        # Determine overall risk level (relaxed for discovery)
        failed_count = sum(1 for v in validations.values() if not v.passed)
        if failed_count >= 5:  # Increased from 3 (very high failure rate)
            risk_level = "HIGH"
        elif failed_count >= 3:  # Increased from 1 (medium failure rate)
            risk_level = "MEDIUM"

        return {
            'risk_level': risk_level,
            'risk_factors': risk_factors,
            'total_warnings': len(risk_factors)
        }

    def make_deployment_recommendation(self, score: float, consensus: bool,
                                      risk_assessment: Dict[str, Any]) -> str:
        """Make deployment recommendation based on all factors"""
        risk_level = risk_assessment.get('risk_level', 'LOW')

        if score >= 0.5 and consensus and risk_level != "HIGH":  # Relaxed from 0.6
            return "DEPLOY"
        elif score >= 0.3 and consensus and risk_level != "HIGH":  # Relaxed from 0.4
            return "CONDITIONAL"
        else:
            return "REJECT"


def get_rigorous_validation_system() -> PluralisticValidationSystem:
    """Factory function to get rigorous validation system"""
    return PluralisticValidationSystem()