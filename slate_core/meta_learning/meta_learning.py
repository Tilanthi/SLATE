#!/usr/bin/env python3
"""
SLATE Meta-Learning System

Phase 8: Self-Evolution Architecture (Weeks 29-32)

Implements meta-learning capabilities:
- Learn what works
- Transfer learning
- Avoid mistakes
- Best practices extraction

Critical for continuous system improvement.

Author: SLATE Evolution
Date: 2026-04-30
Priority: HIGH - Continuous improvement
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
from collections import defaultdict
import pickle

logger = logging.getLogger(__name__)


class LearningType(Enum):
    """Types of learning."""
    SUCCESS_PATTERN = "success_pattern"  # What leads to success
    FAILURE_PATTERN = "failure_pattern"  # What leads to failure
    MARKET_REGIME = "market_regime"  # Regime-specific learning
    PARAMETER_IMPORTANCE = "parameter_importance"  # Feature importance
    TRANSFER_SOURCE = "transfer_source"  # Transferable knowledge


@dataclass
class LearnedPattern:
    """A learned pattern."""
    pattern_type: LearningType
    description: str
    confidence: float

    # Pattern details
    conditions: Dict[str, Any]
    outcome: str
    frequency: int  # How often observed
    success_rate: float

    # Metadata
    learned_at: datetime
    last_observed: datetime
    source_context: Dict[str, Any]


@dataclass
class BestPractice:
    """A best practice."""
    title: str
    description: str
    category: str

    # Evidence
    success_cases: int
    failure_cases: int
    confidence: float

    # Applicability
    applicable_situations: List[str]
    counter_indications: List[str]

    # Implementation
    implementation: str
    validation_method: str


class PatternExtractor:
    """
    Extract patterns from strategy performance.

    Learns what works and what doesn't.
    """

    def __init__(self):
        self.patterns: List[LearnedPattern] = []
        self.observations: List[Dict[str, Any]] = []

        logger.info("PatternExtractor initialized")

    async def extract_patterns(
        self,
        strategies: List[Dict[str, Any]],
        market_context: Dict[str, Any]
    ) -> List[LearnedPattern]:
        """
        Extract patterns from strategy results.

        Args:
            strategies: Strategy results
            market_context: Market conditions

        Returns:
            Learned patterns
        """

        new_patterns = []

        # Analyze successful strategies
        successful = [s for s in strategies if s.get('return', 0) > 0]
        failed = [s for s in strategies if s.get('return', 0) <= 0]

        if successful:
            # Extract success patterns
            success_pattern = await self._extract_success_pattern(successful, market_context)
            new_patterns.append(success_pattern)

        if failed:
            # Extract failure patterns
            failure_pattern = await self._extract_failure_pattern(failed, market_context)
            new_patterns.append(failure_pattern)

        # Extract regime-specific patterns
        regime_patterns = await self._extract_regime_patterns(strategies, market_context)
        new_patterns.extend(regime_patterns)

        # Store patterns
        self.patterns.extend(new_patterns)

        # Store observations
        self.observations.extend(strategies)

        # Trim history
        if len(self.observations) > 10000:
            self.observations = self.observations[-10000:]

        return new_patterns

    async def _extract_success_pattern(
        self,
        successful_strategies: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> LearnedPattern:
        """Extract success pattern."""

        # Common characteristics
        common_params = self._find_common_parameters(successful_strategies)

        # Calculate success rate
        success_rate = len(successful_strategies) / max(1, len(self.observations) + len(successful_strategies))

        pattern = LearnedPattern(
            pattern_type=LearningType.SUCCESS_PATTERN,
            description=f"Parameters {list(common_params.keys())} associated with success",
            confidence=success_rate,
            conditions=common_params,
            outcome="positive_return",
            frequency=len(successful_strategies),
            success_rate=success_rate,
            learned_at=datetime.now(),
            last_observed=datetime.now(),
            source_context=context
        )

        return pattern

    async def _extract_failure_pattern(
        self,
        failed_strategies: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> LearnedPattern:
        """Extract failure pattern."""

        common_params = self._find_common_parameters(failed_strategies)

        pattern = LearnedPattern(
            pattern_type=LearningType.FAILURE_PATTERN,
            description=f"Parameters {list(common_params.keys())} associated with failure",
            confidence=0.7,
            conditions=common_params,
            outcome="negative_return",
            frequency=len(failed_strategies),
            success_rate=0.0,
            learned_at=datetime.now(),
            last_observed=datetime.now(),
            source_context=context
        )

        return pattern

    async def _extract_regime_patterns(
        self,
        strategies: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> List[LearnedPattern]:
        """Extract regime-specific patterns."""

        patterns = []
        regime = context.get('regime', 'UNKNOWN')

        # Group by strategy type
        by_type = defaultdict(list)
        for strategy in strategies:
            strategy_type = strategy.get('type', 'unknown')
            by_type[strategy_type].append(strategy)

        # Analyze performance by type in this regime
        for strategy_type, type_strategies in by_type.items():
            returns = [s.get('return', 0) for s in type_strategies]
            avg_return = np.mean(returns) if returns else 0

            if len(returns) >= 3:  # Need minimum samples
                pattern = LearnedPattern(
                    pattern_type=LearningType.MARKET_REGIME,
                    description=f"{strategy_type} strategies in {regime} regime",
                    confidence=min(1.0, len(returns) / 10),
                    conditions={
                        'regime': regime,
                        'strategy_type': strategy_type
                    },
                    outcome="positive" if avg_return > 0 else "negative",
                    frequency=len(returns),
                    success_rate=max(0, avg_return),
                    learned_at=datetime.now(),
                    last_observed=datetime.now(),
                    source_context=context
                )
                patterns.append(pattern)

        return patterns

    def _find_common_parameters(
        self,
        strategies: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Find common parameters among strategies."""

        if not strategies:
            return {}

        # Extract all parameters
        all_params = []
        for strategy in strategies:
            params = strategy.get('parameters', {})
            all_params.append(params)

        if not all_params:
            return {}

        # Find common keys
        common_keys = set(all_params[0].keys())
        for params in all_params[1:]:
            common_keys &= set(params.keys())

        # Calculate average values for common keys
        common_params = {}
        for key in common_keys:
            values = [params.get(key) for params in all_params if key in params]
            if values:
                # Use most common value for categorical, mean for numeric
                if isinstance(values[0], (int, float)):
                    common_params[key] = np.mean(values)
                else:
                    # Most common value
                    from collections import Counter
                    common_params[key] = Counter(values).most_common(1)[0][0]

        return common_params


class TransferLearning:
    """
    Transfer learning between domains.

    Applies knowledge from one context to another.
    """

    def __init__(self):
        self.knowledge_base: Dict[str, List[LearnedPattern]] = {}
        logger.info("TransferLearning initialized")

    async def find_transferable_knowledge(
        self,
        source_context: Dict[str, Any],
        target_context: Dict[str, Any]
    ) -> List[LearnedPattern]:
        """
        Find knowledge transferable from source to target.

        Args:
            source_context: Source market/context
            target_context: Target market/context

        Returns:
            Transferable patterns
        """

        transferable = []

        # Get knowledge from source
        source_regime = source_context.get('regime', 'UNKNOWN')
        source_patterns = self.knowledge_base.get(source_regime, [])

        # Check applicability to target
        target_regime = target_context.get('regime', 'UNKNOWN')

        for pattern in source_patterns:
            # Check if pattern applies to target regime
            if await self._is_applicable(pattern, target_context):
                transferable.append(pattern)

        return transferable

    async def _is_applicable(
        self,
        pattern: LearnedPattern,
        target_context: Dict[str, Any]
    ) -> bool:
        """Check if pattern is applicable to target context."""

        # Regime transfer
        if pattern.pattern_type == LearningType.MARKET_REGIME:
            pattern_regime = pattern.conditions.get('regime')
            target_regime = target_context.get('regime')

            # Same regime -> applicable
            if pattern_regime == target_regime:
                return True

            # Similar regimes (bull/bear) -> maybe applicable
            similar_regimes = [
                ('bull', 'high_volatility'),
                ('bear', 'high_volatility'),
                ('sideways', 'low_volatility')
            ]
            for pair in similar_regimes:
                if pattern_regime in pair and target_regime in pair:
                    return True

            return False

        # Parameter patterns -> generally applicable
        if pattern.pattern_type in [LearningType.SUCCESS_PATTERN, LearningType.FAILURE_PATTERN]:
            # Check if success rate is high enough
            return pattern.confidence > 0.6

        return False

    async def transfer_knowledge(
        self,
        patterns: List[LearnedPattern],
        target_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply transferred knowledge to target.

        Args:
            patterns: Transferable patterns
            target_context: Target context

        Returns:
            Transfer recommendations
        """

        recommendations = {
            'applicable_patterns': [],
            'parameter_suggestions': {},
            'strategy_suggestions': [],
            'warnings': []
        }

        for pattern in patterns:
            if pattern.pattern_type == LearningType.SUCCESS_PATTERN:
                recommendations['applicable_patterns'].append(pattern.description)

                # Extract parameter suggestions
                for key, value in pattern.conditions.items():
                    if key not in recommendations['parameter_suggestions']:
                        recommendations['parameter_suggestions'][key] = []
                    recommendations['parameter_suggestions'][key].append(value)

            elif pattern.pattern_type == LearningType.MARKET_REGIME:
                strategy_type = pattern.conditions.get('strategy_type')
                if pattern.outcome == "positive":
                    recommendations['strategy_suggestions'].append(strategy_type)
                else:
                    recommendations['warnings'].append(
                        f"{strategy_type} has underperformed in similar conditions"
                    )

        return recommendations


class BestPracticesExtractor:
    """
    Extract and maintain best practices.

    Learns from experience what approaches work best.
    """

    def __init__(self):
        self.best_practices: List[BestPractice] = {}
        self.evidence_log: List[Dict[str, Any]] = []

        logger.info("BestPracticesExtractor initialized")

    async def extract_best_practices(
        self,
        outcomes: List[Dict[str, Any]]
    ) -> List[BestPractice]:
        """
        Extract best practices from outcomes.

        Args:
            outcomes: List of strategy outcomes with context

        Returns:
            Best practices
        """

        practices = []

        # Group by approach
        by_approach = defaultdict(list)
        for outcome in outcomes:
            approach = outcome.get('approach', 'unknown')
            by_approach[approach].append(outcome)

        # Analyze each approach
        for approach, approach_outcomes in by_approach.items():
            successes = [o for o in approach_outcomes if o.get('success', False)]
            failures = [o for o in approach_outcomes if not o.get('success', True)]

            if len(approach_outcomes) >= 5:  # Minimum sample size
                success_rate = len(successes) / len(approach_outcomes)

                if success_rate > 0.7:
                    # This is a best practice
                    practice = BestPractice(
                        title=f"Use {approach}",
                        description=f"{approach} has {success_rate:.1%} success rate",
                        category=approach_outcomes[0].get('category', 'general'),
                        success_cases=len(successes),
                        failure_cases=len(failures),
                        confidence=success_rate,
                        applicable_situations=self._extract_applicable_situations(successes),
                        counter_indications=self._extract_counter_indications(failures),
                        implementation=approach_outcomes[0].get('implementation', ''),
                        validation_method="backtest_validation"
                    )
                    practices.append(practice)

        # Store
        self.best_practices.extend(practices)

        # Log evidence
        self.evidence_log.extend(outcomes)

        return practices

    def _extract_applicable_situations(self, successes: List[Dict[str, Any]]) -> List[str]:
        """Extract situations where practice applies."""
        situations = set()

        for success in successes:
            context = success.get('context', {})
            regime = context.get('regime')
            if regime:
                situations.add(f"{regime}_regime")

            market = context.get('market')
            if market:
                situations.add(f"{market}_market")

        return list(situations)

    def _extract_counter_indications(self, failures: List[Dict[str, Any]]) -> List[str]:
        """Extract situations where practice should be avoided."""
        counter_indications = []

        for failure in failures:
            context = failure.get('context', {})
            regime = context.get('regime')
            if regime:
                counter_indications.append(f"{regime}_regime")

            reason = failure.get('reason')
            if reason:
                counter_indications.append(reason)

        return list(set(counter_indications))


class MistakeAvoidance:
    """
    Learn from mistakes to avoid repeating them.

    Builds a catalog of what doesn't work.
    """

    def __init__(self):
        self.mistakes: List[Dict[str, Any]] = []
        self.avoidance_rules: List[Dict[str, Any]] = []

        logger.info("MistakeAvoidance initialized")

    async def learn_from_mistake(
        self,
        mistake: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Learn from a mistake.

        Args:
            mistake: Mistake details

        Returns:
            Avoidance rule
        """

        # Store mistake
        self.mistakes.append(mistake)

        # Extract pattern
        pattern = {
            'conditions': mistake.get('conditions', {}),
            'outcomes': mistake.get('outcomes', {}),
            'context': mistake.get('context', {})
        }

        # Create avoidance rule
        rule = {
            'rule_id': f"avoid_{len(self.avoidance_rules)}",
            'description': mistake.get('description', 'Avoid this pattern'),
            'pattern': pattern,
            'avoidance_strategy': mistake.get('avoidance_strategy', 'Do not use'),
            'confidence': mistake.get('confidence', 0.8),
            'created_at': datetime.now().isoformat()
        }

        self.avoidance_rules.append(rule)

        return rule

    async def check_avoidance(
        self,
        proposed_action: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Check if proposed action matches any avoidance patterns.

        Args:
            proposed_action: Action to check

        Returns:
            Matching avoidance rules
        """

        matches = []

        for rule in self.avoidance_rules:
            pattern = rule['pattern']

            # Check if conditions match
            if self._matches_pattern(proposed_action, pattern):
                matches.append(rule)

        return matches

    def _matches_pattern(
        self,
        action: Dict[str, Any],
        pattern: Dict[str, Any]
    ) -> bool:
        """Check if action matches pattern."""

        conditions = pattern.get('conditions', {})

        for key, value in conditions.items():
            if key not in action:
                return False

            if isinstance(value, (int, float)):
                # Range check
                if abs(action[key] - value) > value * 0.1:
                    return False
            else:
                # Exact match
                if action[key] != value:
                    return False

        return True


class MetaLearningEngine:
    """
    Unified meta-learning engine.

    Coordinates all learning components.
    """

    def __init__(self):
        self.pattern_extractor = PatternExtractor()
        self.transfer_learning = TransferLearning()
        self.best_practices = BestPracticesExtractor()
        self.mistake_avoidance = MistakeAvoidance()

        self.learned_knowledge: Dict[str, Any] = {}

        logger.info("MetaLearningEngine initialized")

    async def learn(
        self,
        strategies: List[Dict[str, Any]],
        market_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Learn from strategy outcomes.

        Args:
            strategies: Strategy results
            market_context: Market context

        Returns:
            Learned knowledge
        """

        # Extract patterns
        patterns = await self.pattern_extractor.extract_patterns(strategies, market_context)

        # Extract best practices
        outcomes = [
            {
                'approach': s.get('type', 'unknown'),
                'success': s.get('return', 0) > 0,
                'context': market_context,
                'category': s.get('category', 'general'),
                'implementation': s.get('implementation', '')
            }
            for s in strategies
        ]
        practices = await self.best_practices.extract_best_practices(outcomes)

        # Store learned knowledge
        self.learned_knowledge = {
            'patterns': patterns,
            'best_practices': practices,
            'market_context': market_context,
            'learned_at': datetime.now().isoformat()
        }

        # Update transfer learning knowledge base
        regime = market_context.get('regime', 'UNKNOWN')
        if regime not in self.transfer_learning.knowledge_base:
            self.transfer_learning.knowledge_base[regime] = []
        self.transfer_learning.knowledge_base[regime].extend(patterns)

        return self.learned_knowledge

    async def get_recommendations(
        self,
        current_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get recommendations based on learned knowledge.

        Args:
            current_context: Current market context

        Returns:
            Recommendations
        """

        # Find transferable knowledge
        previous_contexts = self._get_previous_contexts()
        recommendations = []

        for prev_context in previous_contexts:
            transferable = await self.transfer_learning.find_transferable_knowledge(
                prev_context, current_context
            )

            if transferable:
                transfer_recs = await self.transfer_learning.transfer_knowledge(
                    transferable, current_context
                )
                recommendations.append(transfer_recs)

        # Compile best practices
        best_practice_recs = []
        for practice in self.best_practices.best_practices:
            # Check if applicable
            if self._is_practice_applicable(practice, current_context):
                best_practice_recs.append({
                    'title': practice.title,
                    'description': practice.description,
                    'confidence': practice.confidence
                })

        return {
            'transfer_recommendations': recommendations,
            'best_practices': best_practice_recs,
            'applicable_patterns': self.learned_knowledge.get('patterns', [])
        }

    async def check_proposed_action(
        self,
        action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Check if proposed action should be avoided.

        Args:
            action: Proposed action

        Returns:
            Avoidance check results
        """

        avoidance_rules = await self.mistake_avoidance.check_avoidance(action)

        return {
            'safe': len(avoidance_rules) == 0,
            'avoidance_rules': avoidance_rules,
            'recommendation': 'Proceed' if not avoidance_rules else 'AVOID - Matches known failure pattern'
        }

    def _get_previous_contexts(self) -> List[Dict[str, Any]]:
        """Get previous market contexts."""
        # Would load from storage
        return [
            {'regime': 'bull', 'volatility': 0.2},
            {'regime': 'bear', 'volatility': 0.4},
            {'regime': 'sideways', 'volatility': 0.15}
        ]

    def _is_practice_applicable(
        self,
        practice: BestPractice,
        context: Dict[str, Any]
    ) -> bool:
        """Check if best practice is applicable."""

        # Check if current context matches applicable situations
        regime = context.get('regime')
        if regime:
            if f"{regime}_regime" in practice.counter_indications:
                return False

        return True

    def save_knowledge(self, filepath: str):
        """Save learned knowledge to file."""
        with open(filepath, 'wb') as f:
            pickle.dump({
                'patterns': self.pattern_extractor.patterns,
                'best_practices': self.best_practices.best_practices,
                'avoidance_rules': self.mistake_avoidance.avoidance_rules,
                'knowledge_base': self.transfer_learning.knowledge_base
            }, f)

        logger.info(f"Saved knowledge to {filepath}")

    def load_knowledge(self, filepath: str):
        """Load learned knowledge from file."""
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

                self.pattern_extractor.patterns = data.get('patterns', [])
                self.best_practices.best_practices = data.get('best_practices', [])
                self.mistake_avoidance.avoidance_rules = data.get('avoidance_rules', [])
                self.transfer_learning.knowledge_base = data.get('knowledge_base', {})

            logger.info(f"Loaded knowledge from {filepath}")
        except FileNotFoundError:
            logger.warning(f"Knowledge file not found: {filepath}")


# Singleton instance
_meta_learning_engine = None


def get_meta_learning_engine() -> MetaLearningEngine:
    """Get or create meta-learning engine instance."""
    global _meta_learning_engine
    if _meta_learning_engine is None:
        _meta_learning_engine = MetaLearningEngine()
    return _meta_learning_engine
