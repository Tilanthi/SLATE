"""
SLATE Trading Decision Maker

Implements adaptive decision-making for autonomous trading exploration.
Moves beyond predefined workflows using market intelligence and opportunity assessment.
"""

import logging
import random
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass

from .config import (
    AutonomousConfig,
    TradingGoal,
    GoalType,
    Discovery
)

logger = logging.getLogger(__name__)


@dataclass
class MarketGap:
    """Represents a gap in trading knowledge or opportunity"""
    gap_type: str  # strategy_gap, regime_gap, correlation_gap, risk_gap
    description: str
    symbol: str
    timeframe: str
    importance: float  # 0.0 to 1.0
    difficulty: float  # 0.0 to 1.0
    estimated_value: float  # Expected profitability
    market_conditions: Dict[str, Any]


class TradingDecisionMaker:
    """
    Generate autonomous trading goals using market intelligence.

    This decision-maker moves beyond reactive workflows to genuine
    adaptive decision-making by:
    - Analyzing market gaps and opportunities
    - Considering current market conditions
    - Evaluating computational resources
    - Ranking opportunities by expected value
    - Generating diverse exploration goals

    SAFETY: All goals respect transaction cost requirements and risk limits.
    """

    def __init__(self, config: AutonomousConfig):
        """
        Initialize the trading decision-maker.

        Args:
            config: Autonomous configuration with constraints
        """
        self.config = config
        self.goal_history = []
        self.market_gap_cache = []

        # Market intelligence tracking
        self.regime_history = {}
        self.volatility_history = {}
        self.correlation_cache = {}

        logger.info("Trading Decision Maker initialized")

    def generate_goals(self, market_intelligence: Dict[str, Any],
                      resource_status: Dict[str, Any]) -> List[TradingGoal]:
        """
        Generate autonomous trading goals for exploration.

        This is the core method that enables adaptive decision-making.
        It analyzes the current state, identifies opportunities, and
        creates prioritized goals for autonomous exploration.

        Args:
            market_intelligence: Current market conditions and intelligence
            resource_status: Current resource availability

        Returns:
            List of prioritized TradingGoal objects
        """
        logger.info("Generating autonomous trading goals...")

        goals = []
        current_regime = market_intelligence.get('current_regime', {})
        available_symbols = self.config.allowed_symbols
        available_timeframes = self.config.allowed_timeframes

        # 1. MARKET REGIME ANALYSIS GOALS
        if self.config.enable_regime_analysis:
            regime_goals = self._generate_regime_analysis_goals(
                current_regime, available_symbols, available_timeframes
            )
            goals.extend(regime_goals)

        # 2. STRATEGY DISCOVERY GOALS
        if self.config.enable_strategy_discovery:
            strategy_goals = self._generate_strategy_discovery_goals(
                market_intelligence, resource_status
            )
            goals.extend(strategy_goals)

        # 3. PATTERN RECOGNITION GOALS
        if self.config.enable_pattern_recognition:
            pattern_goals = self._generate_pattern_recognition_goals(
                current_regime, available_symbols
            )
            goals.extend(pattern_goals)

        # 4. CORRELATION EXPLORATION GOALS
        if self.config.enable_correlation_exploration:
            correlation_goals = self._generate_correlation_exploration_goals(
                available_symbols, available_timeframes
            )
            goals.extend(correlation_goals)

        # 5. RISK OPTIMIZATION GOALS
        risk_goals = self._generate_risk_optimization_goals(market_intelligence)
        goals.extend(risk_goals)

        # Rank all goals by priority
        ranked_goals = self._rank_goals(goals, market_intelligence, resource_status)

        # Select top goals based on resource availability
        selected_goals = self._select_goals(ranked_goals, resource_status)

        logger.info(f"Generated {len(selected_goals)} autonomous goals (from {len(goals)} candidates)")
        self.goal_history.extend(selected_goals)

        return selected_goals

    def _generate_regime_analysis_goals(self, current_regime: Dict[str, Any],
                                       symbols: List[str], timeframes: List[str]) -> List[TradingGoal]:
        """Generate goals for analyzing market regimes"""
        goals = []

        for symbol in symbols:
            for timeframe in timeframes:
                # Goal: Deep analysis of current regime
                goal = TradingGoal(
                    goal_type=GoalType.MARKET_REGIME_ANALYSIS,
                    description=f"Analyze {symbol} {timeframe} market regime in detail",
                    symbol=symbol,
                    timeframe=timeframe,
                    priority=0.7,  # High priority for understanding current conditions
                    estimated_resources={
                        'cpu_percent': 8.0,
                        'duration_seconds': 120,
                        'memory_mb': 200
                    },
                    success_criteria={
                        'regime_identified': True,
                        'confidence': 0.8,
                        'characteristics_identified': 3
                    }
                )
                goals.append(goal)

        return goals

    def _generate_strategy_discovery_goals(self, market_intelligence: Dict[str, Any],
                                         resource_status: Dict[str, Any]) -> List[TradingGoal]:
        """Generate goals for discovering new trading strategies"""
        goals = []

        # Analyze market conditions to determine what types of strategies to explore
        current_volatility = market_intelligence.get('volatility_level', 'medium')
        current_trend = market_intelligence.get('trend_direction', 'neutral')

        # Generate strategy goals based on conditions
        strategy_types = []

        if current_volatility == 'high':
            strategy_types.append('volatility_exploitation')
        if current_trend in ['bullish', 'bearish']:
            strategy_types.append('trend_following')
        else:
            strategy_types.append('mean_reversion')

        for strategy_type in strategy_types:
            for symbol in self.config.allowed_symbols[:2]:  # Limit to top 2 symbols
                goal = TradingGoal(
                    goal_type=GoalType.STRATEGY_DISCOVERY,
                    description=f"Discover {strategy_type} strategies for {symbol}",
                    symbol=symbol,
                    timeframe='1h',  # Default to 1h for discovery
                    priority=0.8,  # High priority - this is core to SLATE
                    estimated_resources={
                        'cpu_percent': 15.0,
                        'duration_seconds': 300,  # 5 minutes per strategy
                        'memory_mb': 500
                    },
                    success_criteria={
                        'strategies_found': 5,
                        'profitable_strategies': 1,
                        'min_sharpe_ratio': 0.5,
                        'realistic_costs': True  # CRITICAL
                    }
                )
                goals.append(goal)

        return goals

    def _generate_pattern_recognition_goals(self, current_regime: Dict[str, Any],
                                          symbols: List[str]) -> List[TradingGoal]:
        """Generate goals for recognizing trading patterns"""
        goals = []

        # Focus on symbols with interesting regime conditions
        interesting_symbols = [s for s in symbols if s in current_regime.keys()]

        for symbol in interesting_symbols:
            goal = TradingGoal(
                goal_type=GoalType.PATTERN_RECOGNITION,
                description=f"Identify technical patterns in {symbol} across timeframes",
                symbol=symbol,
                timeframe='1h',
                priority=0.6,  # Medium priority
                estimated_resources={
                    'cpu_percent': 10.0,
                    'duration_seconds': 180,
                    'memory_mb': 300
                },
                success_criteria={
                    'patterns_found': 3,
                    'patterns_validated': 1,
                    'predictive_power': 0.6
                }
            )
            goals.append(goal)

        return goals

    def _generate_correlation_exploration_goals(self, symbols: List[str],
                                              timeframes: List[str]) -> List[TradingGoal]:
        """Generate goals for exploring market correlations"""
        goals = []

        if len(symbols) < 2:
            return goals  # Need at least 2 symbols for correlation

        # Create symbol pairs
        symbol_pairs = []
        for i, symbol1 in enumerate(symbols):
            for symbol2 in symbols[i+1:]:
                symbol_pairs.append((symbol1, symbol2))

        # Generate correlation goals for top pairs
        for symbol1, symbol2 in symbol_pairs[:3]:  # Top 3 pairs
            goal = TradingGoal(
                goal_type=GoalType.CORRELATION_EXPLORATION,
                description=f"Explore correlations between {symbol1} and {symbol2}",
                symbol=f"{symbol1}_{symbol2}",
                timeframe='1h',
                priority=0.5,  # Lower priority but valuable
                estimated_resources={
                    'cpu_percent': 5.0,
                    'duration_seconds': 90,
                    'memory_mb': 150
                },
                success_criteria={
                    'correlation_found': True,
                    'correlation_strength': 0.7,
                    'tradable': True
                }
            )
            goals.append(goal)

        return goals

    def _generate_risk_optimization_goals(self, market_intelligence: Dict[str, Any]) -> List[TradingGoal]:
        """Generate goals for optimizing risk management"""
        goals = []

        # Portfolio-level risk optimization
        goal = TradingGoal(
            goal_type=GoalType.PORTFOLIO_OPTIMIZATION,
            description="Optimize portfolio risk allocation across current strategies",
            symbol="PORTFOLIO",
            timeframe="1h",
            priority=0.7,  # High priority - risk management is critical
            estimated_resources={
                'cpu_percent': 12.0,
                'duration_seconds': 240,
                'memory_mb': 400
            },
            success_criteria={
                'risk_optimized': True,
                'max_drawdown_reduced': True,
                'sharpe_improved': True
            }
        )
        goals.append(goal)

        return goals

    def _rank_goals(self, goals: List[TradingGoal],
                   market_intelligence: Dict[str, Any],
                   resource_status: Dict[str, Any]) -> List[TradingGoal]:
        """Rank goals by priority and expected value"""
        # Score each goal based on multiple factors
        scored_goals = []

        for goal in goals:
            # Base score from priority
            score = goal.priority

            # Boost score for strategy discovery (core to SLATE)
            if goal.goal_type == GoalType.STRATEGY_DISCOVERY:
                score *= 1.2

            # Adjust based on market conditions
            current_regime = market_intelligence.get('current_regime', {})
            if goal.symbol in current_regime:
                # Boost goals related to current market conditions
                score *= 1.1

            # Adjust based on resource efficiency
            cpu_cost = goal.estimated_resources.get('cpu_percent', 10.0)
            if cpu_cost < 10.0:  # Low CPU cost
                score *= 1.1
            elif cpu_cost > 20.0:  # High CPU cost
                score *= 0.9

            # Add some randomness to encourage exploration
            score *= (0.9 + 0.2 * random.random())  # +/- 10%

            scored_goals.append((score, goal))

        # Sort by score (descending)
        scored_goals.sort(key=lambda x: x[0], reverse=True)

        # Return ranked goals
        return [goal for score, goal in scored_goals]

    def _select_goals(self, ranked_goals: List[TradingGoal],
                     resource_status: Dict[str, Any]) -> List[TradingGoal]:
        """Select goals that fit within resource constraints"""
        selected_goals = []
        total_cpu = 0.0
        total_time = 0.0

        for goal in ranked_goals:
            # Check if we have resources for this goal
            cpu_cost = goal.estimated_resources.get('cpu_percent', 10.0)
            time_cost = goal.estimated_resources.get('duration_seconds', 60)

            # Would this exceed our limits?
            if (total_cpu + cpu_cost) > self.config.max_cpu_percent:
                logger.debug(f"Skipping goal due to CPU limit: {goal.description}")
                continue

            if (total_time + time_cost) > 3600:  # Max 1 hour of operations
                logger.debug(f"Skipping goal due to time limit: {goal.description}")
                continue

            # Select this goal
            selected_goals.append(goal)
            total_cpu += cpu_cost
            total_time += time_cost

            # Stop if we have enough goals
            if len(selected_goals) >= 5:  # Max 5 concurrent goals
                break

        return selected_goals

    def analyze_market_gaps(self, market_intelligence: Dict[str, Any]) -> List[MarketGap]:
        """
        Analyze current market state to identify knowledge gaps.

        This method identifies opportunities where autonomous exploration
        would be most valuable.

        Args:
            market_intelligence: Current market conditions

        Returns:
            List of MarketGap objects representing exploration opportunities
        """
        gaps = []

        # Analyze regime gaps
        current_regime = market_intelligence.get('current_regime', {})
        for symbol, regime in current_regime.items():
            if regime.get('confidence', 0) < 0.7:
                gaps.append(MarketGap(
                    gap_type='regime_gap',
                    description=f"Low confidence in {symbol} regime detection",
                    symbol=symbol,
                    timeframe='1h',
                    importance=0.8,
                    difficulty=0.3,
                    estimated_value=0.7,
                    market_conditions={'current_regime': regime}
                ))

        # Analyze volatility gaps
        volatility_level = market_intelligence.get('volatility_level', 'unknown')
        if volatility_level == 'unknown':
            gaps.append(MarketGap(
                gap_type='strategy_gap',
                description="No current volatility analysis - need volatility-based strategies",
                symbol='ALL',
                timeframe='1h',
                importance=0.7,
                difficulty=0.4,
                estimated_value=0.8,
                market_conditions={'volatility_analysis': 'missing'}
            ))

        self.market_gap_cache = gaps
        return gaps