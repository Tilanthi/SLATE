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
    """Supported LLM providers.

    Inspired by TradingAgents' multi-provider architecture with support for:
    - Major cloud providers (OpenAI, Google, Anthropic)
    - Chinese models (DeepSeek, Qwen, GLM)
    - Aggregator services (OpenRouter)
    - Local models (Ollama)
    - Enterprise (Azure OpenAI)
    """
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    XAI = "xai"  # xAI (Grok)
    DEEPSEEK = "deepseek"
    QWEN = "qwen"  # Alibaba DashScope
    GLM = "glm"  # Zhipu AI
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"
    AZURE = "azure"  # Azure OpenAI
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

        # Map providers to their environment variable names
        env_key_map = {
            LLMProvider.OPENAI: "OPENAI_API_KEY",
            LLMProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
            LLMProvider.GOOGLE: "GOOGLE_API_KEY",
            LLMProvider.XAI: "XAI_API_KEY",
            LLMProvider.DEEPSEEK: "DEEPSEEK_API_KEY",
            LLMProvider.QWEN: "DASHSCOPE_API_KEY",  # Alibaba DashScope
            LLMProvider.GLM: "ZHIPU_API_KEY",  # Zhipu AI
            LLMProvider.OPENROUTER: "OPENROUTER_API_KEY",
            LLMProvider.OLLAMA: None,  # No API key needed for local
            LLMProvider.AZURE: "AZURE_API_KEY",
            LLMProvider.MOCK: None
        }

        env_var = env_key_map.get(provider)
        self.api_key = api_key or (os.getenv(env_var) if env_var else None)
        self._init_client()

    def _init_client(self):
        """Initialize LLM client based on provider.

        Supports multiple providers inspired by TradingAgents architecture:
        - OpenAI (GPT models)
        - Anthropic (Claude models)
        - Google (Gemini models)
        - xAI (Grok models)
        - DeepSeek (Chinese LLM)
        - Qwen (Alibaba DashScope)
        - GLM (Zhipu AI)
        - OpenRouter (Aggregator)
        - Ollama (Local models)
        - Azure OpenAI (Enterprise)
        """
        if self.provider == LLMProvider.OPENAI:
            try:
                import openai
                self.client = openai.OpenAI(api_key=self.api_key)
                self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
                logger.info(f"OpenAI client initialized with model {self.model}")
            except ImportError:
                logger.warning("OpenAI not installed, falling back to MOCK")
                self.provider = LLMProvider.MOCK
                self.client = None

        elif self.provider == LLMProvider.ANTHROPIC:
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key)
                self.model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")
                logger.info(f"Anthropic client initialized with model {self.model}")
            except ImportError:
                logger.warning("Anthropic not installed, falling back to MOCK")
                self.provider = LLMProvider.MOCK
                self.client = None

        elif self.provider == LLMProvider.GOOGLE:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.client = genai
                self.model = os.getenv("GOOGLE_MODEL", "gemini-2.0-flash-exp")
                logger.info(f"Google client initialized with model {self.model}")
            except ImportError:
                logger.warning("Google AI not installed, falling back to MOCK")
                self.provider = LLMProvider.MOCK
                self.client = None

        elif self.provider == LLMProvider.XAI:
            try:
                import openai
                self.client = openai.OpenAI(
                    base_url="https://api.x.ai/v1",
                    api_key=self.api_key
                )
                self.model = os.getenv("XAI_MODEL", "grok-beta")
                logger.info(f"xAI client initialized with model {self.model}")
            except ImportError:
                logger.warning("xAI not available, falling back to MOCK")
                self.provider = LLMProvider.MOCK
                self.client = None

        elif self.provider == LLMProvider.DEEPSEEK:
            try:
                import openai
                self.client = openai.OpenAI(
                    base_url="https://api.deepseek.com",
                    api_key=self.api_key
                )
                self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
                logger.info(f"DeepSeek client initialized with model {self.model}")
            except ImportError:
                logger.warning("DeepSeek not available, falling back to MOCK")
                self.provider = LLMProvider.MOCK
                self.client = None

        elif self.provider == LLMProvider.QWEN:
            try:
                import dashscope
                self.client = dashscope
                self.model = os.getenv("QWEN_MODEL", "qwen-turbo")
                logger.info(f"Qwen (DashScope) client initialized with model {self.model}")
            except ImportError:
                logger.warning("DashScope not installed, falling back to MOCK")
                self.provider = LLMProvider.MOCK
                self.client = None

        elif self.provider == LLMProvider.GLM:
            try:
                import zhipuai
                self.client = zhipuai.ZhipuAI(api_key=self.api_key)
                self.model = os.getenv("GLM_MODEL", "glm-4-flash")
                logger.info(f"GLM (ZhipuAI) client initialized with model {self.model}")
            except ImportError:
                logger.warning("ZhipuAI not installed, falling back to MOCK")
                self.provider = LLMProvider.MOCK
                self.client = None

        elif self.provider == LLMProvider.OPENROUTER:
            try:
                import openai
                self.client = openai.OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=self.api_key
                )
                self.model = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-haiku")
                logger.info(f"OpenRouter client initialized with model {self.model}")
            except ImportError:
                logger.warning("OpenRouter not available, falling back to MOCK")
                self.provider = LLMProvider.MOCK
                self.client = None

        elif self.provider == LLMProvider.OLLAMA:
            try:
                import requests
                self.client = requests
                self.ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
                self.model = os.getenv("OLLAMA_MODEL", "llama3.2")
                logger.info(f"Ollama client initialized at {self.ollama_base} with model {self.model}")
            except ImportError:
                logger.warning("Requests not installed for Ollama")
                self.client = None

        elif self.provider == LLMProvider.AZURE:
            try:
                import openai
                self.client = openai.AzureOpenAI(
                    api_key=self.api_key,
                    api_version=os.getenv("AZURE_API_VERSION", "2024-02-01"),
                    azure_endpoint=os.getenv("AZURE_ENDPOINT")
                )
                self.model = os.getenv("AZURE_DEPLOYMENT", "gpt-4o-mini")
                logger.info(f"Azure OpenAI client initialized with deployment {self.model}")
            except ImportError:
                logger.warning("Azure OpenAI not installed, falling back to MOCK")
                self.provider = LLMProvider.MOCK
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
        """
        Use LLM to generate strategy from natural language.

        Supports multiple providers with unified interface:
        - OpenAI, Anthropic, Google, xAI, DeepSeek, Qwen, GLM, OpenRouter, Ollama, Azure
        """
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

        user_message = f"Convert this strategy: {request.description}"

        try:
            # OpenAI-compatible APIs (OpenAI, xAI, DeepSeek, OpenRouter, Azure)
            if self.provider in [LLMProvider.OPENAI, LLMProvider.XAI,
                                 LLMProvider.DEEPSEEK, LLMProvider.OPENROUTER,
                                 LLMProvider.AZURE]:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=0.3
                )
                content = response.choices[0].message.content

            # Anthropic (Claude)
            elif self.provider == LLMProvider.ANTHROPIC:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_message}
                    ]
                )
                content = response.content[0].text

            # Google (Gemini)
            elif self.provider == LLMProvider.GOOGLE:
                model = self.client.GenerativeModel(self.model)
                response = model.generate_content(
                    f"{system_prompt}\n\nUser: {user_message}",
                    generation_config=self.client.types.GenerationConfig(
                        temperature=0.3,
                        max_output_tokens=1024,
                    )
                )
                content = response.text

            # Qwen (Alibaba DashScope)
            elif self.provider == LLMProvider.QWEN:
                response = self.client.Generation.call(
                    model=self.model,
                    messages=[
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_message}
                    ],
                    result_format='message',
                    temperature=0.3
                )
                content = response.output.choices[0].message.content

            # GLM (ZhipuAI)
            elif self.provider == LLMProvider.GLM:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=0.3
                )
                content = response.choices[0].message.content

            # Ollama (Local models)
            elif self.provider == LLMProvider.OLLAMA:
                response = self.client.post(
                    f"{self.ollama_base}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": f"{system_prompt}\n\nUser: {user_message}",
                        "stream": False,
                        "options": {"temperature": 0.3}
                    },
                    timeout=30
                )
                content = response.json().get("response", "")

            else:
                return NLStrategyResult(success=False, error=f"Unsupported provider: {self.provider}")

            # Parse JSON response
            # Handle potential markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

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
