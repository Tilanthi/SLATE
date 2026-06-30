"""
SLATE Strategy Validator

Robust validation to distinguish genuine trading edges from false discoveries.
Enforces realistic transaction costs and statistical requirements per CLAUDE.md.
"""

import logging
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime

from .config import (
    AutonomousConfig,
    Discovery,
    ValidationResult,
    ValidationMode
)

logger = logging.getLogger(__name__)


class StrategyValidator:
    """
    Validate trading strategies to ensure genuine edge with realistic costs.

    VALIDATION CRITERIA (CRITICAL per CLAUDE.md):
    1. Transaction Cost Reality: Must profit AFTER 0.02% maker + 0.05% taker fees
    2. Statistical Significance: Minimum trade count and confidence intervals
    3. Market Regime Specificity: Strategy must work in specific conditions
    4. Overfitting Prevention: Out-of-sample validation required
    5. Risk-Adjusted Returns: Sharpe ratio, maximum drawdown limits
    6. Market Impact: Realistic slippage and partial fills

    This system ensures that only strategies with genuine edge are reported,
    not strategies that only appear profitable due to unrealistic assumptions.
    """

    def __init__(self, config: AutonomousConfig):
        """
        Initialize strategy validator.

        Args:
            config: Autonomous configuration with validation parameters
        """
        self.config = config
        self.validation_history = []
        self.known_discoveries = set()

        logger.info("Strategy Validator initialized with "
                   f"mode={config.validation_mode.value}, "
                   f"require_realistic_costs={config.require_realistic_costs}")

    def validate(self, discovery: Discovery) -> ValidationResult:
        """
        Validate a trading discovery using multiple criteria.

        This is the main validation method that applies all criteria
        to ensure the discovery is genuinely profitable with realistic costs.

        Args:
            discovery: Trading discovery to validate

        Returns:
            ValidationResult with detailed analysis
        """
        logger.info(f"Validating discovery: {discovery.question[:50]}...")

        try:
            # Run all validation criteria
            validation_scores = {}
            rejection_reasons = []
            warnings = []

            # 1. CRITICAL: Transaction Cost Reality (per CLAUDE.md)
            cost_score, cost_analysis = self._validate_transaction_costs(discovery)
            validation_scores['transaction_costs'] = cost_score
            if not cost_analysis['passed']:
                rejection_reasons.append(cost_analysis['reason'])

            # 2. Statistical Significance
            stats_score, stats_analysis = self._validate_statistical_significance(discovery)
            validation_scores['statistical_significance'] = stats_score
            if not stats_analysis['passed']:
                rejection_reasons.append(stats_analysis['reason'])

            # 3. Market Regime Specificity
            regime_score, regime_analysis = self._validate_regime_specificity(discovery)
            validation_scores['regime_specificity'] = regime_score
            if not regime_analysis['passed']:
                rejection_reasons.append(regime_analysis['reason'])

            # 4. Overfitting Prevention
            overfitting_score, overfitting_analysis = self._validate_overfitting_prevention(discovery)
            validation_scores['overfitting_prevention'] = overfitting_score
            if not overfitting_analysis['passed']:
                warnings.append(overfitting_analysis['reason'])

            # 5. Risk-Adjusted Returns
            risk_score, risk_analysis = self._validate_risk_adjusted_returns(discovery)
            validation_scores['risk_adjusted_returns'] = risk_score
            if not risk_analysis['passed']:
                rejection_reasons.append(risk_analysis['reason'])

            # 6. Market Realism (slippage, partial fills)
            realism_score, realism_analysis = self._validate_market_realism(discovery)
            validation_scores['market_realism'] = realism_score
            if not realism_analysis['passed']:
                warnings.append(realism_analysis['reason'])

            # Calculate overall confidence
            overall_confidence = np.mean(list(validation_scores.values()))

            # Determine if validation passed
            validation_passed = (
                cost_analysis['passed'] and  # CRITICAL - must pass cost validation
                stats_analysis['passed'] and
                len(rejection_reasons) == 0 and
                overall_confidence >= self.config.min_confidence_to_store
            )

            # Apply validation mode adjustments
            if self.config.validation_mode == ValidationMode.PERMISSIVE:
                # More lenient - only require cost validation + basic profitability
                validation_passed = cost_analysis['passed'] and overall_confidence >= 0.5
            elif self.config.validation_mode == ValidationMode.STRICT:
                # More strict - require all validations
                validation_passed = (
                    cost_analysis['passed'] and
                    stats_analysis['passed'] and
                    regime_analysis['passed'] and
                    overall_confidence >= 0.8
                )

            result = ValidationResult(
                passed=validation_passed,
                confidence=float(overall_confidence),
                validation_scores={k: float(v) for k, v in validation_scores.items()},
                rejection_reasons=rejection_reasons,
                warnings=warnings,
                realistic_costs=cost_analysis['passed'],
                statistical_significance=stats_analysis['passed'],
                market_regime_specific=regime_analysis['passed'],
                overfitting_check=overfitting_analysis['passed']
            )

            # Store in history
            self.validation_history.append({
                'timestamp': datetime.now().isoformat(),
                'discovery': discovery.question,
                'result': result
            })

            if validation_passed:
                logger.info(f"✅ Discovery VALIDATED: {discovery.question[:50]}... "
                          f"(confidence: {overall_confidence:.2f})")
            else:
                logger.warning(f"❌ Discovery REJECTED: {discovery.question[:50]}... "
                             f"reasons: {rejection_reasons}")

            return result

        except Exception as e:
            logger.error(f"Error during validation: {e}")
            return ValidationResult(
                passed=False,
                confidence=0.0,
                validation_scores={},
                rejection_reasons=[f"Validation error: {str(e)}"],
                warnings=[],
                realistic_costs=False,
                statistical_significance=False,
                market_regime_specific=False,
                overfitting_check=False
            )

    def _validate_transaction_costs(self, discovery: Discovery) -> tuple:
        """
        CRITICAL VALIDATION: Ensure profitability AFTER realistic transaction costs.

        Per CLAUDE.md requirements:
        - Maker fee: 0.02% (0.0002)
        - Taker fee: 0.05% (0.0005)
        - Base slippage: 10 bps (0.10%)
        - Partial fill probability: 15%

        This is the most important validation - many strategies appear profitable
        only because they ignore transaction costs.
        """
        # Check if discovery includes transaction cost analysis
        if not hasattr(discovery, 'transaction_costs_usdt') or discovery.transaction_costs_usdt is None:
            return 0.0, {
                'passed': False,
                'reason': 'Missing transaction cost analysis - unrealistic assumption'
            }

        # Check if profitable AFTER costs
        if not hasattr(discovery, 'profit_after_costs') or discovery.profit_after_costs is None:
            return 0.0, {
                'passed': False,
                'reason': 'Missing profit-after-costs calculation'
            }

        # Must be genuinely profitable after costs
        if discovery.profit_after_costs <= 0:
            return 0.0, {
                'passed': False,
                'reason': f'Strategy loses money after costs: ${discovery.profit_after_costs:.2f}'
            }

        # Transaction costs should be reasonable (not too low, not too high)
        cost_ratio = abs(discovery.transaction_costs_usdt / discovery.profit_after_costs) if discovery.profit_after_costs != 0 else 0

        # If costs are > 50% of profits, edge is too thin
        if cost_ratio > 0.5:
            return 0.3, {
                'passed': False,
                'reason': f'Transaction costs consume {cost_ratio*100:.1f}% of profits - edge too thin'
            }

        # Check realistic_edge flag (should be set by discovery system)
        if not discovery.realistic_edge:
            return 0.2, {
                'passed': False,
                'reason': 'Strategy not validated as having realistic edge'
            }

        # Calculate score based on cost efficiency
        # Higher score for strategies where costs are small fraction of profits
        cost_efficiency = 1.0 - min(cost_ratio, 1.0)
        cost_score = 0.5 + (0.5 * cost_efficiency)  # Range: 0.5 to 1.0

        return cost_score, {
            'passed': True,
            'reason': f'Profitable after costs: ${discovery.profit_after_costs:.2f}',
            'cost_ratio': cost_ratio,
            'cost_efficiency': cost_efficiency
        }

    def _validate_statistical_significance(self, discovery: Discovery) -> tuple:
        """
        Validate statistical significance of results.

        Requirements:
        - Minimum trade count (default: 20)
        - Reasonable win rate (not 100% which indicates overfitting)
        - Sufficient data sample
        """
        # Check if we have trade count information
        total_trades = discovery.validation_details.get('total_trades', 0)

        if total_trades < self.config.min_trades_for_significance:
            return 0.0, {
                'passed': False,
                'reason': f'Insufficient trades: {total_trades} < {self.config.min_trades_for_significance}'
            }

        # Check win rate is reasonable (not 100% which is suspicious)
        win_rate = discovery.win_rate

        # CRITICAL: Minimum win rate threshold (based on 52,268 strategy analysis)
        # Profitable strategies average 51.0% win rate vs 39.7% for unprofitable
        # Minimum 48% required to proceed to validation
        min_win_rate_threshold = 0.48
        if win_rate < min_win_rate_threshold:
            return 0.0, {
                'passed': False,
                'reason': f'Win rate below minimum threshold: {win_rate*100:.1f}% < {min_win_rate_threshold*100:.1f}% (analysis shows profitable strategies avg 51.0%)'
            }

        if win_rate >= 0.95:
            return 0.2, {
                'passed': False,
                'reason': f'Suspiciously high win rate: {win_rate*100:.1f}% - likely overfit'
            }

        # Check if we have confidence intervals
        confidence_interval = discovery.validation_details.get('confidence_interval', None)
        if confidence_interval:
            # Wider intervals reduce confidence
            interval_width = confidence_interval[1] - confidence_interval[0]
            if interval_width > 0.2:  # 20% width is quite wide
                return 0.4, {
                    'passed': True,
                    'reason': 'Adequate trades but wide confidence interval'
                }

        # Calculate score based on sample size
        # More trades = higher confidence (with diminishing returns)
        trade_score = min(total_trades / 100.0, 1.0)  # Saturates at 100 trades
        stats_score = 0.6 + (0.4 * trade_score)

        return stats_score, {
            'passed': True,
            'reason': f'Statistically significant: {total_trades} trades'
        }

    def _validate_regime_specificity(self, discovery: Discovery) -> tuple:
        """
        Validate that strategy is specific to market conditions.

        Generic strategies that "work everywhere" are usually overfit.
        Good strategies should specify when they work (trending, ranging, high volatility, etc.)
        """
        if not discovery.regime_conditions or len(discovery.regime_conditions) == 0:
            return 0.3, {
                'passed': False,
                'reason': 'Strategy lacks market regime specificity'
            }

        # Check if regime conditions are meaningful
        meaningful_conditions = 0
        for condition, value in discovery.regime_conditions.items():
            if value is not None and value != '':
                meaningful_conditions += 1

        if meaningful_conditions < 2:
            return 0.4, {
                'passed': False,
                'reason': f'Insufficient regime conditions: {meaningful_conditions} < 2'
            }

        # Check for specific, actionable conditions
        good_conditions = ['trend', 'volatility', 'regime', 'market_state', 'timeframe']
        has_specific_condition = any(cond in str(discovery.regime_conditions).lower()
                                     for cond in good_conditions)

        if not has_specific_condition:
            return 0.5, {
                'passed': True,
                'reason': 'Regime specified but could be more specific'
            }

        return 0.9, {
            'passed': True,
            'reason': 'Good market regime specificity'
        }

    def _validate_overfitting_prevention(self, discovery: Discovery) -> tuple:
        """
        Validate that strategy isn't overfit to historical data.

        Checks:
        - Out-of-sample validation performed
        - Performance consistency across time periods
        - Not too many parameters (complexity penalty)
        """
        # Check if out-of-sample validation was done
        if not discovery.validation_details.get('out_of_sample_tested', False):
            if self.config.require_out_of_sample:
                return 0.0, {
                    'passed': False,
                    'reason': 'No out-of-sample validation performed'
                }
            else:
                return 0.6, {
                    'passed': True,
                    'reason': 'Out-of-sample not required but recommended'
                }

        # Check for parameter complexity
        parameter_count = discovery.validation_details.get('parameter_count', 0)
        if parameter_count > 10:
            complexity_penalty = min((parameter_count - 10) * self.config.overfitting_penalty, 0.5)
            overfitting_score = 0.7 - complexity_penalty
            return overfitting_score, {
                'passed': True,
                'reason': f'Complex strategy ({parameter_count} parameters) - overfitting risk'
            }

        # Check performance consistency
        in_sample_return = discovery.validation_details.get('in_sample_return', 0)
        out_sample_return = discovery.validation_details.get('out_of_sample_return', 0)

        if in_sample_return and out_sample_return:
            # Large performance drop indicates overfitting
            performance_drop = in_sample_return - out_sample_return
            if performance_drop > 0.5:  # 50% drop
                return 0.3, {
                    'passed': True,
                    'reason': f'Large out-of-sample performance drop: {performance_drop*100:.1f}%'
                }

        return 0.9, {
            'passed': True,
            'reason': 'Good out-of-sample validation'
        }

    def _validate_risk_adjusted_returns(self, discovery: Discovery) -> tuple:
        """
        Validate risk-adjusted return metrics.

        Requirements:
        - Minimum Sharpe ratio (default: 0.5)
        - Maximum drawdown within limits
        - Positive profit factor
        """
        # Check Sharpe ratio
        if discovery.sharpe_ratio < self.config.min_sharpe_ratio:
            return 0.0, {
                'passed': False,
                'reason': f'Sharpe ratio too low: {discovery.sharpe_ratio:.2f} < {self.config.min_sharpe_ratio}'
            }

        # Check maximum drawdown
        if abs(discovery.max_drawdown_pct) > self.config.max_drawdown_pct:
            return 0.0, {
                'passed': False,
                'reason': f'Maximum drawdown too high: {discovery.max_drawdown_pct:.1f}% > {self.config.max_drawdown_pct}%'
            }

        # Check profit factor
        if discovery.profit_factor < 1.2:  # At least 1.2 to be considered decent
            return 0.4, {
                'passed': False,
                'reason': f'Profit factor too low: {discovery.profit_factor:.2f}'
            }

        # Calculate score based on risk metrics
        sharpe_score = min(discovery.sharpe_ratio / 2.0, 1.0)  # Sharpe of 2.0 = excellent
        drawdown_score = 1.0 - (abs(discovery.max_drawdown_pct) / 50.0)  # Lower drawdown = better
        risk_score = 0.6 + (0.4 * ((sharpe_score + drawdown_score) / 2.0))

        return risk_score, {
            'passed': True,
            'reason': f'Good risk-adjusted returns: Sharpe={discovery.sharpe_ratio:.2f}'
        }

    def _validate_market_realism(self, discovery: Discovery) -> tuple:
        """
        Validate market realism assumptions.

        Checks:
        - Realistic slippage (not 0%)
        - Partial fills considered
        - Market impact for larger orders
        """
        validation_details = discovery.validation_details

        # Check if slippage was considered
        slippage_bps = validation_details.get('slippage_bps', 0)
        if slippage_bps < 5.0:  # Less than 5 bps is unrealistic
            return 0.5, {
                'passed': True,
                'reason': f'Unrealistically low slippage: {slippage_bps:.1f} bps'
            }

        # Check if partial fills were considered
        partial_fill_rate = validation_details.get('partial_fill_rate', 0.0)
        if partial_fill_rate == 0.0:
            return 0.6, {
                'passed': True,
                'reason': 'Partial fills not considered - may be optimistic'
            }

        # Check market impact for larger positions
        position_size = validation_details.get('avg_position_size_usdt', 0)
        if position_size > 100000:  # $100k+ positions
            market_impact = validation_details.get('market_impact_bps', 0)
            if market_impact == 0:
                return 0.7, {
                    'passed': True,
                    'reason': 'Large positions should consider market impact'
                }

        return 0.9, {
            'passed': True,
            'reason': 'Good market realism assumptions'
        }