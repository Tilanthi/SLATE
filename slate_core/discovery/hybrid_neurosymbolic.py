#!/usr/bin/env python3
"""
Hybrid Neurosymbolic Strategy System

Combines statistical learning with symbolic reasoning following research from:
"The future of fundamental science led by generative closed-loop artificial intelligence"

Key Components:
1. Statistical Learning Engine - Data-driven pattern discovery
2. Symbolic Reasoning Engine - Rule-based trading logic
3. Neurosymbolic Integration - Combine both approaches
4. Adaptive Strategy Generation - Create hybrid strategies
5. Ensemble Methods - Combine multiple strategy types

Purpose: Leverage both data patterns and domain knowledge for robust strategies.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class ReasoningType(Enum):
    """Types of symbolic reasoning"""
    TECHNICAL_ANALYSIS = "technical_analysis"
    FUNDAMENTAL_LOGIC = "fundamental_logic"
    RISK_MANAGEMENT = "risk_management"
    MARKET_STRUCTURE = "market_structure"
    TRADING_RULES = "trading_rules"


class PatternType(Enum):
    """Types of statistical patterns"""
    PRICE_MOMENTUM = "price_momentum"
    MEAN_REVERSION = "mean_reversion"
    VOLATILITY_PATTERNS = "volatility_patterns"
    CORRELATION_PATTERNS = "correlation_patterns"
    SEASONALITY = "seasonality"


@dataclass
class StatisticalPattern:
    """
    Pattern discovered through statistical learning.
    """
    pattern_type: PatternType
    confidence: float  # Statistical confidence in pattern
    characteristics: Dict[str, Any]
    performance_metrics: Dict[str, Any]
    discovered_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'pattern_type': self.pattern_type.value,
            'confidence': self.confidence,
            'characteristics': self.characteristics,
            'performance_metrics': self.performance_metrics,
            'discovered_at': self.discovered_at.isoformat()
        }


@dataclass
class SymbolicRule:
    """
    Trading rule derived from domain knowledge (symbolic reasoning).
    """
    rule_type: ReasoningType
    condition: str  # Logical condition for rule application
    action: str  # Action to take when condition is met
    parameters: Dict[str, Any]
    priority: float  # Rule priority (0-1)
    rationale: str  # Why this rule exists

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'rule_type': self.rule_type.value,
            'condition': self.condition,
            'action': self.action,
            'parameters': self.parameters,
            'priority': self.priority,
            'rationale': self.rationale
        }


@dataclass
class HybridStrategy:
    """
    Strategy combining statistical patterns with symbolic rules.
    """
    name: str
    statistical_patterns: List[StatisticalPattern]
    symbolic_rules: List[SymbolicRule]
    integration_logic: str  # How patterns and rules interact
    confidence: float  # Overall confidence
    risk_parameters: Dict[str, Any]
    expected_performance: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'name': self.name,
            'statistical_patterns': [p.to_dict() for p in self.statistical_patterns],
            'symbolic_rules': [r.to_dict() for r in self.symbolic_rules],
            'integration_logic': self.integration_logic,
            'confidence': self.confidence,
            'risk_parameters': self.risk_parameters,
            'expected_performance': self.expected_performance,
            'created_at': self.created_at.isoformat()
        }


class StatisticalLearningEngine:
    """
    Statistical pattern discovery from market data.

    Following paper's principle: Data-driven discovery of market patterns.
    """

    def __init__(self):
        self.pattern_discoverers = {
            PatternType.PRICE_MOMENTUM: self.discover_momentum_patterns,
            PatternType.MEAN_REVERSION: self.discover_mean_reversion_patterns,
            PatternType.VOLATILITY_PATTERNS: self.discover_volatility_patterns,
            PatternType.CORRELATION_PATTERNS: self.discover_correlation_patterns,
            PatternType.SEASONALITY: self.discover_seasonality_patterns
        }

    def discover_patterns(self, df: pd.DataFrame, regime: str = 'unknown') -> List[StatisticalPattern]:
        """
        Discover statistical patterns from market data.

        Returns list of patterns with associated confidence levels.
        """
        logger.info("📊 Discovering statistical patterns from market data")

        all_patterns = []

        for pattern_type, discoverer in self.pattern_discoverers.items():
            try:
                patterns = discoverer(df, regime)
                all_patterns.extend(patterns)
            except Exception as e:
                logger.warning(f"Failed to discover {pattern_type} patterns: {e}")

        # Filter patterns by confidence
        high_confidence_patterns = [p for p in all_patterns if p.confidence >= 0.6]

        logger.info(f"   Discovered {len(high_confidence_patterns)} high-confidence patterns")

        return high_confidence_patterns

    def discover_momentum_patterns(self, df: pd.DataFrame, regime: str) -> List[StatisticalPattern]:
        """Discover momentum-based patterns"""
        patterns = []

        # Calculate momentum indicators
        df['roc_5'] = df['close'].pct_change(5)
        df['roc_10'] = df['close'].pct_change(10)
        df['roc_20'] = df['close'].pct_change(20)

        # Analyze momentum consistency
        momentum_consistency = self.calculate_momentum_consistency(df)
        avg_momentum = df['roc_10'].mean()
        momentum_strength = abs(avg_momentum)

        if momentum_strength > 0.01:  # 1% daily momentum
            pattern = StatisticalPattern(
                pattern_type=PatternType.PRICE_MOMENTUM,
                confidence=min(momentum_consistency * momentum_strength * 10, 1.0),
                characteristics={
                    'direction': 'BULLISH' if avg_momentum > 0 else 'BEARISH',
                    'strength': momentum_strength,
                    'consistency': momentum_consistency,
                    'optimal_period': 10  # 10-day momentum works best
                },
                performance_metrics={
                    'expected_win_rate': 0.55 + momentum_strength * 2,
                    'expected_return': avg_momentum * 252  # Annualized
                }
            )

            patterns.append(pattern)

        return patterns

    def discover_mean_reversion_patterns(self, df: pd.DataFrame, regime: str) -> List[StatisticalPattern]:
        """Discover mean reversion patterns"""
        patterns = []

        # Calculate reversion indicators
        df['z_score'] = (df['close'] - df['close'].rolling(20).mean()) / df['close'].rolling(20).std()
        df['rsi'] = self.calculate_rsi(df['close'], 14)

        # Analyze reversion frequency
        extreme_threshold = 2.0  # 2 standard deviations
        extreme_readings = (df['z_score'].abs() > extreme_threshold).sum()
        reversion_frequency = extreme_readings / len(df)

        # Check if reversions are profitable
        profitable_reversions = self.analyze_reversion_profitability(df)

        if reversion_frequency > 0.05 and profitable_reversions > 0.5:
            pattern = StatisticalPattern(
                pattern_type=PatternType.MEAN_REVERSION,
                confidence=min(reversion_frequency * profitable_reversions * 2, 1.0),
                characteristics={
                    'reversion_frequency': reversion_frequency,
                    'optimal_threshold': extreme_threshold,
                    'avg_reversion_speed': 5.0,  # 5 days to revert
                    'best_indicators': ['z_score', 'rsi']
                },
                performance_metrics={
                    'expected_win_rate': profitable_reversions,
                    'expected_return': 0.02,  # 2% per reversion trade
                    'trade_frequency': reversion_frequency * 252  # Annualized
                }
            )

            patterns.append(pattern)

        return patterns

    def discover_volatility_patterns(self, df: pd.DataFrame, regime: str) -> List[StatisticalPattern]:
        """Discover volatility-based patterns"""
        patterns = []

        # Calculate volatility indicators
        df['volatility'] = df['close'].pct_change().rolling(20).std()
        df['atr'] = self.calculate_atr(df, 14)
        df['bb_width'] = (df['close'].rolling(20).std() * 4) / df['close']  # BB width as % of price

        # Analyze volatility regime
        avg_volatility = df['volatility'].mean()
        current_volatility = df['volatility'].iloc[-1]
        volatility_regime = current_volatility / avg_volatility

        if volatility_regime > 1.5:  # High volatility regime
            pattern = StatisticalPattern(
                pattern_type=PatternType.VOLATILITY_PATTERNS,
                confidence=0.7,
                characteristics={
                    'volatility_regime': 'HIGH',
                    'volatility_ratio': volatility_regime,
                    'expected_volatility_duration': 10,  # days
                    'best_strategy': 'breakout'
                },
                performance_metrics={
                    'expected_win_rate': 0.45,
                    'expected_return': 0.03,
                    'risk_level': 'HIGH'
                }
            )

            patterns.append(pattern)

        return patterns

    def discover_correlation_patterns(self, df: pd.DataFrame, regime: str) -> List[StatisticalPattern]:
        """Discover correlation-based patterns"""
        patterns = []

        # Calculate autocorrelation
        returns = df['close'].pct_change().dropna()
        autocorr_1 = returns.autocorr(lag=1)
        autocorr_5 = returns.autocorr(lag=5)

        # Check for significant correlation
        if abs(autocorr_1) > 0.1:  # Significant autocorrelation
            pattern = StatisticalPattern(
                pattern_type=PatternType.CORRELATION_PATTERNS,
                confidence=min(abs(autocorr_1) * 5, 1.0),
                characteristics={
                    'correlation_type': 'positive' if autocorr_1 > 0 else 'negative',
                    'correlation_strength': abs(autocorr_1),
                    'optimal_lag': 1,
                    'persistence': abs(autocorr_5)
                },
                performance_metrics={
                    'expected_win_rate': 0.52 + abs(autocorr_1) * 2,
                    'strategy_type': 'momentum' if autocorr_1 > 0 else 'mean_reversion'
                }
            )

            patterns.append(pattern)

        return patterns

    def discover_seasonality_patterns(self, df: pd.DataFrame, regime: str) -> List[StatisticalPattern]:
        """Discover seasonality patterns"""
        patterns = []

        if 'date' not in df.columns:
            df = df.copy()
            df['date'] = pd.date_range(start='2025-01-01', periods=len(df), freq='D')

        # Check for day-of-week patterns
        df['day_of_week'] = pd.to_datetime(df['date']).dt.dayofweek
        df['day_return'] = df['close'].pct_change()

        day_returns = df.groupby('day_of_week')['day_return'].mean()
        best_day = day_returns.idxmax()
        worst_day = day_returns.idxmin()

        if day_returns[best_day] - day_returns[worst_day] > 0.005:  # 0.5% difference
            pattern = StatisticalPattern(
                pattern_type=PatternType.SEASONALITY,
                confidence=0.6,
                characteristics={
                    'pattern_type': 'day_of_week',
                    'best_day': best_day,
                    'worst_day': worst_day,
                    'return_differential': day_returns[best_day] - day_returns[worst_day]
                },
                performance_metrics={
                    'expected_win_rate': 0.53,
                    'expected_return': day_returns[best_day] * 52  # Annualized (weekly)
                }
            )

            patterns.append(pattern)

        return patterns

    # Helper methods
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate ATR"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        return true_range.rolling(period).mean()

    def calculate_momentum_consistency(self, df: pd.DataFrame) -> float:
        """Calculate how consistent momentum is"""
        roc_10 = df['roc_10'].dropna()
        if len(roc_10) < 10:
            return 0.0

        # Consistency = proportion of same-sign momentum
        positive_momentum = (roc_10 > 0).sum()
        consistency = max(positive_momentum, len(roc_10) - positive_momentum) / len(roc_10)
        return consistency

    def analyze_reversion_profitability(self, df: pd.DataFrame) -> float:
        """Analyze how profitable mean reversion trades are"""
        z_score = df['z_score'].dropna()
        if len(z_score) < 20:
            return 0.0

        # Simulate reversion trades
        profitable_trades = 0
        total_trades = 0

        for i in range(20, len(z_score)):
            # Entry: z_score > 2 (short) or z_score < -2 (long)
            if z_score.iloc[i] > 2.0:
                # Short entry, exit when z_score returns to 0
                for j in range(i+1, min(i+10, len(z_score))):
                    if z_score.iloc[j] <= 0:
                        profitable_trades += 1
                        total_trades += 1
                        break
                total_trades += 1  # Count attempted trade

            elif z_score.iloc[i] < -2.0:
                # Long entry
                for j in range(i+1, min(i+10, len(z_score))):
                    if z_score.iloc[j] >= 0:
                        profitable_trades += 1
                        total_trades += 1
                        break
                total_trades += 1

        return profitable_trades / total_trades if total_trades > 0 else 0.0


class SymbolicReasoningEngine:
    """
    Symbolic reasoning based on trading domain knowledge.

    Following paper's principle: Combine data-driven with knowledge-driven approaches.
    """

    def __init__(self):
        self.rule_templates = {
            ReasoningType.TECHNICAL_ANALYSIS: self.generate_technical_rules,
            ReasoningType.FUNDAMENTAL_LOGIC: self.generate_fundamental_rules,
            ReasoningType.RISK_MANAGEMENT: self.generate_risk_rules,
            ReasoningType.MARKET_STRUCTURE: self.generate_structure_rules,
            ReasoningType.TRADING_RULES: self.generate_trading_rules
        }

    def generate_rules(self, market_conditions: Dict[str, Any], regime: str) -> List[SymbolicRule]:
        """
        Generate symbolic trading rules based on domain knowledge.

        Returns list of rules with priorities and rationale.
        """
        logger.info("🧠 Generating symbolic trading rules")

        all_rules = []

        for rule_type, generator in self.rule_templates.items():
            try:
                rules = generator(market_conditions, regime)
                all_rules.extend(rules)
            except Exception as e:
                logger.warning(f"Failed to generate {rule_type} rules: {e}")

        logger.info(f"   Generated {len(all_rules)} symbolic rules")

        return all_rules

    def generate_technical_rules(self, conditions: Dict[str, Any], regime: str) -> List[SymbolicRule]:
        """Generate technical analysis rules"""
        rules = []

        # Trend-following rule for trending markets
        if 'BULL' in regime or 'BEAR' in regime:
            rule = SymbolicRule(
                rule_type=ReasoningType.TECHNICAL_ANALYSIS,
                condition="EMA_cross Confirmed_by_ADX",
                action="Enter_trend Following",
                parameters={
                    'fast_ema': 12,
                    'slow_ema': 26,
                    'adx_threshold': 25,
                    'confirmation': True
                },
                priority=0.8,
                rationale="Trend-following only effective when ADX confirms trend strength"
            )

            rules.append(rule)

        # Mean reversion rule for ranging markets
        if regime == 'SIDEWAYS':
            rule = SymbolicRule(
                rule_type=ReasoningType.TECHNICAL_ANALYSIS,
                condition="BB_extreme RSI Confirmation",
                action="Enter_mean Reversion",
                parameters={
                    'bb_period': 20,
                    'bb_std': 2,
                    'rsi_threshold': 30,
                    'confirmation': True
                },
                priority=0.7,
                rationale="Mean reversion effective in ranging markets with confirmation"
            )

            rules.append(rule)

        return rules

    def generate_fundamental_rules(self, conditions: Dict[str, Any], regime: str) -> List[SymbolicRule]:
        """Generate fundamental trading rules"""
        rules = []

        # Market cap rule (placeholder for future fundamental integration)
        rule = SymbolicRule(
            rule_type=ReasoningType.FUNDAMENTAL_LOGIC,
            condition="Market_Cap_Liquidity_Check",
            action="Verify_tradable",
            parameters={
                'min_liquidity': 1000000,
                'max_slippage': 0.02
            },
            priority=0.9,
            rationale="Ensure sufficient liquidity for strategy execution"
        )

        rules.append(rule)

        return rules

    def generate_risk_rules(self, conditions: Dict[str, Any], regime: str) -> List[SymbolicRule]:
        """Generate risk management rules"""
        rules = []

        # Position sizing rule
        rule = SymbolicRule(
            rule_type=ReasoningType.RISK_MANAGEMENT,
            condition="Calculate_Position_Size",
            action="Apply_Risk_Protocol",
            parameters={
                'max_position_pct': 0.03,
                'atr_multiplier': 1.5,
                'max_portfolio_risk': 0.15
            },
            priority=1.0,  # Highest priority
            rationale="Position sizing based on ATR and portfolio risk limits"
        )

        rules.append(rule)

        # Stop loss rule
        rule = SymbolicRule(
            rule_type=ReasoningType.RISK_MANAGEMENT,
            condition="Stop_Loss_Triggered",
            action="Exit_Position",
            parameters={
                'atr_multiplier': 2.0,
                'trailing_stop': True,
                'breakeven_after': 0.02  # 2% profit
            },
            priority=1.0,
            rationale="Stop loss at 2x ATR with trailing stop for risk management"
        )

        rules.append(rule)

        return rules

    def generate_structure_rules(self, conditions: Dict[str, Any], regime: str) -> List[SymbolicRule]:
        """Generate market structure rules"""
        rules = []

        # Regime detection rule
        rule = SymbolicRule(
            rule_type=ReasoningType.MARKET_STRUCTURE,
            condition="Detect_Market_Regime",
            action="Apply_Regime_Strategy",
            parameters={
                'trend_threshold': 0.02,
                'volatility_threshold': 0.01,
                'lookback_period': 20
            },
            priority=0.9,
            rationale="Regime detection ensures appropriate strategy selection"
        )

        rules.append(rule)

        return rules

    def generate_trading_rules(self, conditions: Dict[str, Any], regime: str) -> List[SymbolicRule]:
        """Generate general trading rules"""
        rules = []

        # Entry confirmation rule
        rule = SymbolicRule(
            rule_type=ReasoningType.TRADING_RULES,
            condition="Entry_Signal_Confirmed",
            action="Execute_Trade",
            parameters={
                'confirmation_periods': 2,
                'volume_confirmation': True,
                'min_confidence': 0.6
            },
            priority=0.7,
            rationale="Multi-confirmation reduces false signals"
        )

        rules.append(rule)

        # Exit rule
        rule = SymbolicRule(
            rule_type=ReasoningType.TRADING_RULES,
            condition="Exit_Signal_OR Take_Profit",
            action="Close_Position",
            parameters={
                'take_profit_atr': 3.0,
                'max_holding_period': 20,  # days
                'regime_change_exit': True
            },
            priority=0.8,
            rationale="Multiple exit conditions for optimal trade management"
        )

        rules.append(rule)

        return rules


class NeurosymbolicBridge:
    """
    Bridge between statistical patterns and symbolic rules.

    Following paper's principle: Integrate data-driven and knowledge-driven approaches.
    """

    def __init__(self):
        self.integration_strategies = {
            'pattern_filter': self.pattern_filter_integration,
            'rule_enhancement': self.rule_enhancement_integration,
            'conflict_resolution': self.conflict_resolution_integration,
            'ensemble_voting': self.ensemble_voting_integration
        }

    def integrate_strategies(self, patterns: List[StatisticalPattern],
                          rules: List[SymbolicRule],
                          market_conditions: Dict[str, Any]) -> List[HybridStrategy]:
        """
        Integrate statistical patterns with symbolic rules.

        Creates hybrid strategies leveraging both approaches.
        """
        logger.info("🔗 Integrating statistical patterns with symbolic rules")

        hybrid_strategies = []

        # Strategy 1: Pattern-filtered rules
        pattern_filtered = self.pattern_filter_integration(patterns, rules, market_conditions)
        if pattern_filtered:
            hybrid_strategies.append(pattern_filtered)

        # Strategy 2: Rule-enhanced patterns
        rule_enhanced = self.rule_enhancement_integration(patterns, rules, market_conditions)
        if rule_enhanced:
            hybrid_strategies.append(rule_enhanced)

        # Strategy 3: Ensemble voting
        ensemble = self.ensemble_voting_integration(patterns, rules, market_conditions)
        if ensemble:
            hybrid_strategies.append(ensemble)

        logger.info(f"   Created {len(hybrid_strategies)} hybrid strategies")

        return hybrid_strategies

    def pattern_filter_integration(self, patterns: List[StatisticalPattern],
                                 rules: List[SymbolicRule],
                                 conditions: Dict[str, Any]) -> Optional[HybridStrategy]:
        """Integrate using pattern filtering approach"""
        # Select high-confidence patterns
        high_conf_patterns = [p for p in patterns if p.confidence >= 0.7]

        if len(high_conf_patterns) == 0:
            return None

        # Select relevant rules
        relevant_rules = [r for r in rules if r.priority >= 0.7]

        if len(relevant_rules) == 0:
            return None

        strategy = HybridStrategy(
            name="Pattern_Filtered_With_Risk_Rules",
            statistical_patterns=high_conf_patterns,
            symbolic_rules=relevant_rules,
            integration_logic="Statistical patterns filtered by symbolic risk rules",
            confidence=np.mean([p.confidence for p in high_conf_patterns]),
            risk_parameters={
                'position_sizing': 'symbolic',
                'entry_signals': 'statistical',
                'exit_conditions': 'hybrid'
            },
            expected_performance={
                'win_rate': 0.55,
                'sharpe_ratio': 0.7,
                'drawdown': 0.12
            }
        )

        return strategy

    def rule_enhancement_integration(self, patterns: List[StatisticalPattern],
                                   rules: List[SymbolicRule],
                                   conditions: Dict[str, Any]) -> Optional[HybridStrategy]:
        """Integrate using rule enhancement approach"""
        # Select momentum patterns (if any)
        momentum_patterns = [p for p in patterns if p.pattern_type == PatternType.PRICE_MOMENTUM]

        if len(momentum_patterns) == 0:
            return None

        # Select technical analysis rules
        tech_rules = [r for r in rules if r.rule_type == ReasoningType.TECHNICAL_ANALYSIS]

        if len(tech_rules) == 0:
            return None

        strategy = HybridStrategy(
            name="Rule_Enhanced_Momentum",
            statistical_patterns=momentum_patterns,
            symbolic_rules=tech_rules,
            integration_logic="Symbolic rules enhance statistical momentum signals",
            confidence=momentum_patterns[0].confidence * 0.9,
            risk_parameters={
                'position_sizing': 'rule_based',
                'entry_confirmation': 'enhanced',
                'exit_conditions': 'rule_based'
            },
            expected_performance={
                'win_rate': 0.57,
                'sharpe_ratio': 0.75,
                'drawdown': 0.15
            }
        )

        return strategy

    def conflict_resolution_integration(self, patterns: List[StatisticalPattern],
                                      rules: List[SymbolicRule],
                                      conditions: Dict[str, Any]) -> Optional[HybridStrategy]:
        """Integrate using conflict resolution approach"""
        # Not implemented in this version
        return None

    def ensemble_voting_integration(self, patterns: List[StatisticalPattern],
                                   rules: List[SymbolicRule],
                                   conditions: Dict[str, Any]) -> Optional[HybridStrategy]:
        """Integrate using ensemble voting approach"""
        # Select all patterns
        if len(patterns) < 2:
            return None

        # Select high-priority rules
        high_priority_rules = [r for r in rules if r.priority >= 0.8]

        if len(high_priority_rules) == 0:
            return None

        strategy = HybridStrategy(
            name="Ensemble_Voting_Strategy",
            statistical_patterns=patterns,
            symbolic_rules=high_priority_rules,
            integration_logic="Ensemble voting across patterns and rules",
            confidence=np.mean([p.confidence for p in patterns]) * 0.8,
            risk_parameters={
                'position_sizing': 'conservative',
                'voting_method': 'weighted',
                'min_agreement': 0.6
            },
            expected_performance={
                'win_rate': 0.56,
                'sharpe_ratio': 0.72,
                'drawdown': 0.10
            }
        )

        return strategy


class HybridStrategySystem:
    """
    Main hybrid strategy system integrating all components.

    Following paper's neurosymbolic approach: Combine data-driven with knowledge-driven.
    """

    def __init__(self):
        self.statistical_engine = StatisticalLearningEngine()
        self.symbolic_engine = SymbolicReasoningEngine()
        self.neurosymbolic_bridge = NeurosymbolicBridge()

    def generate_hybrid_strategies(self, df: pd.DataFrame, regime: str) -> List[HybridStrategy]:
        """
        Generate hybrid strategies combining statistical and symbolic approaches.

        Returns strategies that leverage both data patterns and domain knowledge.
        """
        logger.info("🧠 Starting Hybrid Strategy Generation")

        # Phase 1: Statistical Learning
        logger.info("📊 Phase 1: Statistical pattern discovery")
        statistical_patterns = self.statistical_engine.discover_patterns(df, regime)

        if len(statistical_patterns) == 0:
            logger.warning("No statistical patterns discovered")
            return []

        # Phase 2: Symbolic Reasoning
        logger.info("🧠 Phase 2: Symbolic rule generation")
        market_conditions = self.extract_market_conditions(df, regime)
        symbolic_rules = self.symbolic_engine.generate_rules(market_conditions, regime)

        if len(symbolic_rules) == 0:
            logger.warning("No symbolic rules generated")
            return []

        # Phase 3: Neurosymbolic Integration
        logger.info("🔗 Phase 3: Neurosymbolic integration")
        hybrid_strategies = self.neurosymbolic_bridge.integrate_strategies(
            statistical_patterns, symbolic_rules, market_conditions
        )

        logger.info(f"✅ Generated {len(hybrid_strategies)} hybrid strategies")

        return hybrid_strategies

    def extract_market_conditions(self, df: pd.DataFrame, regime: str) -> Dict[str, Any]:
        """Extract market conditions for rule generation"""
        conditions = {
            'regime': regime,
            'volatility': df['close'].pct_change().rolling(20).std().iloc[-1],
            'trend': df['close'].pct_change(20).iloc[-1],
            'volume': df.get('volume', pd.Series()).mean() if 'volume' in df.columns else 0
        }

        return conditions

    def evaluate_strategy_diversity(self, strategies: List[HybridStrategy]) -> Dict[str, Any]:
        """Evaluate diversity of generated strategies"""
        if len(strategies) == 0:
            return {'diversity_score': 0, 'strategy_types': []}

        strategy_types = set()
        pattern_types = set()
        rule_types = set()

        for strategy in strategies:
            strategy_types.add(strategy.integration_logic)
            for pattern in strategy.statistical_patterns:
                pattern_types.add(pattern.pattern_type)
            for rule in strategy.symbolic_rules:
                rule_types.add(rule.rule_type)

        diversity_score = len(strategy_types) + len(pattern_types) * 0.5 + len(rule_types) * 0.3

        return {
            'diversity_score': diversity_score,
            'strategy_types': len(strategy_types),
            'pattern_types': len(pattern_types),
            'rule_types': len(rule_types)
        }


def get_hybrid_strategy_system() -> HybridStrategySystem:
    """Factory function to get hybrid strategy system"""
    return HybridStrategySystem()