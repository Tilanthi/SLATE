#!/usr/bin/env python3
"""
SLATE Research Prioritization System

Phase 5: Autonomous Research Agenda

Implements intelligent research prioritization:
- Expected information gain calculation
- Resource optimization
- Time sensitivity scoring
- Market applicability assessment

Critical for autonomous research direction.

Author: SLATE Evolution
Date: 2026-04-30
Priority: HIGH - Enables self-directed research
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
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class ResearchPriority(Enum):
    """Research priority levels."""
    CRITICAL = "critical"  # Execute immediately
    HIGH = "high"  # Execute within hours
    MEDIUM = "medium"  # Execute within days
    LOW = "low"  # Execute when resources available
    DEFERRED = "deferred"  # Not worth pursuing


@dataclass
class ResearchOpportunity:
    """A potential research opportunity."""
    id: str
    title: str
    description: str
    hypothesis: str

    # Priority components
    expected_information_gain: float  # 0-1
    resource_requirement: float  0-1 (1 = most expensive)
    time_sensitivity: float  # 0-1 (1 = most urgent)
    market_applicability: float  # 0-1 (1 = broadly applicable)

    # Meta information
    estimated_hours: float
    required_compute: float  # 0-1
    data_requirements: List[str]
    expected_roi: float  # Expected return on investment

    # Dependencies
    dependencies: List[str]  # IDs of required research
    blocked_by: List[str]  # IDs of blocking research

    # Status
    priority: ResearchPriority = ResearchPriority.MEDIUM
    confidence: float = 0.5  # Confidence in assessment


class ExpectedInformationGain:
    """
    Calculate expected information gain (EIG).

    EIG measures how much we expect to learn from research.
    Higher EIG = more valuable research.
    """

    def __init__(self):
        logger.info("ExpectedInformationGain initialized")

    def calculate_eig(
        self,
        prior_beliefs: Dict[str, float],
        potential_outcomes: List[Dict[str, float]],
        outcome_probabilities: List[float]
    ) -> float:
        """
        Calculate expected information gain using entropy reduction.

        EIG = H(prior) - E[H(posterior)]

        Args:
            prior_beliefs: Current beliefs (probabilities)
            potential_outcomes: List of possible posterior beliefs
            outcome_probabilities: Probability of each outcome

        Returns:
            Expected information gain (0-1, normalized)
        """

        # Calculate prior entropy
        prior_entropy = self._entropy(list(prior_beliefs.values()))

        # Calculate expected posterior entropy
        expected_posterior_entropy = 0.0
        for outcome, prob in zip(potential_outcomes, outcome_probabilities):
            posterior_entropy = self._entropy(list(outcome.values()))
            expected_posterior_entropy += prob * posterior_entropy

        # Information gain
        eig = prior_entropy - expected_posterior_entropy

        # Normalize by maximum possible entropy
        max_entropy = np.log(len(prior_beliefs))
        normalized_eig = eig / max_entropy if max_entropy > 0 else 0.0

        return max(0.0, min(1.0, normalized_eig))

    def _entropy(self, probabilities: List[float]) -> float:
        """Calculate Shannon entropy."""
        probabilities = np.array(probabilities)
        probabilities = probabilities[probabilities > 0]  # Remove zeros
        return -np.sum(probabilities * np.log(probabilities))

    def estimate_research_eig(
        self,
        research_type: str,
        current_uncertainty: float,
        sample_size: int,
        effect_size: Optional[float] = None
    ) -> float:
        """
        Estimate EIG for a research task.

        Args:
            research_type: Type of research
            current_uncertainty: Current uncertainty (0-1)
            sample_size: Available sample size
            effect_size: Expected effect size (if known)

        Returns:
            Estimated EIG
        """

        # Base EIG from uncertainty
        base_eig = current_uncertainty

        # Adjust by sample size (diminishing returns)
        sample_bonus = np.log(sample_size + 1) / np.log(10000 + 1)

        # Adjust by effect size (larger effects easier to detect)
        if effect_size is not None:
            detectability = min(1.0, abs(effect_size) * 2)
            effect_bonus = detectability * 0.3
        else:
            effect_bonus = 0.0

        # Research type modifiers
        type_bonus = {
            'regime_detection': 0.2,
            'correlation_analysis': 0.15,
            'strategy_discovery': 0.25,
            'parameter_optimization': 0.1,
            'backtest_validation': 0.05
        }.get(research_type, 0.0)

        eig = base_eig * 0.5 + sample_bonus * 0.2 + effect_bonus + type_bonus

        return min(1.0, max(0.0, eig))


class ResourceOptimizer:
    """
    Optimize resource allocation for research tasks.

    Balances:
    - Compute resources
    - Time budget
    - Researcher attention
    - Opportunity cost
    """

    def __init__(self, total_compute_hours: float = 168.0):  # 1 week
        self.total_compute_hours = total_compute_hours
        self.allocated_hours = 0.0

        logger.info(f"ResourceOptimizer initialized with {total_compute_hours} hours")

    def calculate_opportunity_cost(
        self,
        task_hours: float,
        competing_tasks: List[ResearchOpportunity]
    ) -> float:
        """
        Calculate opportunity cost of pursuing a task.

        Args:
            task_hours: Hours required for task
            competing_tasks: Alternative tasks

        Returns:
            Opportunity cost (0-1, 1 = high cost)
        """

        if not competing_tasks:
            return 0.0

        # Calculate value of competing tasks per hour
        competing_value = 0.0
        for task in competing_tasks:
            value_per_hour = task.expected_roi / (task.estimated_hours + 1e-10)
            competing_value += value_per_hour

        # Opportunity cost = value of alternatives * time spent
        opportunity_cost = competing_value * task_hours

        # Normalize
        max_cost = 100.0  # Arbitrary maximum
        return min(1.0, opportunity_cost / max_cost)

    def optimize_allocation(
        self,
        opportunities: List[ResearchOpportunity],
        time_budget: float
    ) -> List[Tuple[str, float]]:
        """
        Optimize resource allocation across research opportunities.

        Uses knapsack-style optimization.

        Args:
            opportunities: List of research opportunities
            time_budget: Available time budget

        Returns:
            List of (task_id, allocated_hours)
        """

        # Score each opportunity
        scored = []
        for opp in opportunities:
            # Value score
            value = (
                opp.expected_information_gain * 0.3 +
                opp.market_applicability * 0.3 +
                opp.time_sensitivity * 0.2 +
                (1 - opp.resource_requirement) * 0.2
            )

            # Value per hour
            value_per_hour = value / (opp.estimated_hours + 1e-10)

            scored.append((opp.id, opp, value, value_per_hour))

        # Sort by value per hour
        scored.sort(key=lambda x: x[3], reverse=True)

        # Greedy allocation
        allocation = []
        remaining_budget = time_budget

        for task_id, opp, value, vph in scored:
            if opp.estimated_hours <= remaining_budget:
                allocation.append((task_id, opp.estimated_hours))
                remaining_budget -= opp.estimated_hours
            elif remaining_budget > 0:
                # Partial allocation
                allocation.append((task_id, remaining_budget))
                remaining_budget = 0
                break

        return allocation


class TimeSensitivityScorer:
    """
    Score time sensitivity of research opportunities.

    Time-sensitive research should be prioritized.
    """

    def __init__(self):
        logger.info("TimeSensitivityScorer initialized")

    def calculate_time_sensitivity(
        self,
        opportunity: ResearchOpportunity,
        market_regime: str,
        volatility_level: float,
        time_to_expiry: Optional[float] = None
    ) -> float:
        """
        Calculate time sensitivity score.

        Args:
            opportunity: Research opportunity
            market_regime: Current market regime
            volatility_level: Current volatility level
            time_to_expiry: Time until opportunity expires (days)

        Returns:
            Time sensitivity (0-1)
        """

        score = 0.0

        # Regime-dependent sensitivity
        regime_sensitivity = {
            'bull': 0.3,
            'bear': 0.7,  # Bear markets more urgent
            'sideways': 0.2,
            'high_vol': 0.9,  # High volatility = urgent
            'low_vol': 0.1
        }
        score += regime_sensitivity.get(market_regime, 0.5) * 0.4

        # Volatility sensitivity
        vol_score = min(1.0, volatility_level * 2)
        score += vol_score * 0.3

        # Time to expiry (if applicable)
        if time_to_expiry is not None:
            expiry_score = max(0.0, 1.0 - time_to_expiry / 30)  # 30 day window
            score += expiry_score * 0.3

        return min(1.0, score)


class MarketApplicabilityAssessor:
    """
    Assess market applicability of research.

    Broadly applicable research is more valuable.
    """

    def __init__(self):
        logger.info("MarketApplicabilityAssessor initialized")

    def assess_applicability(
        self,
        opportunity: ResearchOpportunity,
        available_markets: List[str],
        market_regimes: Dict[str, str]
    ) -> float:
        """
        Assess how broadly applicable research is.

        Args:
            opportunity: Research opportunity
            available_markets: Available markets
            market_regimes: Current regime of each market

        Returns:
            Applicability score (0-1)
        """

        # Check market coverage
        required_markets = opportunity.data_requirements
        coverage = len(set(required_markets) & set(available_markets))
        coverage_score = coverage / len(required_markets) if required_markets else 1.0

        # Regime diversity
        regime_diversity = len(set(market_regimes.values())) / 5  # 5 typical regimes
        diversity_score = min(1.0, regime_diversity)

        # Type of research
        type_broadness = {
            'regime_detection': 1.0,  # Applies to all markets
            'correlation_analysis': 0.9,
            'strategy_discovery': 0.8,
            'parameter_optimization': 0.5,  # Strategy-specific
            'backtest_validation': 0.3  # Single strategy
        }.get(opportunity.id.split('_')[0], 0.5)

        # Combine
        applicability = (
            coverage_score * 0.3 +
            diversity_score * 0.2 +
            type_broadness * 0.5
        )

        return min(1.0, max(0.0, applicability))


class ResearchPrioritizer:
    """
    Unified research prioritization system.

    Combines all components to score and rank research opportunities.
    """

    def __init__(self):
        self.eig_calculator = ExpectedInformationGain()
        self.resource_optimizer = ResourceOptimizer()
        self.time_scorer = TimeSensitivityScorer()
        self.applicability_assessor = MarketApplicabilityAssessor()

        logger.info("ResearchPrioritizer initialized")

    async def prioritize_opportunities(
        self,
        opportunities: List[ResearchOpportunity],
        market_context: Dict[str, Any],
        time_budget: float = 168.0  # 1 week
    ) -> List[ResearchOpportunity]:
        """
        Prioritize research opportunities.

        Args:
            opportunities: List of research opportunities
            market_context: Current market context
            time_budget: Available time budget

        Returns:
            Prioritized list of opportunities
        """

        results = []

        for opp in opportunities:
            # Calculate scores
            eig = self.eig_calculator.estimate_research_eig(
                opp.id.split('_')[0],
                current_uncertainty=1.0 - opp.confidence,
                sample_size=1000,
                effect_size=None
            )
            opp.expected_information_gain = eig

            opp.time_sensitivity = self.time_scorer.calculate_time_sensitivity(
                opp,
                market_context.get('regime', 'sideways'),
                market_context.get('volatility', 0.5)
            )

            opp.market_applicability = self.applicability_assessor.assess_applicability(
                opp,
                market_context.get('markets', []),
                market_context.get('regimes', {})
            )

            # Calculate priority score
            priority_score = (
                opp.expected_information_gain * 0.3 +
                opp.market_applicability * 0.25 +
                opp.time_sensitivity * 0.25 +
                (1 - opp.resource_requirement) * 0.2
            )

            # Assign priority level
            if priority_score > 0.8:
                opp.priority = ResearchPriority.CRITICAL
            elif priority_score > 0.6:
                opp.priority = ResearchPriority.HIGH
            elif priority_score > 0.4:
                opp.priority = ResearchPriority.MEDIUM
            elif priority_score > 0.2:
                opp.priority = ResearchPriority.LOW
            else:
                opp.priority = ResearchPriority.DEFERRED

            results.append(opp)

        # Sort by priority score
        results.sort(key=lambda o: (
            o.priority.value == 'critical',
            o.priority.value == 'high',
            o.priority.value == 'medium',
            o.priority.value == 'low',
            o.priority.value == 'deferred'
        ), reverse=True)

        # Optimize resource allocation
        allocation = self.resource_optimizer.optimize_allocation(
            results, time_budget
        )

        logger.info(f"Prioritized {len(results)} opportunities")
        logger.info(f"Resource allocation: {len(allocation)} tasks funded")

        return results

    def generate_prioritization_report(
        self,
        opportunities: List[ResearchOpportunity]
    ) -> str:
        """Generate prioritization report."""

        report = f"""
{'='*60}
RESEARCH PRIORITIZATION REPORT
{'='*60}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

TOTAL OPPORTUNITIES: {len(opportunities)}

PRIORITY BREAKDOWN:
"""

        priority_counts = {}
        for opp in opportunities:
            priority_counts[opp.priority] = priority_counts.get(opp.priority, 0) + 1

        for priority, count in sorted(priority_counts.items(), key=lambda x: x[0].value):
            report += f"  {priority.value.upper()}: {count}\n"

        report += f"\nTOP OPPORTUNITIES:\n"

        for i, opp in enumerate(opportunities[:10], 1):
            report += f"""
{i}. {opp.title}
   ID: {opp.id}
   Priority: {opp.priority.value.upper()}
   EIG: {opp.expected_information_gain:.3f}
   Time Sensitivity: {opp.time_sensitivity:.3f}
   Applicability: {opp.market_applicability:.3f}
   Est. Hours: {opp.estimated_hours:.1f}
   Expected ROI: {opp.expected_roi:.2f}

   Hypothesis: {opp.hypothesis}
"""

        return report


# Singleton instance
_research_prioritizer = None


def get_research_prioritizer() -> ResearchPrioritizer:
    """Get or create research prioritizer instance."""
    global _research_prioritizer
    if _research_prioritizer is None:
        _research_prioritizer = ResearchPrioritizer()
    return _research_prioritizer
