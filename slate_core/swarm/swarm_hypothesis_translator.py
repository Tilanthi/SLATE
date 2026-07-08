#!/usr/bin/env python3
"""
Swarm Hypothesis Translator Implementation

Converts swarm discoveries to StrategyHypothesis objects for validation.
This bridges the collective intelligence of the swarm with the hypothesis-driven discovery system.
"""

import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from slate_core.discovery.closed_loop_discovery import StrategyHypothesis, HypothesisType

logger = logging.getLogger(__name__)


class SwarmToHypothesisTranslator:
    """
    Converts swarm discoveries to StrategyHypothesis objects.

    This class is the bridge between the swarm intelligence system and the
    hypothesis-driven discovery system. It takes collective intelligence results
    from 63 specialized agents and translates them into formal hypotheses that
    can be validated through the existing backtest and validation infrastructure.

    Usage:
        translator = SwarmToHypothesisTranslator()
        hypotheses = translator.translate_collective_intelligence(swarm_results)
    """

    def __init__(self):
        """Initialize SwarmToHypothesisTranslator."""
        self.hypotheses_translated = 0
        self.translation_history = []

        # Agent type to hypothesis type mapping
        self.AGENT_TO_HYPOTHESIS_MAPPING = {
            'regime_detector': HypothesisType.REGIME_SWITCHING,
            'pattern_discoverer': HypothesisType.MEAN_REVERSION,
            'parameter_explorer': HypothesisType.MOMENTUM,
            'cross_timeframe_analyst': HypothesisType.ARBITRAGE,
            'experimental_strategist': HypothesisType.BREAKOUT,
        }

        logger.info("SwarmToHypothesisTranslator initialized")

    def translate_collective_intelligence(self, swarm_results: Dict[str, Any]) -> List[StrategyHypothesis]:
        """
        Convert swarm collective intelligence to hypotheses.

        Args:
            swarm_results: Dictionary containing collective intelligence from swarm
                Expected structure:
                {
                    'collective_intelligence': {
                        'successful_patterns': [...],
                        'agent_contributions': {...}
                    },
                    'pheromone_signals': [...],
                    'regime_intelligence': {...}
                }

        Returns:
            List of StrategyHypothesis objects created from swarm discoveries
        """
        hypotheses = []

        try:
            # Extract collective intelligence
            collective_intelligence = swarm_results.get('collective_intelligence', {})

            # Process successful patterns
            successful_patterns = collective_intelligence.get('successful_patterns', [])

            for pattern in successful_patterns:
                try:
                    hypothesis = self._convert_pattern_to_hypothesis(pattern)
                    if hypothesis:
                        hypotheses.append(hypothesis)
                        self.hypotheses_translated += 1

                except Exception as e:
                    logger.warning(f"Error converting pattern to hypothesis: {e}")

            # Process agent contributions if available
            agent_contributions = collective_intelligence.get('agent_contributions', {})

            for agent_type, contributions in agent_contributions.items():
                if isinstance(contributions, list):
                    for contribution in contributions:
                        try:
                            hypothesis = self._convert_contribution_to_hypothesis(contribution, agent_type)
                            if hypothesis:
                                hypotheses.append(hypothesis)
                                self.hypotheses_translated += 1

                        except Exception as e:
                            logger.warning(f"Error converting contribution from {agent_type}: {e}")

            logger.info(f"Translated {len(hypotheses)} hypotheses from swarm results")

            return hypotheses

        except Exception as e:
            logger.error(f"Error translating collective intelligence: {e}")
            return []

    def _convert_pattern_to_hypothesis(self, pattern: Dict[str, Any]) -> Optional[StrategyHypothesis]:
        """Convert individual pattern to hypothesis."""
        try:
            # Extract pattern information
            agent_type = pattern.get('agent_type', 'pattern_discoverer')
            strategy_name = pattern.get('strategy_name', 'unknown')
            performance = pattern.get('performance', {})
            confidence = pattern.get('confidence', 0.5)

            # Map agent type to hypothesis type
            hypothesis_type = self._map_agent_type_to_hypothesis_type(agent_type)

            # Extract strategy design
            strategy_design = self._extract_strategy_design_from_pattern(pattern)

            # Create hypothesis
            hypothesis = StrategyHypothesis(
                name=f"swarm_{agent_type}_{strategy_name}_{uuid.uuid4().hex[:8]}",
                hypothesis_type=hypothesis_type,
                premise=self._generate_premise_from_pattern(pattern, agent_type),
                prediction=self._generate_prediction_from_pattern(pattern, performance),
                market_conditions=self._extract_market_conditions(pattern),
                strategy_design=strategy_design,
                test_design={
                    'test_period': '12_months',
                    'transaction_costs': 'realistic_perpetual',
                    'validation_methods': ['bootstrap', 'regime_stress', 'cost_sensitivity']
                },
                expected_outcomes=self._generate_expected_outcomes(pattern, performance),
                regime_applicability=self._extract_regime_applicability(pattern),
                confidence_level=confidence
            )

            # Track translation
            self.translation_history.append({
                'timestamp': datetime.now(),
                'agent_type': agent_type,
                'hypothesis_name': hypothesis.name,
                'hypothesis_type': hypothesis_type.value,
                'confidence': confidence
            })

            return hypothesis

        except Exception as e:
            logger.warning(f"Error converting pattern to hypothesis: {e}")
            return None

    def _convert_contribution_to_hypothesis(self, contribution: Dict[str, Any],
                                          agent_type: str) -> Optional[StrategyHypothesis]:
        """Convert agent contribution to hypothesis."""
        try:
            # Extract contribution information
            strategy_params = contribution.get('strategy_parameters', {})
            performance_score = contribution.get('performance_score', 0.5)

            # Map agent type to hypothesis type
            hypothesis_type = self._map_agent_type_to_hypothesis_type(agent_type)

            # Create hypothesis from contribution
            hypothesis = StrategyHypothesis(
                name=f"swarm_{agent_type}_contribution_{uuid.uuid4().hex[:8]}",
                hypothesis_type=hypothesis_type,
                premise=f"Collective intelligence from {agent_type} agents identified profitable opportunity",
                prediction=f"Strategy will achieve {performance_score:.1%} win rate based on swarm analysis",
                market_conditions=contribution.get('market_conditions', {}),
                strategy_design=strategy_params,
                test_design={
                    'test_period': '12_months',
                    'transaction_costs': 'realistic_perpetual',
                    'validation_methods': ['bootstrap', 'walk_forward']
                },
                expected_outcomes={
                    'min_win_rate': max(0.4, performance_score - 0.1),
                    'min_sharpe': 0.3,
                    'max_drawdown': 0.15
                },
                regime_applicability=contribution.get('regime_applicability', ['ALL']),
                confidence_level=performance_score
            )

            return hypothesis

        except Exception as e:
            logger.warning(f"Error converting contribution to hypothesis: {e}")
            return None

    def _map_agent_type_to_hypothesis_type(self, agent_type: str) -> HypothesisType:
        """Map agent type to hypothesis type."""
        return self.AGENT_TO_HYPOTHESIS_MAPPING.get(agent_type, HypothesisType.MOMENTUM)

    def _generate_premise_from_pattern(self, pattern: Dict[str, Any], agent_type: str) -> str:
        """Generate premise from pattern."""
        strategy_desc = pattern.get('strategy_description', 'Collective intelligence discovery')
        market_condition = pattern.get('market_condition', 'current market')

        return f"Swarm {agent_type} agents identified {strategy_desc} opportunity in {market_condition} conditions"

    def _generate_prediction_from_pattern(self, pattern: Dict[str, Any],
                                        performance: Dict[str, Any]) -> str:
        """Generate prediction from pattern and performance."""
        expected_return = performance.get('expected_return', 0.05)
        expected_win_rate = performance.get('expected_win_rate', 0.50)

        return f"Strategy will achieve {expected_win_rate:.1%} win rate with {expected_return:.1%} expected return"

    def _extract_strategy_design_from_pattern(self, pattern: Dict[str, Any]) -> Dict[str, Any]:
        """Extract strategy design from pattern."""
        return pattern.get('strategy_parameters', pattern.get('strategy_design', {}))

    def _extract_market_conditions(self, pattern: Dict[str, Any]) -> Dict[str, Any]:
        """Extract market conditions from pattern."""
        return pattern.get('market_conditions', {
            'regime': pattern.get('detected_regime', 'UNKNOWN'),
            'volatility': pattern.get('volatility_regime', 'NORMAL'),
            'trend': pattern.get('trend_direction', 'UNKNOWN')
        })

    def _generate_expected_outcomes(self, pattern: Dict[str, Any],
                                   performance: Dict[str, Any]) -> Dict[str, Any]:
        """Generate expected outcomes from pattern performance."""
        return {
            'min_trades': pattern.get('expected_trades', 15),
            'min_win_rate': performance.get('expected_win_rate', 0.50),
            'min_sharpe': performance.get('expected_sharpe', 0.5),
            'max_drawdown': performance.get('max_drawdown', 0.15),
            'expected_return': f"{performance.get('expected_return', 0.05):.1%}"
        }

    def _extract_regime_applicability(self, pattern: Dict[str, Any]) -> List[str]:
        """Extract regime applicability from pattern."""
        detected_regime = pattern.get('detected_regime', 'UNKNOWN')

        if detected_regime == 'SIDEWAYS':
            return ['SIDEWAYS', 'MILD_BULL', 'MILD_BEAR']
        elif detected_regime == 'TRENDING_UP':
            return ['TRENDING_UP', 'BULL']
        elif detected_regime == 'TRENDING_DOWN':
            return ['TRENDING_DOWN', 'BEAR']
        else:
            return ['ALL']

    def get_translation_summary(self) -> Dict[str, Any]:
        """Get summary of translation activity."""
        return {
            'hypotheses_translated': self.hypotheses_translated,
            'agent_types_mapped': list(self.AGENT_TO_HYPOTHESIS_MAPPING.keys()),
            'recent_translations': self.translation_history[-10:] if self.translation_history else []
        }

    def reset_statistics(self):
        """Reset translation statistics."""
        self.hypotheses_translated = 0
        self.translation_history = []


def get_swarm_hypothesis_translator() -> SwarmToHypothesisTranslator:
    """Get global swarm hypothesis translator instance."""
    # For now, create new instance each time
    # Could be converted to singleton pattern if needed
    return SwarmToHypothesisTranslator()
