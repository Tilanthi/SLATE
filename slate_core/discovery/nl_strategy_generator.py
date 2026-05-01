#!/usr/bin/env python3
"""
SLATE Natural Language Strategy Generator

Converts natural language descriptions into EdgeCandidate objects.
Supports multiple LLM providers (OpenAI, Anthropic, local models).

Example usage:
    "Test a mean reversion strategy when RSI is below 30"
    "Create a momentum strategy with EMA crossover"
    "Test a breakout strategy when volume is high"
"""

import logging
import re
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import os

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    MOCK = "mock"  # For testing without API calls


@dataclass
class NLStrategyRequest:
    """Natural language strategy generation request."""
    description: str
    context: Optional[str] = None
    complexity: str = "medium"  # simple, medium, complex
    risk_tolerance: str = "moderate"  # conservative, moderate, aggressive


@dataclass
class NLStrategyResult:
    """Result from natural language strategy generation."""
    success: bool
    edge_type: str
    description: str
    entry_conditions: Dict[str, Any]
    exit_conditions: Dict[str, Any]
    risk_params: Dict[str, Any]
    confidence: float
    expected_return: float
    expected_drawdown: float
    explanation: str
    raw_response: Optional[str] = None
    error: Optional[str] = None


class NLStrategyGenerator:
    """
    Converts natural language strategy descriptions into EdgeCandidates.

    Uses LLMs to understand strategy intent and convert to structured parameters.
    Falls back to rule-based parsing for simple patterns.
    """

    def __init__(self, provider: LLMProvider = LLMProvider.MOCK, api_key: Optional[str] = None):
        self.provider = provider
        self.api_key = api_key or os.getenv(f"{provider.value.upper()}_API_KEY")
        self._init_client()

    def _init_client(self):
        """Initialize LLM client based on provider."""
        if self.provider == LLMProvider.OPENAI:
            try:
                import openai
                self.client = openai.OpenAI(api_key=self.api_key)
                logger.info("OpenAI client initialized")
            except ImportError:
                logger.warning("OpenAI not installed, falling back to MOCK")
                self.provider = LLMProvider.MOCK
                self.client = None

        elif self.provider == LLMProvider.ANTHROPIC:
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key)
                logger.info("Anthropic client initialized")
            except ImportError:
                logger.warning("Anthropic not installed, falling back to MOCK")
                self.provider = LLMProvider.MOCK
                self.client = None

        elif self.provider == LLMProvider.OLLAMA:
            try:
                import requests
                self.client = requests
                self.ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
                logger.info(f"Ollama client initialized at {self.ollama_base}")
            except ImportError:
                logger.warning("Requests not installed for Ollama")
                self.client = None

        else:
            self.client = None
            logger.info("Using MOCK provider (rule-based parsing only)")

    def generate_strategy(self, request: NLStrategyRequest) -> NLStrategyResult:
        """
        Convert natural language description to EdgeCandidate structure.

        Args:
            request: Strategy description and parameters

        Returns:
            NLStrategyResult with structured strategy parameters
        """
        # First try rule-based parsing for common patterns
        rule_result = self._try_rule_based_parsing(request)
        if rule_result.success:
            logger.info(f"Strategy generated via rule-based parsing: {rule_result.edge_type}")
            return rule_result

        # Fall back to LLM if available
        if self.provider != LLMProvider.MOCK and self.client:
            try:
                return self._llm_generate_strategy(request)
            except Exception as e:
                logger.error(f"LLM generation failed: {e}")
                # Fall back to mock
                pass

        # Final fallback to mock generation
        return self._mock_generate_strategy(request)

    def _try_rule_based_parsing(self, request: NLStrategyRequest) -> NLStrategyResult:
        """
        Parse common strategy patterns using regex rules.

        Handles simple descriptions like:
        - "RSI below 30"
        - "EMA crossover"
        - "breakout when volume high"
        """
        desc = request.description.lower()

        # Mean reversion patterns
        if any(term in desc for term in ["mean reversion", "oversold", "overbought", "reversal"]):
            return self._parse_mean_reversion(desc)

        # Momentum patterns
        elif any(term in desc for term in ["momentum", "trend", "breakout", "crossover"]):
            return self._parse_momentum(desc)

        # Volatility patterns
        elif any(term in desc for term in ["volatility", "squeeze", "expansion", "atr"]):
            return self._parse_volatility(desc)

        # Time-based patterns
        elif any(term in desc for term in ["session", "open", "close", "time", "hour"]):
            return self._parse_time_pattern(desc)

        # Volume patterns
        elif any(term in desc for term in ["volume", "liquidity", "flow"]):
            return self._parse_volume_pattern(desc)

        # Pattern recognition
        elif any(term in desc for term in ["double", "triangle", "head", "shoulders", "flag", "cup"]):
            return self._parse_pattern_recognition(desc)

        return NLStrategyResult(success=False, error="No rule-based match found")

    def _parse_mean_reversion(self, desc: str) -> NLStrategyResult:
        """Parse mean reversion strategies."""
        # Extract RSI period
        rsi_match = re.search(r'rsi\s*(\d+)', desc)
        rsi_period = int(rsi_match.group(1)) if rsi_match else 14

        # Extract threshold
        thresh_match = re.search(r'(\d+)', desc)
        threshold = int(thresh_match.group(1)) if thresh_match else 30

        return NLStrategyResult(
            success=True,
            edge_type="VOLATILITY_REGIME",
            description=f"RSI{rsi_period} Mean Reversion (threshold={threshold})",
            entry_conditions={
                "indicator": "rsi",
                "period": rsi_period,
                "oversold_threshold": threshold,
                "overbought_threshold": 100 - threshold
            },
            exit_conditions={
                "type": "indicator_revert",
                "target_level": 50
            },
            risk_params={
                "stop_loss_atr_multiple": 2.0,
                "take_profit_atr_multiple": 3.0
            },
            confidence=0.7,
            expected_return=0.02,
            expected_drawdown=0.08,
            explanation=f"Mean reversion strategy using RSI{rsi_period}. Enters long when RSI falls below {threshold} (oversold) and short when above {100-threshold} (overbought)."
        )

    def _parse_momentum(self, desc: str) -> NLStrategyResult:
        """Parse momentum strategies."""
        # Check for EMA crossover
        if "ema" in desc or "crossover" in desc or "cross" in desc:
            fast_match = re.search(r'ema\s*(\d+)', desc)
            fast_period = int(fast_match.group(1)) if fast_match else 12
            slow_period = fast_period * 2 if fast_match else 26

            return NLStrategyResult(
                success=True,
                edge_type="MOMENTUM_MEAN_REVERSION",
                description=f"EMA{fast_period}/EMA{slow_period} Crossover Momentum",
                entry_conditions={
                    "type": "ema_crossover",
                    "fast_period": fast_period,
                    "slow_period": slow_period
                },
                exit_conditions={
                    "type": "crossover_reversal"
                },
                risk_params={
                    "stop_loss_atr_multiple": 2.0,
                    "take_profit_atr_multiple": 3.0
                },
                confidence=0.75,
                expected_return=0.035,
                expected_drawdown=0.10,
                explanation=f"Momentum strategy trading EMA crossovers. Long when EMA{fast_period} crosses above EMA{slow_period}, short when it crosses below."
            )

        # Breakout strategy
        return NLStrategyResult(
            success=True,
            edge_type="MOMENTUM_MEAN_REVERSION",
            description="Breakout Momentum Strategy",
            entry_conditions={
                "type": "breakout",
                "period": 20,
                "volume_confirm": True
            },
            exit_conditions={
                "type": "trailing_stop",
                "atr_multiple": 3.0
            },
            risk_params={
                "stop_loss_atr_multiple": 2.0,
                "take_profit_atr_multiple": 3.0
            },
            confidence=0.65,
            expected_return=0.03,
            expected_drawdown=0.12,
            explanation="Momentum breakout strategy. Enters when price breaks through recent highs with volume confirmation."
        )

    def _parse_volatility(self, desc: str) -> NLStrategyResult:
        """Parse volatility strategies."""
        # Extract ATR period
        atr_match = re.search(r'atr\s*(\d+)', desc)
        atr_period = int(atr_match.group(1)) if atr_match else 14

        return NLStrategyResult(
            success=True,
            edge_type="VOLATILITY_REGIME",
            description=f"ATR{atr_period} Breakout Expansion",
            entry_conditions={
                "type": "atr_breakout",
                "atr_period": atr_period,
                "expansion_threshold": 1.5
            },
            exit_conditions={
                "type": "time_based",
                "max_hold_bars": 20
            },
            risk_params={
                "stop_loss_atr_multiple": 2.0,
                "take_profit_atr_multiple": 3.0
            },
            confidence=0.68,
            expected_return=0.028,
            expected_drawdown=0.11,
            explanation=f"Volatility expansion strategy using ATR{atr_period}. Enters when volatility expands significantly."
        )

    def _parse_time_pattern(self, desc: str) -> NLStrategyResult:
        """Parse time-based strategies."""
        # Determine session
        if "asian" in desc or "tokyo" in desc:
            session = "asian"
            hour_range = (0, 8)
        elif "london" in desc:
            session = "london"
            hour_range = (8, 12)
        elif "ny" in desc or "new york" in desc:
            session = "new_york"
            hour_range = (13, 17)
        else:
            session = "generic"
            hour_range = (9, 16)

        return NLStrategyResult(
            success=True,
            edge_type="TIME_PATTERN",
            description=f"{session.title()} Session Time Pattern",
            entry_conditions={
                "type": "time_based",
                "session": session,
                "hour_start": hour_range[0],
                "hour_end": hour_range[1]
            },
            exit_conditions={
                "type": "time_based",
                "exit_hour": hour_range[1]
            },
            risk_params={
                "stop_loss_atr_multiple": 1.5,
                "take_profit_atr_multiple": 2.0
            },
            confidence=0.55,
            expected_return=0.015,
            expected_drawdown=0.06,
            explanation=f"Time-based strategy trading {session.title()} session patterns."
        )

    def _parse_volume_pattern(self, desc: str) -> NLStrategyResult:
        """Parse volume-based strategies."""
        return NLStrategyResult(
            success=True,
            edge_type="MARKET_MICROSTRUCTURE",
            description="Volume Confirmation Strategy",
            entry_conditions={
                "type": "volume_confirmation",
                "volume_threshold": 1.5
            },
            exit_conditions={
                "type": "indicator_revert"
            },
            risk_params={
                "stop_loss_atr_multiple": 2.0,
                "take_profit_atr_multiple": 3.0
            },
            confidence=0.60,
            expected_return=0.022,
            expected_drawdown=0.09,
            explanation="Volume-based strategy requiring high volume confirmation for entries."
        )

    def _parse_pattern_recognition(self, desc: str) -> NLStrategyResult:
        """Parse pattern recognition strategies."""
        if "double" in desc:
            pattern = "double_top_bottom"
        elif "triangle" in desc:
            pattern = "triangle"
        elif "head" in desc or "shoulders" in desc:
            pattern = "head_shoulders"
        elif "flag" in desc:
            pattern = "flag"
        else:
            pattern = "generic"

        return NLStrategyResult(
            success=True,
            edge_type="MOMENTUM_MEAN_REVERSION",
            description=f"{pattern.title()} Pattern Recognition",
            entry_conditions={
                "type": "pattern",
                "pattern_type": pattern
            },
            exit_conditions={
                "type": "pattern_target"
            },
            risk_params={
                "stop_loss_atr_multiple": 2.0,
                "take_profit_atr_multiple": 3.0
            },
            confidence=0.58,
            expected_return=0.025,
            expected_drawdown=0.10,
            explanation=f"Pattern recognition strategy identifying {pattern} formations."
        )

    def _llm_generate_strategy(self, request: NLStrategyRequest) -> NLStrategyResult:
        """Use LLM to generate strategy from natural language."""
        system_prompt = """You are an expert quantitative trading strategist. Convert user descriptions into structured trading strategies.

Always respond with valid JSON in this exact format:
{
    "edge_type": "MOMENTUM_MEAN_REVERSION|VOLATILITY_REGIME|MARKET_MICROSTRUCTURE|TIME_PATTERN|CORRELATION_ARBITRAGE|ORDER_FLOW_IMBALANCE|LIQUIDITY_PREMIUM",
    "description": "Brief strategy name",
    "entry_conditions": {"indicator": "...", "period": 10, "threshold": 30},
    "exit_conditions": {"type": "...", "value": ...},
    "risk_params": {"stop_loss_atr_multiple": 2.0, "take_profit_atr_multiple": 3.0},
    "confidence": 0.7,
    "expected_return": 0.03,
    "expected_drawdown": 0.10,
    "explanation": "Brief explanation of how the strategy works"
}

Supported edge_types: MOMENTUM_MEAN_REVERSION, VOLATILITY_REGIME, MARKET_MICROSTRUCTURE, TIME_PATTERN, CORRELATION_ARBITRAGE, ORDER_FLOW_IMBALANCE, LIQUIDITY_PREMIUM"""

        try:
            if self.provider == LLMProvider.OPENAI:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Convert this strategy: {request.description}"}
                    ],
                    temperature=0.3
                )
                content = response.choices[0].message.content

            elif self.provider == LLMProvider.ANTHROPIC:
                response = self.client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=1024,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": f"Convert this strategy: {request.description}"}
                    ]
                )
                content = response.content[0].text

            # Parse JSON response
            data = json.loads(content)

            return NLStrategyResult(
                success=True,
                edge_type=data["edge_type"],
                description=data["description"],
                entry_conditions=data["entry_conditions"],
                exit_conditions=data["exit_conditions"],
                risk_params=data["risk_params"],
                confidence=data["confidence"],
                expected_return=data["expected_return"],
                expected_drawdown=data["expected_drawdown"],
                explanation=data["explanation"],
                raw_response=content
            )

        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            return NLStrategyResult(success=False, error=str(e))

    def _mock_generate_strategy(self, request: NLStrategyRequest) -> NLStrategyResult:
        """Generate a mock strategy when no LLM is available."""
        desc = request.description.lower()

        # Simple keyword matching for mock
        if "mean" in desc or "reversion" in desc or "rsi" in desc:
            return self._parse_mean_reversion(desc)
        elif "momentum" in desc or "trend" in desc:
            return self._parse_momentum(desc)
        elif "volatility" in desc or "atr" in desc:
            return self._parse_volatility(desc)
        else:
            # Default fallback
            return NLStrategyResult(
                success=True,
                edge_type="MOMENTUM_MEAN_REVERSION",
                description="Generated Strategy: " + request.description[:50],
                entry_conditions={
                    "type": "generic",
                    "description": request.description
                },
                exit_conditions={
                    "type": "time_based",
                    "max_hold_bars": 20
                },
                risk_params={
                    "stop_loss_atr_multiple": 2.0,
                    "take_profit_atr_multiple": 3.0
                },
                confidence=0.5,
                expected_return=0.02,
                expected_drawdown=0.10,
                explanation="Generated strategy based on description. Please verify parameters."
            )


def create_nl_generator(provider: str = "mock", api_key: Optional[str] = None) -> NLStrategyGenerator:
    """
    Factory function to create a natural language strategy generator.

    Args:
        provider: LLM provider name ("openai", "anthropic", "ollama", "mock")
        api_key: API key for the provider (if required)

    Returns:
        NLStrategyGenerator instance
    """
    try:
        provider_enum = LLMProvider(provider.lower())
    except ValueError:
        logger.warning(f"Unknown provider '{provider}', using MOCK")
        provider_enum = LLMProvider.MOCK

    return NLStrategyGenerator(provider=provider_enum, api_key=api_key)
