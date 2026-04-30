#!/usr/bin/env python3
"""
SLATE Query Understanding System

Phase 7: Natural Language Interface (Weeks 25-28)

Implements natural language query understanding:
- Intent classification
- Entity extraction
- Context interpretation
- Market terminology parsing

Critical for conversational interaction with SLATE.

Author: SLATE Evolution
Date: 2026-04-30
Priority: MEDIUM - Natural language interface
"""

import asyncio
import logging
import re
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import json

logger = logging.getLogger(__name__)


class Intent(Enum):
    """User query intents."""
    QUERY_STATUS = "query_status"  # Check system status
    QUERY_PERFORMANCE = "query_performance"  # Ask about performance
    QUERY_STRATEGY = "query_strategy"  # Ask about specific strategy
    QUERY_MARKET = "query_market"  # Ask about market conditions
    QUERY_RISK = "query_risk"  # Ask about risk metrics
    CREATE_STRATEGY = "create_strategy"  # Create new strategy
    MODIFY_STRATEGY = "modify_strategy"  # Modify existing strategy
    ACTIVATE_STRATEGY = "activate_strategy"  # Activate strategy
    DEACTIVATE_STRATEGY = "deactivate_strategy"  # Deactivate strategy
    DELETE_STRATEGY = "delete_strategy"  # Delete strategy
    RUN_BACKTEST = "run_backtest"  # Run backtest
    RUN_DISCOVERY = "run_discovery"  # Run strategy discovery
    OPTIMIZE_PORTFOLIO = "optimize_portfolio"  # Optimize portfolio
    ADJUST_RISK = "adjust_risk"  # Adjust risk parameters
    EXPLAIN_METRIC = "explain_metric"  # Explain a metric
    GENERATE_REPORT = "generate_report"  # Generate report
    UNKNOWN = "unknown"  # Unknown intent


@dataclass
class QueryEntity:
    """Extracted entity from query."""
    entity_type: str  # e.g., "strategy", "symbol", "metric", "timeframe"
    value: str
    confidence: float
    span: Tuple[int, int]  # Character span in original query


@dataclass
class QueryContext:
    """Context for query interpretation."""
    previous_queries: List[str]
    active_strategies: List[str]
    current_regime: str
    market_state: str
    user_preferences: Dict[str, Any]


@dataclass
class ParsedQuery:
    """Parsed query with intent and entities."""
    original_query: str
    intent: Intent
    confidence: float
    entities: List[QueryEntity]
    context: QueryContext

    # Normalized parameters
    strategy_name: Optional[str] = None
    symbol: Optional[str] = None
    metric: Optional[str] = None
    timeframe: Optional[str] = None
    threshold: Optional[float] = None
    parameters: Dict[str, Any] = field(default_factory=dict)


class IntentClassifier:
    """
    Classify user query intent.

    Uses pattern matching and keyword detection.
    """

    def __init__(self):
        self.intent_patterns = self._load_intent_patterns()
        logger.info("IntentClassifier initialized")

    def _load_intent_patterns(self) -> Dict[Intent, List[str]]:
        """Load intent classification patterns."""

        return {
            Intent.QUERY_STATUS: [
                r"how (is|are) (the )?system",
                r"what('s| is) (the )?status",
                r"are you (running|operational|working)",
                r"system health",
                r"current state"
            ],
            Intent.QUERY_PERFORMANCE: [
                r"how (did|do|has) (it )?perform",
                r"what('s| is) (the )?(performance|return|pnl|profit)",
                r"show (me )?performance",
                r"how much (money|profit|return)",
                r"sharpe ratio",
                r"win rate",
                r"total return"
            ],
            Intent.QUERY_STRATEGY: [
                r"tell me about (the )?strategy",
                r"what('s| is) (the )?.* strategy",
                r"explain (the )?.* strategy",
                r"describe (the )?.* strategy",
                r"strategy details"
            ],
            Intent.QUERY_MARKET: [
                r"what('s| is) (the )?market",
                r"market (condition|state|regime)",
                r"how('s| is) (the )?market",
                r"market volatility",
                r"trend"
            ],
            Intent.QUERY_RISK: [
                r"what('s| is) (the )?risk",
                r"risk (level|metric|exposure)",
                r"var|cvar|drawdown",
                r"position (size|risk)",
                r"portfolio risk"
            ],
            Intent.CREATE_STRATEGY: [
                r"create (a )?(new )?strategy",
                r"build (a )?strategy",
                r"develop (a )?strategy",
                r"make (a )?strategy",
                r"new strategy"
            ],
            Intent.MODIFY_STRATEGY: [
                r"change (the )?strategy",
                r"modify (the )?strategy",
                r"update (the )?strategy",
                r"adjust (the )?strategy",
                r"edit (the )?strategy"
            ],
            Intent.ACTIVATE_STRATEGY: [
                r"activate (the )?strategy",
                r"enable (the )?strategy",
                r"start (the )?strategy",
                r"turn on (the )?strategy"
            ],
            Intent.DEACTIVATE_STRATEGY: [
                r"deactivate (the )?strategy",
                r"disable (the )?strategy",
                r"stop (the )?strategy",
                r"turn off (the )?strategy"
            ],
            Intent.DELETE_STRATEGY: [
                r"delete (the )?strategy",
                r"remove (the )?strategy",
                r"get rid of (the )?strategy"
            ],
            Intent.RUN_BACKTEST: [
                r"run (a )?backtest",
                r"backtest (the )?strategy",
                r"test (the )?strategy",
                r"simulate"
            ],
            Intent.RUN_DISCOVERY: [
                r"run (a )?discovery",
                r"start (the )?discovery",
                r"find (new )?strategies",
                r"discover strategies",
                r"search for strategies"
            ],
            Intent.OPTIMIZE_PORTFOLIO: [
                r"optimize (the )?portfolio",
                r"rebalance",
                r"portfolio (optimization|allocation)"
            ],
            Intent.ADJUST_RISK: [
                r"change (the )?risk",
                r"adjust (the )?risk",
                r"set risk (level|parameter)",
                r"risk management"
            ],
            Intent.EXPLAIN_METRIC: [
                r"what (does|is) .+ mean",
                r"explain .+",
                r"define .+",
                r"how (do|does) .+ work"
            ],
            Intent.GENERATE_REPORT: [
                r"generate (a )?report",
                r"create (a )?report",
                r"write (a )?report",
                r"report"
            ]
        }

    def classify(self, query: str) -> Tuple[Intent, float]:
        """
        Classify query intent.

        Args:
            query: User query

        Returns:
            (intent, confidence)
        """

        query_lower = query.lower()

        best_intent = Intent.UNKNOWN
        best_score = 0.0

        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    # Calculate confidence based on match quality
                    match = re.search(pattern, query_lower)
                    score = len(match.group()) / len(query_lower) if match else 0.5
                    score = min(1.0, score + 0.3)  # Boost for pattern match

                    if score > best_score:
                        best_intent = intent
                        best_score = score

        return best_intent, best_score


class EntityExtractor:
    """
    Extract entities from user queries.

    Identifies strategies, symbols, metrics, timeframes, etc.
    """

    def __init__(self):
        self.patterns = self._load_entity_patterns()
        logger.info("EntityExtractor initialized")

    def _load_entity_patterns(self) -> Dict[str, List[str]]:
        """Load entity extraction patterns."""

        return {
            'symbol': [
                r'\b[A-Z]{2,10}\b',  # Ticker symbols
                r'\bbitcoin\b',
                r'\bethereum\b',
                r'\bbtc\b',
                r'\beth\b'
            ],
            'strategy': [
                r'\b(momentum|mean.reversion|trend.following|arbitrage)\b',
                r'\bstrategy \d+\b',
                r'\b[a-z_]+_strategy\b'
            ],
            'metric': [
                r'\b(sharpe|sortino|calmar|var|cvar|drawdown)\b',
                r'\b(return|profit|pnl|win.rate)\b',
                r'\b(volatility|beta|alpha)\b'
            ],
            'timeframe': [
                r'\b\d+\s*(hour|day|week|month|year)s?\b',
                r'\b(1h|4h|1d|1w|1M)\b',
                r'\b(daily|weekly|monthly)\b'
            ],
            'percentage': [
                r'\b\d+(\.\d+)?%\b',
                r'\b\d+(\.\d+)?\s*percent\b'
            ],
            'number': [
                r'\b\d+(\.\d+)?\b'
            ]
        }

    def extract(self, query: str) -> List[QueryEntity]:
        """
        Extract entities from query.

        Args:
            query: User query

        Returns:
            List of extracted entities
        """

        entities = []

        for entity_type, patterns in self.patterns.items():
            for pattern in patterns:
                for match in re.finditer(pattern, query, re.IGNORECASE):
                    entity = QueryEntity(
                        entity_type=entity_type,
                        value=match.group(),
                        confidence=0.8,  # Base confidence
                        span=(match.start(), match.end())
                    )
                    entities.append(entity)

        return entities


class ContextInterpreter:
    """
    Interpret query context.

    Uses conversation history and system state to resolve ambiguities.
    """

    def __init__(self):
        self.conversation_history: List[str] = []
        self.context_window = 5
        logger.info("ContextInterpreter initialized")

    def update_context(self, query: str):
        """Update conversation context."""
        self.conversation_history.append(query)
        if len(self.conversation_history) > self.context_window:
            self.conversation_history.pop(0)

    def resolve_references(
        self,
        query: str,
        context: QueryContext
    ) -> Dict[str, Any]:
        """
        Resolve references in query.

        Args:
            query: User query
            context: Query context

        Returns:
            Resolved parameters
        """

        resolved = {}

        # Resolve "it", "that", "the strategy"
        if re.search(r'\b(it|that|this)\b', query, re.IGNORECASE):
            if context.active_strategies:
                resolved['strategy_name'] = context.active_strategies[0]
            if self.conversation_history:
                # Refer to last discussed entity
                resolved['reference'] = self.conversation_history[-1]

        # Resolve time references
        now = datetime.now()
        if 'today' in query.lower():
            resolved['date'] = now.date()
        elif 'yesterday' in query.lower():
            resolved['date'] = (now - timedelta(days=1)).date()
        elif 'this week' in query.lower():
            resolved['start_date'] = now - timedelta(days=now.weekday())
            resolved['end_date'] = now

        # Resolve market context
        if 'current market' in query.lower():
            resolved['regime'] = context.current_regime
            resolved['market_state'] = context.market_state

        return resolved


class QueryUnderstandingEngine:
    """
    Unified query understanding engine.

    Combines intent classification, entity extraction, and context.
    """

    def __init__(self):
        self.intent_classifier = IntentClassifier()
        self.entity_extractor = EntityExtractor()
        self.context_interpreter = ContextInterpreter()

        logger.info("QueryUnderstandingEngine initialized")

    async def parse_query(
        self,
        query: str,
        context: QueryContext
    ) -> ParsedQuery:
        """
        Parse user query.

        Args:
            query: User query
            context: Query context

        Returns:
            Parsed query
        """

        # Classify intent
        intent, confidence = self.intent_classifier.classify(query)

        # Extract entities
        entities = self.entity_extractor.extract(query)

        # Interpret context
        resolved_refs = self.context_interpreter.resolve_references(query, context)

        # Update conversation history
        self.context_interpreter.update_context(query)

        # Normalize entities
        normalized = self._normalize_entities(entities, resolved_refs)

        # Create parsed query
        parsed = ParsedQuery(
            original_query=query,
            intent=intent,
            confidence=confidence,
            entities=entities,
            context=context,
            **normalized
        )

        return parsed

    def _normalize_entities(
        self,
        entities: List[QueryEntity],
        resolved_refs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Normalize extracted entities."""

        normalized = {}

        for entity in entities:
            if entity.entity_type == 'symbol':
                normalized['symbol'] = entity.value.upper()
            elif entity.entity_type == 'strategy':
                normalized['strategy_name'] = entity.value.lower()
            elif entity.entity_type == 'metric':
                normalized['metric'] = entity.value.lower()
            elif entity.entity_type == 'timeframe':
                normalized['timeframe'] = entity.value.lower()
            elif entity.entity_type == 'percentage':
                # Extract numeric value
                match = re.search(r'([\d.]+)', entity.value)
                if match:
                    normalized['threshold'] = float(match.group()) / 100
            elif entity.entity_type == 'number':
                normalized['parameters'] = normalized.get('parameters', {})
                normalized['parameters']['value'] = float(entity.value)

        # Add resolved references
        normalized.update(resolved_refs)

        return normalized

    def generate_understanding_report(
        self,
        parsed: ParsedQuery
    ) -> str:
        """Generate query understanding report."""

        report = f"""
{'='*60}
QUERY UNDERSTANDING REPORT
{'='*60}

ORIGINAL QUERY: "{parsed.original_query}"

INTENT: {parsed.intent.value}
CONFIDENCE: {parsed.confidence:.1%}

ENTITIES:
"""
        for entity in parsed.entities:
            report += f"  {entity.entity_type}: {entity.value} (confidence: {entity.confidence:.1%})\n"

        report += f"""
NORMALIZED PARAMETERS:
"""
        if parsed.strategy_name:
            report += f"  Strategy: {parsed.strategy_name}\n"
        if parsed.symbol:
            report += f"  Symbol: {parsed.symbol}\n"
        if parsed.metric:
            report += f"  Metric: {parsed.metric}\n"
        if parsed.timeframe:
            report += f"  Timeframe: {parsed.timeframe}\n"
        if parsed.threshold is not None:
            report += f"  Threshold: {parsed.threshold:.2%}\n"
        if parsed.parameters:
            report += f"  Parameters: {parsed.parameters}\n"

        return report


# Singleton instance
_query_understanding_engine = None


def get_query_understanding_engine() -> QueryUnderstandingEngine:
    """Get or create query understanding engine instance."""
    global _query_understanding_engine
    if _query_understanding_engine is None:
        _query_understanding_engine = QueryUnderstandingEngine()
    return _query_understanding_engine
