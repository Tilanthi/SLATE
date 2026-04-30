#!/usr/bin/env python3
"""
SLATE Natural Language Interface Module

Phase 7: Natural Language Interface (Weeks 25-28)

Components:
- Query Understanding: Intent classification and entity extraction
- Explanatory Capabilities: Strategy explanations and insights
- Report Generation: Automated research and performance reports

This phase enables conversational interaction with SLATE.

Author: SLATE Evolution
Date: 2026-04-30
Status: OPERATIONAL
"""

from .query_understanding import (
    Intent,
    QueryEntity,
    QueryContext,
    ParsedQuery,
    QueryUnderstandingEngine,
    get_query_understanding_engine
)

from .explanatory import (
    ExplanationLevel,
    StrategyExplanation,
    ExplainerEngine,
    get_explainer_engine
)

from .report_generation import (
    ReportType,
    ReportSection,
    Report,
    ReportGenerator,
    get_report_generator
)

__all__ = [
    'Intent',
    'QueryEntity',
    'QueryContext',
    'ParsedQuery',
    'QueryUnderstandingEngine',
    'get_query_understanding_engine',

    'ExplanationLevel',
    'StrategyExplanation',
    'ExplainerEngine',
    'get_explainer_engine',

    'ReportType',
    'ReportSection',
    'Report',
    'ReportGenerator',
    'get_report_generator'
]
