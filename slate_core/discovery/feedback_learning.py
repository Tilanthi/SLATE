#!/usr/bin/env python3
"""
Discovery Feedback Learning System

Implements closed-loop learning from validation results following research from:
"The future of fundamental science led by generative closed-loop artificial intelligence"

Key Learning Components:
1. Pattern Extraction - Extract success/failure patterns from validation results
2. Bias Updates - Update discovery biases to avoid repeating mistakes
3. Discovery Optimization - Improve discovery efficiency over time
4. Knowledge Base - Build persistent knowledge about what works
5. Adaptive Discovery - Adjust discovery strategy based on learning

Purpose: Avoid "statistical inertia" through continuous learning from feedback.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging
from datetime import datetime
import json
from slate_core.config.paths import CORE_ROOT

logger = logging.getLogger(__name__)


class LearningSourceType(Enum):
    """Types of learning sources"""
    VALIDATION_SUCCESS = "validation_success"
    VALIDATION_FAILURE = "validation_failure"
    REGIME_MISMATCH = "regime_mismatch"
    OVERFITTING_INDICATOR = "overfitting_indicator"
    COST_SENSITIVITY = "cost_sensitivity"
    PARAMETER_INSTABILITY = "parameter_instability"


@dataclass
class LearningPattern:
    """
    Extracted pattern from validation results for learning.
    """
    pattern_type: LearningSourceType
    description: str
    characteristics: Dict[str, Any]
    frequency: int = 1  # How often this pattern occurs
    confidence: float = 0.5  # Confidence in this pattern
    discovered_at: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'pattern_type': self.pattern_type.value,
            'description': self.description,
            'characteristics': self.characteristics,
            'frequency': self.frequency,
            'confidence': self.confidence,
            'discovered_at': self.discovered_at.isoformat(),
            'last_seen': self.last_seen.isoformat()
        }


@dataclass
class DiscoveryBias:
    """
    Bias updates for discovery system based on learning.
    """
    bias_type: str  # 'favor' or 'avoid'
    target_area: str  # What to favor or avoid
    reason: str  # Why this bias exists
    strength: float  # How strong this bias should be (0-1)
    created_at: datetime = field(default_factory=datetime.now)
    effectiveness: float = 0.5  # How well this bias has worked

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'bias_type': self.bias_type,
            'target_area': self.target_area,
            'reason': self.reason,
            'strength': self.strength,
            'created_at': self.created_at.isoformat(),
            'effectiveness': self.effectiveness
        }


class PatternExtractor:
    """
    Extract learning patterns from validation results.

    Following paper's principle: Learn from every experiment, success or failure.
    """

    def __init__(self):
        self.pattern_templates = {
            LearningSourceType.VALIDATION_SUCCESS: self.extract_success_patterns,
            LearningSourceType.VALIDATION_FAILURE: self.extract_failure_patterns,
            LearningSourceType.REGIME_MISMATCH: self.extract_regime_patterns,
            LearningSourceType.OVERFITTING_INDICATOR: self.extract_overfitting_patterns,
            LearningSourceType.COST_SENSITIVITY: self.extract_cost_patterns,
            LearningSourceType.PARAMETER_INSTABILITY: self.extract_parameter_patterns
        }

    def extract_patterns(self, validation_result: Dict[str, Any], strategy_hypothesis: Dict[str, Any]) -> List[LearningPattern]:
        """
        Extract all relevant learning patterns from validation result.

        Analyzes both successes and failures to extract actionable insights.
        """
        patterns = []

        # Determine if validation succeeded or failed
        validation_passed = validation_result.get('overall_validation_score', 0) >= 0.5

        # Extract appropriate patterns
        if validation_passed:
            patterns.extend(self.extract_success_patterns(validation_result, strategy_hypothesis))
        else:
            patterns.extend(self.extract_failure_patterns(validation_result, strategy_hypothesis))

        # Always check for specific pattern types
        patterns.extend(self.extract_regime_patterns(validation_result, strategy_hypothesis))
        patterns.extend(self.extract_cost_patterns(validation_result, strategy_hypothesis))
        patterns.extend(self.extract_overfitting_patterns(validation_result, strategy_hypothesis))

        return patterns

    def extract_success_patterns(self, validation_result: Dict[str, Any], hypothesis: Dict[str, Any]) -> List[LearningPattern]:
        """Extract patterns from successful validations"""
        patterns = []

        # Analyze what made this strategy successful
        hypothesis_type = hypothesis.get('hypothesis_type', 'unknown')
        regime = hypothesis.get('regime_applicability', [])

        pattern = LearningPattern(
            pattern_type=LearningSourceType.VALIDATION_SUCCESS,
            description=f"{hypothesis_type} strategies successful in {regime} regimes",
            characteristics={
                'strategy_type': hypothesis_type,
                'successful_regimes': regime,
                'validation_score': validation_result.get('overall_validation_score', 0),
                'key_factors': self.identify_success_factors(validation_result)
            },
            confidence=0.7
        )

        patterns.append(pattern)

        return patterns

    def extract_failure_patterns(self, validation_result: Dict[str, Any], hypothesis: Dict[str, Any]) -> List[LearningPattern]:
        """Extract patterns from failed validations"""
        patterns = []

        # Analyze why this strategy failed
        individual_validations = validation_result.get('individual_validations', {})

        for method_name, method_result in individual_validations.items():
            if not method_result.get('passed', False):
                # Extract failure pattern for this validation method
                pattern = LearningPattern(
                    pattern_type=LearningSourceType.VALIDATION_FAILURE,
                    description=f"Failed {method_name} validation: {method_result.get('warnings', ['Unknown reason'])[0]}",
                    characteristics={
                        'failed_method': method_name,
                        'failure_reason': method_result.get('warnings', ['Unknown']),
                        'score': method_result.get('score', 0),
                        'strategy_type': hypothesis.get('hypothesis_type', 'unknown')
                    },
                    confidence=0.6
                )

                patterns.append(pattern)

        return patterns

    def extract_regime_patterns(self, validation_result: Dict[str, Any], hypothesis: Dict[str, Any]) -> List[LearningPattern]:
        """Extract regime-related patterns"""
        patterns = []

        # Check if regime mismatch contributed to failure
        regime_test = validation_result.get('individual_validations', {}).get('regime_stress', {})

        if not regime_test.get('passed', True):  # If regime test failed
            regime_performance = regime_test.get('details', {}).get('regime_performance', {})

            # Find which regimes performed poorly
            poor_regimes = [r for r, perf in regime_performance.items() if perf < 0]

            if poor_regimes:
                pattern = LearningPattern(
                    pattern_type=LearningSourceType.REGIME_MISMATCH,
                    description=f"Strategy performs poorly in {poor_regimes} regimes",
                    characteristics={
                        'poor_regimes': poor_regimes,
                        'strategy_type': hypothesis.get('hypothesis_type', 'unknown'),
                        'applicable_regimes': hypothesis.get('regime_applicability', [])
                    },
                    confidence=0.8
                )

                patterns.append(pattern)

        return patterns

    def extract_overfitting_patterns(self, validation_result: Dict[str, Any], hypothesis: Dict[str, Any]) -> List[LearningPattern]:
        """Extract overfitting indicator patterns"""
        patterns = []

        # Check walk-forward vs bootstrap performance
        walk_forward = validation_result.get('individual_validations', {}).get('walk_forward', {})
        bootstrap = validation_result.get('individual_validations', {}).get('bootstrap', {})

        wf_score = walk_forward.get('score', 0)
        bs_score = bootstrap.get('score', 0)

        # If walk-forward much worse than bootstrap, potential overfitting
        if wf_score < bs_score - 0.2:
            pattern = LearningPattern(
                pattern_type=LearningSourceType.OVERFITTING_INDICATOR,
                description="Walk-forward performance much worse than bootstrap - potential overfitting",
                characteristics={
                    'walk_forward_score': wf_score,
                    'bootstrap_score': bs_score,
                    'performance_gap': bs_score - wf_score,
                    'strategy_type': hypothesis.get('hypothesis_type', 'unknown')
                },
                confidence=0.7
            )

            patterns.append(pattern)

        return patterns

    def extract_cost_patterns(self, validation_result: Dict[str, Any], hypothesis: Dict[str, Any]) -> List[LearningPattern]:
        """Extract cost sensitivity patterns"""
        patterns = []

        cost_sensitivity = validation_result.get('individual_validations', {}).get('cost_sensitivity', {})

        if not cost_sensitivity.get('passed', True):
            cost_resilience = cost_sensitivity.get('details', {}).get('cost_resilience', 0)

            pattern = LearningPattern(
                pattern_type=LearningSourceType.COST_SENSITIVITY,
                description=f"Strategy highly cost sensitive: {cost_resilience:.1%} resilience",
                characteristics={
                    'cost_resilience': cost_resilience,
                    'break_even_cost': cost_sensitivity.get('details', {}).get('break_even_cost'),
                    'strategy_type': hypothesis.get('hypothesis_type', 'unknown'),
                    'trade_frequency': hypothesis.get('expected_outcomes', {}).get('min_trades', 0)
                },
                confidence=0.8
            )

            patterns.append(pattern)

        return patterns

    def extract_parameter_patterns(self, validation_result: Dict[str, Any], hypothesis: Dict[str, Any]) -> List[LearningPattern]:
        """Extract parameter stability patterns"""
        patterns = []

        param_sensitivity = validation_result.get('individual_validations', {}).get('parameter_sensitivity', {})

        if not param_sensitivity.get('passed', True):
            sensitivity_results = param_sensitivity.get('details', {}).get('sensitivity_results', [])

            sensitive_params = [r['parameter'] for r in sensitivity_results if not r.get('robust', True)]

            if sensitive_params:
                pattern = LearningPattern(
                    pattern_type=LearningSourceType.PARAMETER_INSTABILITY,
                    description=f"Strategy sensitive to parameters: {sensitive_params}",
                    characteristics={
                        'sensitive_parameters': sensitive_params,
                        'robustness_ratio': param_sensitivity.get('details', {}).get('robustness_ratio', 0),
                        'strategy_type': hypothesis.get('hypothesis_type', 'unknown')
                    },
                    confidence=0.7
                )

                patterns.append(pattern)

        return patterns

    def identify_success_factors(self, validation_result: Dict[str, Any]) -> List[str]:
        """Identify what contributed to success"""
        factors = []

        for method_name, method_result in validation_result.get('individual_validations', {}).items():
            if method_result.get('passed', False):
                factors.append(f"{method_name}_validation_passed")

        return factors


class BiasUpdateSystem:
    """
    Update discovery biases based on learned patterns.

    Following paper's principle: Avoid statistical inertia by updating exploration strategy.
    """

    def __init__(self):
        self.current_biases = {
            'favor_patterns': [],
            'avoid_patterns': [],
            'regime_restrictions': [],
            'parameter_constraints': []
        }

    def update_biases(self, patterns: List[LearningPattern]) -> List[DiscoveryBias]:
        """
        Update discovery biases based on learned patterns.

        Converts patterns into actionable bias updates for the discovery system.
        """
        new_biases = []

        for pattern in patterns:
            if pattern.pattern_type == LearningSourceType.VALIDATION_SUCCESS:
                # Favor successful patterns
                bias = self.create_favor_bias(pattern)
                if bias:
                    new_biases.append(bias)
                    self.current_biases['favor_patterns'].append(bias)

            elif pattern.pattern_type == LearningSourceType.VALIDATION_FAILURE:
                # Avoid failed patterns
                bias = self.create_avoid_bias(pattern)
                if bias:
                    new_biases.append(bias)
                    self.current_biases['avoid_patterns'].append(bias)

            elif pattern.pattern_type == LearningSourceType.REGIME_MISMATCH:
                # Add regime restrictions
                bias = self.create_regime_bias(pattern)
                if bias:
                    new_biases.append(bias)
                    self.current_biases['regime_restrictions'].append(bias)

            elif pattern.pattern_type == LearningSourceType.COST_SENSITIVITY:
                # Add parameter constraints
                bias = self.create_constraint_bias(pattern)
                if bias:
                    new_biases.append(bias)
                    self.current_biases['parameter_constraints'].append(bias)

        return new_biases

    def create_favor_bias(self, pattern: LearningPattern) -> Optional[DiscoveryBias]:
        """Create bias to favor successful patterns"""
        characteristics = pattern.characteristics

        return DiscoveryBias(
            bias_type='favor',
            target_area=characteristics.get('strategy_type', 'unknown'),
            reason=f"Validated successfully in {characteristics.get('successful_regimes', [])} regimes",
            strength=pattern.confidence * 0.3,  # Moderate strength
            effectiveness=0.5
        )

    def create_avoid_bias(self, pattern: LearningPattern) -> Optional[DiscoveryBias]:
        """Create bias to avoid failed patterns"""
        characteristics = pattern.characteristics
        failed_method = characteristics.get('failed_method', 'unknown')

        return DiscoveryBias(
            bias_type='avoid',
            target_area=f"{characteristics.get('strategy_type', 'unknown')}_{failed_method}",
            reason=f"Failed {failed_method} validation: {characteristics.get('failure_reason', ['Unknown'])[0]}",
            strength=pattern.confidence * 0.5,  # Stronger strength for avoidance
            effectiveness=0.5
        )

    def create_regime_bias(self, pattern: LearningPattern) -> Optional[DiscoveryBias]:
        """Create bias to restrict regime usage"""
        characteristics = pattern.characteristics
        poor_regimes = characteristics.get('poor_regimes', [])
        strategy_type = characteristics.get('strategy_type', 'unknown')

        return DiscoveryBias(
            bias_type='avoid',
            target_area=f"{strategy_type}_regime_{poor_regimes[0] if poor_regimes else 'unknown'}",
            reason=f"Strategy performs poorly in {poor_regimes} regimes",
            strength=pattern.confidence * 0.4,
            effectiveness=0.5
        )

    def create_constraint_bias(self, pattern: LearningPattern) -> Optional[DiscoveryBias]:
        """Create bias to constrain parameters"""
        characteristics = pattern.characteristics
        strategy_type = characteristics.get('strategy_type', 'unknown')

        return DiscoveryBias(
            bias_type='avoid',
            target_area=f"{strategy_type}_high_frequency_trading",
            reason=f"Strategy too cost sensitive: {characteristics.get('cost_resilience', 0):.1%} resilience",
            strength=pattern.confidence * 0.3,
            effectiveness=0.5
        )

    def get_current_biases(self) -> Dict[str, List[DiscoveryBias]]:
        """Get current bias state"""
        return self.current_biases


class DiscoveryOptimizer:
    """
    Optimize discovery process based on learned biases.

    Following paper's principle: Adaptive exploration based on feedback.
    """

    def __init__(self):
        self.discovery_history = []
        self.performance_metrics = {
            'success_rate': 0.0,
            'efficiency_score': 0.0,
            'learning_rate': 0.1
        }

    def optimize_discovery_strategy(self, biases: Dict[str, List[DiscoveryBias]]) -> Dict[str, Any]:
        """
        Optimize discovery strategy based on learned biases.

        Returns optimized discovery parameters.
        """
        optimization = {
            'favored_areas': [],
            'avoided_areas': [],
            'regime_focus': [],
            'parameter_constraints': {},
            'exploration_strategy': 'adaptive'
        }

        # Extract favored areas
        for bias in biases.get('favor_patterns', []):
            optimization['favored_areas'].append({
                'area': bias.target_area,
                'strength': bias.strength,
                'reason': bias.reason
            })

        # Extract avoided areas
        for bias in biases.get('avoid_patterns', []):
            optimization['avoided_areas'].append({
                'area': bias.target_area,
                'strength': bias.strength,
                'reason': bias.reason
            })

        # Extract regime restrictions
        for bias in biases.get('regime_restrictions', []):
            if 'regime_' in bias.target_area:
                regime = bias.target_area.split('regime_')[-1]
                optimization['regime_focus'].append({
                    'avoid_regime': regime,
                    'reason': bias.reason
                })

        # Extract parameter constraints
        for bias in biases.get('parameter_constraints', []):
            if 'high_frequency' in bias.target_area:
                optimization['parameter_constraints']['min_trade_interval'] = '4h'
                optimization['parameter_constraints']['max_trades_per_day'] = 2

        return optimization

    def calculate_discovery_efficiency(self, validation_results: List[Dict[str, Any]]) -> float:
        """Calculate discovery efficiency (success rate per attempt)"""
        if len(validation_results) == 0:
            return 0.0

        successful = sum(1 for r in validation_results if r.get('overall_validation_score', 0) >= 0.5)
        return successful / len(validation_results)


class KnowledgeBase:
    """
    Persistent knowledge base for discovered learnings.

    Following paper's principle: Build cumulative knowledge over time.
    """

    def __init__(self, storage_path: str = f'{CORE_ROOT}/discovery/knowledge_base.json'):
        self.storage_path = storage_path
        self.knowledge = {
            'successful_patterns': [],
            'failed_patterns': [],
            'regime_insights': {},
            'cost_insights': {},
            'parameter_insights': {},
            'learning_history': []
        }
        self.load_knowledge()

    def add_pattern(self, pattern: LearningPattern):
        """Add learned pattern to knowledge base"""
        pattern_dict = pattern.to_dict()

        if pattern.pattern_type == LearningSourceType.VALIDATION_SUCCESS:
            self.knowledge['successful_patterns'].append(pattern_dict)
        elif pattern.pattern_type == LearningSourceType.VALIDATION_FAILURE:
            self.knowledge['failed_patterns'].append(pattern_dict)
        elif pattern.pattern_type == LearningSourceType.REGIME_MISMATCH:
            self.knowledge['regime_insights'][pattern.description] = pattern_dict
        elif pattern.pattern_type == LearningSourceType.COST_SENSITIVITY:
            self.knowledge['cost_insights'][pattern.description] = pattern_dict

        self.save_knowledge()

    def query_knowledge(self, query_type: str, **kwargs) -> List[Dict[str, Any]]:
        """Query knowledge base for relevant insights"""
        if query_type == 'successful_patterns':
            return self.knowledge['successful_patterns']
        elif query_type == 'failed_patterns':
            return self.knowledge['failed_patterns']
        elif query_type == 'regime_insights':
            return list(self.knowledge['regime_insights'].values())
        elif query_type == 'cost_insights':
            return list(self.knowledge['cost_insights'].values())
        else:
            return []

    def save_knowledge(self):
        """Save knowledge base to disk"""
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(self.knowledge, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save knowledge base: {e}")

    def load_knowledge(self):
        """Load knowledge base from disk"""
        try:
            with open(self.storage_path, 'r') as f:
                self.knowledge = json.load(f)
        except FileNotFoundError:
            logger.info("Knowledge base not found, creating new one")
        except Exception as e:
            logger.warning(f"Failed to load knowledge base: {e}")


class FeedbackLearningSystem:
    """
    Main feedback learning system integrating all components.

    Following paper's closed-loop learning framework:
    Results → Pattern Extraction → Bias Updates → Discovery Optimization
    """

    def __init__(self):
        self.pattern_extractor = PatternExtractor()
        self.bias_system = BiasUpdateSystem()
        self.discovery_optimizer = DiscoveryOptimizer()
        self.knowledge_base = KnowledgeBase()

        self.learning_cycle_count = 0
        self.efficiency_history = []

    def learn_from_validation_cycle(self, validation_results: List[Dict[str, Any]],
                                   strategy_hypotheses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Learn from complete validation cycle.

        Following paper's principle: Extract patterns from every experiment.
        """
        logger.info("📚 Starting feedback learning cycle")

        # Extract patterns from all validation results
        all_patterns = []
        for validation_result, hypothesis in zip(validation_results, strategy_hypotheses):
            patterns = self.pattern_extractor.extract_patterns(validation_result, hypothesis)
            all_patterns.extend(patterns)

            # Add patterns to knowledge base
            for pattern in patterns:
                self.knowledge_base.add_pattern(pattern)

        logger.info(f"   Extracted {len(all_patterns)} learning patterns")

        # Update biases based on patterns
        new_biases = self.bias_system.update_biases(all_patterns)
        current_biases = self.bias_system.get_current_biases()

        logger.info(f"   Updated biases: {len(new_biases)} new/updated")

        # Optimize discovery strategy
        optimization = self.discovery_optimizer.optimize_discovery_strategy(current_biases)

        # Calculate efficiency
        efficiency = self.discovery_optimizer.calculate_discovery_efficiency(validation_results)
        self.efficiency_history.append(efficiency)

        self.learning_cycle_count += 1

        learning_summary = {
            'learning_cycle': self.learning_cycle_count,
            'patterns_extracted': len(all_patterns),
            'biases_updated': len(new_biases),
            'current_efficiency': efficiency,
            'efficiency_trend': self.calculate_efficiency_trend(),
            'optimization': optimization,
            'knowledge_base_size': len(self.knowledge_base.knowledge['successful_patterns']) +
                                 len(self.knowledge_base.knowledge['failed_patterns'])
        }

        logger.info(f"📊 Learning cycle {self.learning_cycle_count} complete:")
        logger.info(f"   Efficiency: {efficiency:.1%}")
        logger.info(f"   Trends: {learning_summary['efficiency_trend']}")
        logger.info(f"   Knowledge size: {learning_summary['knowledge_base_size']} patterns")

        return learning_summary

    def calculate_efficiency_trend(self) -> str:
        """Calculate efficiency trend over recent cycles"""
        if len(self.efficiency_history) < 3:
            return "INSUFFICIENT_DATA"

        recent = self.efficiency_history[-3:]
        if recent[-1] > recent[0] + 0.05:  # 5% improvement
            return "IMPROVING"
        elif recent[-1] < recent[0] - 0.05:  # 5% decline
            return "DECLINING"
        else:
            return "STABLE"

    def get_discovery_recommendations(self) -> List[str]:
        """Get recommendations for next discovery cycle based on learning"""
        recommendations = []
        biases = self.bias_system.get_current_biases()

        # Recommendations from favored patterns
        for bias in biases['favor_patterns'][:3]:  # Top 3
            recommendations.append(f"Focus on {bias.target_area} strategies: {bias.reason}")

        # Recommendations from avoided patterns
        for bias in biases['avoid_patterns'][:3]:  # Top 3
            recommendations.append(f"Avoid {bias.target_area}: {bias.reason}")

        # Efficiency-based recommendations
        if len(self.efficiency_history) >= 3:
            trend = self.calculate_efficiency_trend()
            if trend == "DECLINING":
                recommendations.append("Discovery efficiency declining - consider regime change or strategy diversification")
            elif trend == "IMPROVING":
                recommendations.append("Discovery efficiency improving - continue current approach")

        return recommendations

    def learn_from_validation_results(self, validation_results: Dict, regime_info: Dict) -> None:
        """
        Learn from validation results to improve future hypothesis generation.

        This implements Phase 5 continuous learning with:
        - Track strategy performance by regime
        - Adaptive threshold optimization
        - Hypothesis quality scoring

        This is the key to continuous improvement in validation success rate.
        """
        logger.info("📚 Starting enhanced feedback learning cycle")

        # Track performance by strategy type and regime
        strategies_tested = validation_results.get('strategies_tested', [])
        strategies_validated = validation_results.get('strategies_validated', [])

        for strategy_result in strategies_tested:
            strategy_type = strategy_result.get('hypothesis_type', 'unknown')
            passed_validation = strategy_result.get('passed', False)

            # Update performance tracking
            self._update_strategy_regime_performance(strategy_type, regime_info['regime'], passed_validation)

        # Adjust thresholds if needed
        self._optimize_validation_thresholds(regime_info['regime'])

        # Update generation priorities
        self._update_generation_priorities()

        logger.info("   Enhanced feedback learning complete")

    def _update_strategy_regime_performance(self, strategy_type: str, regime: str, passed: bool) -> None:
        """Update performance tracking for strategy-regime combinations"""

        # Initialize performance tracking if not exists
        if not hasattr(self, 'performance_tracking'):
            self.performance_tracking = {}

        key = f"{strategy_type}_{regime}"

        if key not in self.performance_tracking:
            self.performance_tracking[key] = {
                'attempts': 0,
                'successes': 0,
                'success_rate': 0.0,
                'last_updated': datetime.now()
            }

        self.performance_tracking[key]['attempts'] += 1
        if passed:
            self.performance_tracking[key]['successes'] += 1

        self.performance_tracking[key]['success_rate'] = (
            self.performance_tracking[key]['successes'] / self.performance_tracking[key]['attempts']
        )
        self.performance_tracking[key]['last_updated'] = datetime.now()

        logger.debug(f"Updated {key} performance: {self.performance_tracking[key]['success_rate']:.2%}")

    def _optimize_validation_thresholds(self, regime: str) -> None:
        """
        Automatically adjust validation thresholds based on success rates.

        If success rate too low (<2%): relax thresholds
        If success rate too high (>30%): tighten thresholds
        Target: 5-15% success rate
        """
        if not hasattr(self, 'performance_tracking'):
            return

        # Calculate overall success rate for this regime
        regime_attempts = 0
        regime_successes = 0

        for key, perf_data in self.performance_tracking.items():
            if key.endswith(f"_{regime}"):
                regime_attempts += perf_data['attempts']
                regime_successes += perf_data['successes']

        if regime_attempts < 10:  # Need minimum data
            return

        success_rate = regime_successes / regime_attempts

        # Adjust thresholds based on success rate
        if success_rate < 0.02:  # Less than 2% success
            logger.info(f"   Low success rate ({success_rate:.1%}) - thresholds may be too strict")
            # Could implement automatic threshold relaxation here
        elif success_rate > 0.30:  # More than 30% success
            logger.info(f"   High success rate ({success_rate:.1%}) - thresholds may be too lenient")
            # Could implement automatic threshold tightening here

    def _update_generation_priorities(self) -> None:
        """
        Update which hypothesis types get priority based on success rates.

        This implements adaptive hypothesis generation by prioritizing
        successful strategy-regime combinations.
        """
        if not hasattr(self, 'performance_tracking'):
            return

        # Initialize priority tracking
        if not hasattr(self, 'priority_combinations'):
            self.priority_combinations = set()
        if not hasattr(self, 'deprecated_combinations'):
            self.deprecated_combinations = set()

        for key, perf_data in self.performance_tracking.items():
            strategy_type, regime = key.split('_')

            # Prioritize high-success combinations (>10% success rate)
            if perf_data['success_rate'] > 0.10 and perf_data['attempts'] >= 5:
                self.priority_combinations.add((strategy_type, regime))
                logger.info(f"   Prioritizing {strategy_type} in {regime} (success: {perf_data['success_rate']:.1%})")

            # Deprioritize low-success combinations (<2% success, 100+ attempts)
            if perf_data['success_rate'] < 0.02 and perf_data['attempts'] > 100:
                self.deprecated_combinations.add((strategy_type, regime))
                logger.info(f"   Deprioritizing {strategy_type} in {regime} (success: {perf_data['success_rate']:.1%})")

    def get_priority_combinations(self) -> set:
        """Get high-priority strategy-regime combinations"""
        return getattr(self, 'priority_combinations', set())

    def get_deprecated_combinations(self) -> set:
        """Get deprecated strategy-regime combinations"""
        return getattr(self, 'deprecated_combinations', set())

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get summary of performance tracking for analysis"""
        if not hasattr(self, 'performance_tracking'):
            return {'status': 'no_performance_data'}

        summary = {
            'total_combinations': len(self.performance_tracking),
            'combinations_tracked': list(self.performance_tracking.keys()),
            'top_performers': [],
            'underperformers': []
        }

        # Get top and bottom performers
        sorted_perf = sorted(
            self.performance_tracking.items(),
            key=lambda x: x[1]['success_rate'],
            reverse=True
        )

        for key, perf_data in sorted_perf[:5]:  # Top 5
            if perf_data['attempts'] >= 5:
                summary['top_performers'].append({
                    'combination': key,
                    'success_rate': perf_data['success_rate'],
                    'attempts': perf_data['attempts']
                })

        for key, perf_data in sorted_perf[-5:]:  # Bottom 5
            if perf_data['attempts'] >= 5:
                summary['underperformers'].append({
                    'combination': key,
                    'success_rate': perf_data['success_rate'],
                    'attempts': perf_data['attempts']
                })

        return summary

    def reset_learning(self):
        """Reset learning system (use with caution)"""
        self.bias_system = BiasUpdateSystem()
        self.discovery_optimizer = DiscoveryOptimizer()
        self.learning_cycle_count = 0
        self.efficiency_history = []
        logger.warning("⚠️  Learning system reset")


class EnhancedFeedbackLearning:
    """
    Enhanced feedback learning system incorporating swarm intelligence.

    This class extends the existing feedback learning system to incorporate:
    1. Swarm collective intelligence learning
    2. Pheromone signal learning
    3. Multi-source feedback integration (closed-loop + swarm)

    Following the principle: Learn from ALL sources of intelligence.
    """

    def __init__(self):
        """Initialize enhanced feedback learning system."""
        # Existing feedback learning system
        self.feedback_system = FeedbackLearningSystem()

        # Swarm-specific learning
        self.swarm_learning_history = []
        self.pheromone_effectiveness = {}
        self.collective_intelligence_patterns = []

        # Integration statistics
        self.learning_sources_count = {
            'closed_loop': 0,
            'swarm': 0,
            'combined': 0
        }

        logger.info("🧠 Enhanced feedback learning system initialized with swarm integration")

    def learn_from_validation_results(self, validation_results: List[Any],
                                     swarm_results: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Learn from both closed-loop and swarm validation results.

        Args:
            validation_results: List of validation results from both systems
            swarm_results: Optional swarm collective intelligence results

        Returns:
            Learning summary incorporating all intelligence sources
        """
        logger.info("📚 Starting enhanced feedback learning (Closed-Loop + Swarm)")

        # 1. Existing closed-loop learning
        try:
            # Convert validation results to format expected by existing system
            closed_loop_results = [self._convert_validation_result(r) for r in validation_results]

            closed_loop_learning = self.feedback_system.learn_from_validation_cycle(
                closed_loop_results,
                []  # Strategy hypotheses would be passed separately if available
            )

            self.learning_sources_count['closed_loop'] += 1
            logger.info(f"✅ Closed-loop learning: {closed_loop_learning['patterns_extracted']} patterns")

        except Exception as e:
            logger.warning(f"Closed-loop learning failed (non-critical): {e}")
            closed_loop_learning = {'patterns_extracted': 0, 'efficiency': 0.0}

        # 2. Swarm intelligence learning
        swarm_learning = {'patterns_extracted': 0, 'efficiency': 0.0}
        if swarm_results and swarm_results.get('status') == 'success':
            try:
                swarm_learning = self._learn_from_swarm_intelligence(swarm_results)
                self.learning_sources_count['swarm'] += 1
                logger.info(f"✅ Swarm learning: {swarm_learning['patterns_extracted']} patterns")
            except Exception as e:
                logger.warning(f"Swarm learning failed (non-critical): {e}")

        # 3. Combined intelligence synthesis
        combined_learning = self._synthesize_combined_intelligence(
            closed_loop_learning,
            swarm_learning,
            validation_results
        )

        self.learning_sources_count['combined'] += 1

        # 4. Update collective intelligence patterns
        self._update_collective_intelligence(validation_results, swarm_results)

        learning_summary = {
            'status': 'success',
            'learning_sources': self.learning_sources_count,
            'closed_loop_patterns': closed_loop_learning.get('patterns_extracted', 0),
            'swarm_patterns': swarm_learning.get('patterns_extracted', 0),
            'combined_patterns': combined_learning.get('patterns_extracted', 0),
            'overall_efficiency': combined_learning.get('efficiency', 0.0),
            'collective_intelligence_size': len(self.collective_intelligence_patterns),
            'timestamp': datetime.now().isoformat()
        }

        logger.info(f"🎯 Enhanced learning complete: {learning_summary}")

        return learning_summary

    def _learn_from_swarm_intelligence(self, swarm_results: Dict[str, Any]) -> Dict[str, Any]:
        """Learn from swarm collective intelligence results."""
        patterns_extracted = 0

        try:
            # Extract pheromone signals
            pheromone_signals = swarm_results.get('pheromone_signals', [])

            # Learn from pheromone effectiveness
            for pheromone in pheromone_signals:
                pheromone_type = pheromone.get('pheromone_type', 'DISCOVERY')
                strength = pheromone.get('strength', 0.0)

                # Track pheromone effectiveness over time
                if pheromone_type not in self.pheromone_effectiveness:
                    self.pheromone_effectiveness[pheromone_type] = []

                self.pheromone_effectiveness[pheromone_type].append({
                    'strength': strength,
                    'timestamp': datetime.now()
                })

                patterns_extracted += 1

            # Extract collective intelligence patterns
            collective_intelligence = swarm_results.get('collective_intelligence', {})
            successful_patterns = collective_intelligence.get('successful_patterns', [])

            for pattern in successful_patterns:
                self.collective_intelligence_patterns.append({
                    'pattern': pattern,
                    'source': 'swarm',
                    'timestamp': datetime.now()
                })
                patterns_extracted += 1

            # Calculate swarm learning efficiency
            hypotheses_generated = swarm_results.get('hypotheses_generated', 0)
            strategies_validated = swarm_results.get('strategies_validated', 0)

            efficiency = strategies_validated / hypotheses_generated if hypotheses_generated > 0 else 0.0

            return {
                'patterns_extracted': patterns_extracted,
                'efficiency': efficiency,
                'pheromone_signals_processed': len(pheromone_signals)
            }

        except Exception as e:
            logger.warning(f"Error learning from swarm intelligence: {e}")
            return {'patterns_extracted': 0, 'efficiency': 0.0}

    def _synthesize_combined_intelligence(self, closed_loop_learning: Dict,
                                         swarm_learning: Dict,
                                         validation_results: List[Any]) -> Dict[str, Any]:
        """Synthesize combined intelligence from both sources."""
        # Combine pattern counts
        combined_patterns = (
            closed_loop_learning.get('patterns_extracted', 0) +
            swarm_learning.get('patterns_extracted', 0)
        )

        # Calculate combined efficiency (weighted average)
        closed_loop_weight = 0.7  # Closed-loop is more established
        swarm_weight = 0.3  # Swarm is newer but valuable

        combined_efficiency = (
            closed_loop_learning.get('efficiency', 0.0) * closed_loop_weight +
            swarm_learning.get('efficiency', 0.0) * swarm_weight
        )

        return {
            'patterns_extracted': combined_patterns,
            'efficiency': combined_efficiency,
            'intelligence_sources': ['closed_loop', 'swarm']
        }

    def _update_collective_intelligence(self, validation_results: List[Any],
                                      swarm_results: Dict[str, Any] = None):
        """Update collective intelligence patterns from both sources."""
        for validation in validation_results:
            try:
                # Extract successful patterns
                if hasattr(validation, 'is_successful') and validation.is_successful():
                    self.collective_intelligence_patterns.append({
                        'pattern': {
                            'source': 'validation',
                            'strategy': getattr(validation, 'strategy_name', 'unknown'),
                            'performance': getattr(validation, 'overall_score', 0.0)
                        },
                        'timestamp': datetime.now()
                    })
            except Exception as e:
                logger.debug(f"Error extracting pattern from validation: {e}")

    def _convert_validation_result(self, result: Any) -> Dict[str, Any]:
        """Convert validation result to format expected by existing system."""
        if hasattr(result, 'to_dict'):
            return result.to_dict()
        elif isinstance(result, dict):
            return result
        else:
            return {'status': 'unknown', 'is_successful': False}

    def get_collective_intelligence_summary(self) -> Dict[str, Any]:
        """Get summary of collective intelligence patterns."""
        return {
            'total_patterns': len(self.collective_intelligence_patterns),
            'pheromone_effectiveness': self.pheromone_effectiveness,
            'learning_sources': self.learning_sources_count,
            'recent_patterns': [
                p for p in self.collective_intelligence_patterns[-10:]
            ] if self.collective_intelligence_patterns else []
        }


def get_enhanced_feedback_learning() -> EnhancedFeedbackLearning:
    """Factory function to get enhanced feedback learning system"""
    return EnhancedFeedbackLearning()


def get_feedback_learning_system() -> FeedbackLearningSystem:
    """Factory function to get feedback learning system"""
    return FeedbackLearningSystem()