#!/usr/bin/env python3
"""
SLATE Autonomous Research Module

Phase 5: Autonomous Research Agenda (Weeks 17-20)

Components:
- Research Prioritization: Intelligent research opportunity scoring
- Hypothesis Engine: Automated hypothesis generation and testing
- Continuous Monitoring: Real-time opportunity scanning

This phase enables SLATE to self-direct research instead of waiting for commands.

Author: SLATE Evolution
Date: 2026-04-30
Status: OPERATIONAL
"""

from .research_prioritization import (
    ResearchPriority,
    ResearchOpportunity,
    ResearchPrioritizer,
    get_research_prioritizer
)

from .hypothesis_engine import (
    HypothesisStatus,
    Hypothesis,
    HypothesisGenerator,
    BayesianHypothesisTester,
    SequentialAnalyzer,
    HypothesisEngine,
    get_hypothesis_engine
)

from .continuous_monitoring import (
    AlertSeverity,
    OpportunityType,
    Alert,
    ContinuousMonitor,
    get_continuous_monitor
)

__all__ = [
    'ResearchPriority',
    'ResearchOpportunity',
    'ResearchPrioritizer',
    'get_research_prioritizer',

    'HypothesisStatus',
    'Hypothesis',
    'HypothesisGenerator',
    'BayesianHypothesisTester',
    'SequentialAnalyzer',
    'HypothesisEngine',
    'get_hypothesis_engine',

    'AlertSeverity',
    'OpportunityType',
    'Alert',
    'ContinuousMonitor',
    'get_continuous_monitor'
]
