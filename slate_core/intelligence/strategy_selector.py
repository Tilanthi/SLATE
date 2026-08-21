#!/usr/bin/env python3
"""
SLATE Strategy Selection Engine

Intelligently selects which strategies to deploy from the pool of validated discoveries.
Uses multi-criteria optimization to choose optimal strategies for current market conditions.

Key Features:
- Multi-criteria scoring (expected return, Sharpe ratio, regime compatibility, correlation, trend)
- Regime-aware strategy filtering
- Correlation-based diversification
- Portfolio fit analysis
- Statistical validation of selections
"""

import logging
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import sqlite3
from enum import Enum
from slate_core.config.paths import CORE_ROOT

logger = logging.getLogger(__name__)


class SelectionCriteria(Enum):
    """Strategy selection criteria."""
    EXPECTED_RETURN = "expected_return"           # 30% weight
    RISK_ADJUSTED_RETURN = "risk_adjusted_return" # 25% weight (Sharpe ratio)
    REGIME_COMPATIBILITY = "regime_compatibility" # 20% weight
    CORRELATION_DIVERSIFICATION = "correlation_diversification" # 15% weight
    RECENT_PERFORMANCE_TREND = "recent_performance_trend" # 10% weight


@dataclass
class StrategyCandidate:
    """A candidate strategy for selection."""
    strategy_id: str
    strategy_type: str
    timeframe: str
    parameters: Dict[str, Any]
    expected_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    regime_compatibility: Dict[str, float]  # Regime type -> compatibility score
    recent_performance: List[float]  # Last 30 days of returns
    discovery_date: datetime
    validation_score: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'strategy_id': self.strategy_id,
            'strategy_type': self.strategy_type,
            'timeframe': self.timeframe,
            'parameters': self.parameters,
            'expected_return': self.expected_return,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'win_rate': self.win_rate,
            'regime_compatibility': self.regime_compatibility,
            'recent_performance': self.recent_performance,
            'discovery_date': self.discovery_date.isoformat(),
            'validation_score': self.validation_score
        }


@dataclass
class SelectedStrategy:
    """A strategy selected for deployment."""
    strategy: StrategyCandidate
    selection_score: float
    allocation_weight: float  # Suggested allocation weight
    selection_reason: str
    confidence_level: float  # Statistical confidence in selection

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'strategy': self.strategy.to_dict(),
            'selection_score': self.selection_score,
            'allocation_weight': self.allocation_weight,
            'selection_reason': self.selection_reason,
            'confidence_level': self.confidence_level
        }


@dataclass
class PortfolioContext:
    """Context about existing portfolio for selection decisions."""
    existing_strategies: List[str]  # Strategy IDs currently deployed
    current_allocation: Dict[str, float]  # Strategy ID -> current allocation
    portfolio_return: float  # Current portfolio return
    portfolio_volatility: float  # Current portfolio volatility
    current_regime: str  # Current market regime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'existing_strategies': self.existing_strategies,
            'current_allocation': self.current_allocation,
            'portfolio_return': self.portfolio_return,
            'portfolio_volatility': self.portfolio_volatility,
            'current_regime': self.current_regime
        }


class StrategySelector:
    """
    Select optimal strategies for deployment based on multi-criteria analysis.

    Selection Algorithm:
    1. Regime Filtering: Only consider strategies suitable for current regime
    2. Correlation Analysis: Ensure diversification (max correlation 0.7)
    3. Performance Scoring: Multi-criteria ranking with statistical validation
    4. Portfolio Fit: Select strategies that complement existing portfolio
    5. Resource Constraints: Respect computational and capital limits
    """

    def __init__(self,
                 db_path: str = f"{CORE_ROOT}/slate_realistic_discoveries.db",
                 min_sharpe_ratio: float = 0.5,
                 max_correlation: float = 0.7,
                 max_strategies: int = 10):
        """
        Initialize the strategy selector.

        Args:
            db_path: Path to discoveries database
            min_sharpe_ratio: Minimum Sharpe ratio for consideration
            max_correlation: Maximum correlation with existing strategies
            max_strategies: Maximum number of strategies to select
        """
        self.db_path = db_path
        self.min_sharpe_ratio = min_sharpe_ratio
        self.max_correlation = max_correlation
        self.max_strategies = max_strategies

        # Selection criteria weights
        self.criteria_weights = {
            SelectionCriteria.EXPECTED_RETURN: 0.30,
            SelectionCriteria.RISK_ADJUSTED_RETURN: 0.25,
            SelectionCriteria.REGIME_COMPATIBILITY: 0.20,
            SelectionCriteria.CORRELATION_DIVERSIFICATION: 0.15,
            SelectionCriteria.RECENT_PERFORMANCE_TREND: 0.10
        }

        # Statistics
        self.total_selections = 0
        self.strategies_selected = 0
        self.selections_by_regime = {}

        logger.info(f"StrategySelector initialized: max_strategies={max_strategies}, min_sharpe={min_sharpe_ratio}")

    def select_strategies(
        self,
        candidate_strategies: List[StrategyCandidate],
        current_regime: str,
        portfolio_context: PortfolioContext,
        available_capital: float = 10000.0
    ) -> Tuple[List[SelectedStrategy], Dict[str, Any]]:
        """
        Select strategies using weighted multi-criteria optimization.

        Args:
            candidate_strategies: List of candidate strategies
            current_regime: Current market regime
            portfolio_context: Current portfolio state
            available_capital: Available capital for allocation

        Returns:
            Tuple of (selected strategies, selection metadata)
        """
        self.total_selections += 1

        logger.info(f"Starting strategy selection: {len(candidate_strategies)} candidates, regime={current_regime}")

        selection_metadata = {
            'candidates_considered': len(candidate_strategies),
            'current_regime': current_regime,
            'selection_timestamp': datetime.now().isoformat(),
            'filtering_steps': []
        }

        # Step 1: Filter by basic criteria
        filtered_strategies = self._apply_basic_filters(candidate_strategies)
        selection_metadata['filtering_steps'].append({
            'step': 'basic_filters',
            'input': len(candidate_strategies),
            'output': len(filtered_strategies)
        })

        # Step 2: Filter by regime compatibility
        regime_filtered = self._filter_by_regime_compatibility(filtered_strategies, current_regime)
        selection_metadata['filtering_steps'].append({
            'step': 'regime_filter',
            'input': len(filtered_strategies),
            'output': len(regime_filtered)
        })

        # Step 3: Filter by correlation with existing strategies
        correlation_filtered = self._filter_by_correlation(regime_filtered, portfolio_context)
        selection_metadata['filtering_steps'].append({
            'step': 'correlation_filter',
            'input': len(regime_filtered),
            'output': len(correlation_filtered)
        })

        if not correlation_filtered:
            logger.warning("No strategies passed filtering, returning empty selection")
            selection_metadata['no_strategies_reason'] = "All strategies filtered out"
            return [], selection_metadata

        # Step 4: Score strategies using multi-criteria analysis
        scored_strategies = self._score_strategies(correlation_filtered, current_regime, portfolio_context)

        # Step 5: Select top strategies
        selected = self._select_top_strategies(scored_strategies, available_capital)

        # Update statistics
        self.strategies_selected += len(selected)
        self.selections_by_regime[current_regime] = self.selections_by_regime.get(current_regime, 0) + 1

        selection_metadata['strategies_selected'] = len(selected)
        selection_metadata['selection_details'] = [
            {
                'strategy_id': s.strategy.strategy_id,
                'selection_score': s.selection_score,
                'allocation_weight': s.allocation_weight,
                'selection_reason': s.selection_reason
            }
            for s in selected
        ]

        logger.info(f"Strategy selection complete: {len(selected)} strategies selected")

        return selected, selection_metadata

    def _apply_basic_filters(self, strategies: List[StrategyCandidate]) -> List[StrategyCandidate]:
        """Apply basic quality filters."""
        filtered = []

        for strategy in strategies:
            # Must meet minimum Sharpe ratio
            if strategy.sharpe_ratio < self.min_sharpe_ratio:
                continue

            # Must have reasonable validation score (> 60%)
            if strategy.validation_score < 0.6:
                continue

            # Must not have excessive drawdown (> 30%)
            if strategy.max_drawdown > 0.30:
                continue

            filtered.append(strategy)

        logger.debug(f"Basic filters: {len(strategies)} → {len(filtered)} strategies")
        return filtered

    def _filter_by_regime_compatibility(self, strategies: List[StrategyCandidate], current_regime: str) -> List[StrategyCandidate]:
        """Filter strategies by regime compatibility."""
        filtered = []

        for strategy in strategies:
            # Get regime compatibility score
            regime_score = strategy.regime_compatibility.get(current_regime, 0.0)

            # Must have at least 60% compatibility with current regime
            if regime_score >= 0.6:
                filtered.append(strategy)

        logger.debug(f"Regime filter ({current_regime}): {len(strategies)} → {len(filtered)} strategies")
        return filtered

    def _filter_by_correlation(self, strategies: List[StrategyCandidate], portfolio_context: PortfolioContext) -> List[StrategyCandidate]:
        """Filter strategies by correlation with existing portfolio."""
        if not portfolio_context.existing_strategies:
            # No existing strategies, return all candidates
            return strategies

        filtered = []

        for strategy in strategies:
            # Check correlation with each existing strategy
            max_correlation = 0.0

            for existing_id in portfolio_context.existing_strategies:
                correlation = self._calculate_strategy_correlation(strategy.strategy_id, existing_id)
                max_correlation = max(max_correlation, correlation)

            # Only add if not too correlated with existing strategies
            if max_correlation < self.max_correlation:
                filtered.append(strategy)

        logger.debug(f"Correlation filter: {len(strategies)} → {len(filtered)} strategies")
        return filtered

    def _score_strategies(
        self,
        strategies: List[StrategyCandidate],
        current_regime: str,
        portfolio_context: PortfolioContext
    ) -> List[Tuple[StrategyCandidate, float, str]]:
        """
        Score strategies using multi-criteria analysis.

        Returns:
            List of (strategy, score, reason) tuples
        """
        scored_strategies = []

        for strategy in strategies:
            # Calculate individual criterion scores
            scores = {}

            # 1. Expected Return (normalized to 0-1)
            scores[SelectionCriteria.EXPECTED_RETURN] = self._normalize_return(strategy.expected_return)

            # 2. Risk-Adjusted Return (Sharpe ratio)
            scores[SelectionCriteria.RISK_ADJUSTED_RETURN] = self._normalize_sharpe(strategy.sharpe_ratio)

            # 3. Regime Compatibility
            scores[SelectionCriteria.REGIME_COMPATIBILITY] = strategy.regime_compatibility.get(current_regime, 0.0)

            # 4. Correlation Diversification (inverse of correlation)
            diversification_score = self._calculate_diversification_score(strategy, portfolio_context)
            scores[SelectionCriteria.CORRELATION_DIVERSIFICATION] = diversification_score

            # 5. Recent Performance Trend
            trend_score = self._calculate_performance_trend(strategy.recent_performance)
            scores[SelectionCriteria.RECENT_PERFORMANCE_TREND] = trend_score

            # Calculate weighted total score
            total_score = sum(
                scores[criterion] * self.criteria_weights[criterion]
                for criterion in SelectionCriteria
            )

            # Generate selection reason
            top_criteria = max(scores.items(), key=lambda x: x[1])
            reason = f"Selected based on {top_criteria[0].value} (score: {top_criteria[1]:.2f})"

            scored_strategies.append((strategy, total_score, reason))

        # Sort by score (descending)
        scored_strategies.sort(key=lambda x: x[1], reverse=True)

        return scored_strategies

    def _normalize_return(self, return_pct: float) -> float:
        """Normalize return to 0-1 scale (assuming 0-50% annual return range)."""
        # Use sigmoid function for smooth normalization
        max_return = 50.0  # 50% annual return
        normalized = return_pct / max_return
        return min(max(normalized, 0.0), 1.0)

    def _normalize_sharpe(self, sharpe_ratio: float) -> float:
        """Normalize Sharpe ratio to 0-1 scale (assuming 0-5 range)."""
        max_sharpe = 5.0
        normalized = sharpe_ratio / max_sharpe
        return min(max(normalized, 0.0), 1.0)

    def _calculate_diversification_score(self, strategy: StrategyCandidate, portfolio_context: PortfolioContext) -> float:
        """Calculate diversification score (inverse of correlation with existing strategies)."""
        if not portfolio_context.existing_strategies:
            # No existing strategies, maximum diversification benefit
            return 1.0

        # Calculate average correlation with existing strategies
        correlations = []
        for existing_id in portfolio_context.existing_strategies:
            correlation = self._calculate_strategy_correlation(strategy.strategy_id, existing_id)
            correlations.append(correlation)

        avg_correlation = np.mean(correlations) if correlations else 0.0

        # Diversification score is inverse of correlation
        diversification_score = 1.0 - avg_correlation
        return max(diversification_score, 0.0)

    def _calculate_strategy_correlation(self, strategy_id_1: str, strategy_id_2: str) -> float:
        """Calculate correlation between two strategies (simplified estimate)."""
        # In real implementation, this would use historical returns data
        # For now, use strategy type and timeframe as correlation proxy

        # Extract strategy types and timeframes
        type_1 = strategy_id_1.split('_')[0] if '_' in strategy_id_1 else strategy_id_1
        type_2 = strategy_id_2.split('_')[0] if '_' in strategy_id_2 else strategy_id_2

        # Same strategy type = higher correlation
        if type_1 == type_2:
            return 0.8
        else:
            # Different strategies = lower correlation
            return 0.3

    def _calculate_performance_trend(self, recent_performance: List[float]) -> float:
        """Calculate performance trend score from recent returns."""
        if not recent_performance or len(recent_performance) < 2:
            return 0.5  # Neutral score if no data

        # Calculate linear trend (positive = improving, negative = declining)
        returns = np.array(recent_performance)
        x = np.arange(len(returns))

        # Simple linear regression
        if len(returns) > 1:
            slope = np.polyfit(x, returns, 1)[0]
            # Normalize slope: assume -2% to +2% daily range
            normalized_slope = (slope + 0.02) / 0.04
            return min(max(normalized_slope, 0.0), 1.0)
        else:
            return 0.5

    def _select_top_strategies(
        self,
        scored_strategies: List[Tuple[StrategyCandidate, float, str]],
        available_capital: float
    ) -> List[SelectedStrategy]:
        """Select top strategies and calculate allocation weights."""
        if not scored_strategies:
            return []

        # Select top N strategies
        top_strategies = scored_strategies[:self.max_strategies]

        # Calculate allocation weights using softmax of scores
        scores = np.array([score for _, score, _ in top_strategies])

        # Use softmax for smooth allocation
        exp_scores = np.exp(scores - np.max(scores))  # Subtract max for numerical stability
        softmax_weights = exp_scores / np.sum(exp_scores)

        # Create SelectedStrategy objects
        selected = []
        for (strategy, score, reason), weight in zip(top_strategies, softmax_weights):
            # Calculate statistical confidence using bootstrap validation
            confidence = self._calculate_selection_confidence(strategy, score)

            selected_strategy = SelectedStrategy(
                strategy=strategy,
                selection_score=score,
                allocation_weight=float(weight),
                selection_reason=reason,
                confidence_level=confidence
            )
            selected.append(selected_strategy)

        return selected

    def _calculate_selection_confidence(self, strategy: StrategyCandidate, selection_score: float) -> float:
        """Calculate statistical confidence in selection using bootstrap validation."""
        # In real implementation, this would use bootstrap resampling
        # For now, use validation score and recency as confidence proxy

        # Base confidence from validation score
        base_confidence = strategy.validation_score

        # Adjust for recency (strategies discovered more recently are less proven)
        days_since_discovery = (datetime.now() - strategy.discovery_date).days
        recency_adjustment = max(0.0, 1.0 - (days_since_discovery / 365.0))

        # Combine factors
        confidence = base_confidence * 0.7 + recency_adjustment * 0.3

        return min(max(confidence, 0.0), 1.0)

    def load_candidate_strategies_from_db(self, limit: int = 100) -> List[StrategyCandidate]:
        """Load candidate strategies from discoveries database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Query recent validated strategies
            cursor.execute("""
                SELECT
                    edge_description,
                    total_return_pct,
                    sharpe_ratio,
                    max_drawdown_pct,
                    win_rate,
                    timestamp,
                    passed_validation,
                    timeframe
                FROM edge_discoveries
                WHERE passed_validation = 1
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))

            strategies = []
            for row in cursor.fetchall():
                # Parse strategy information from edge_description
                edge_desc = row[0]

                # Extract timeframe from row data (if available) or parse from description
                timeframe = row[7] if len(row) > 7 and row[7] else '1d'  # Use timeframe from column if available

                # If timeframe not in row, try to parse from description
                if timeframe == '1d' and '[' in edge_desc and ']' in edge_desc:
                    timeframe = edge_desc[edge_desc.index('[')+1:edge_desc.index(']')]

                # Determine strategy type from description keywords
                strategy_type = 'momentum_mean_reversion'  # Default
                if 'mean_reversion' in edge_desc.lower():
                    strategy_type = 'mean_reversion'
                elif 'momentum' in edge_desc.lower():
                    strategy_type = 'momentum'
                elif 'breakout' in edge_desc.lower():
                    strategy_type = 'breakout'

                # Parse timestamp
                try:
                    discovery_date = datetime.fromisoformat(row[5])
                except (ValueError, TypeError):
                    discovery_date = datetime.now()  # Fallback to current time

                # Estimate validation score from available metrics
                # Use Sharpe ratio and win rate as validation proxy
                sharpe_ratio = row[2]
                win_rate = row[4]
                estimated_validation_score = min(0.9, 0.5 + (sharpe_ratio * 0.1) + ((win_rate - 0.5) * 0.5))

                # Create strategy candidate
                candidate = StrategyCandidate(
                    strategy_id=f"{strategy_type}_{timeframe}_{int(row[1]*100)}",  # type_timeframe_return
                    strategy_type=strategy_type,
                    timeframe=timeframe,
                    parameters={},  # Would be parsed from full strategy details
                    expected_return=row[1],  # total_return_pct
                    sharpe_ratio=row[2],
                    max_drawdown=abs(row[3]) / 100.0,  # Convert pct to decimal
                    win_rate=row[4],
                    regime_compatibility=self._estimate_regime_compatibility(strategy_type, timeframe),
                    recent_performance=[],  # Would be loaded from performance history
                    discovery_date=discovery_date,
                    validation_score=estimated_validation_score
                )
                strategies.append(candidate)

            conn.close()
            logger.info(f"Loaded {len(strategies)} candidate strategies from database")
            return strategies

        except Exception as e:
            logger.error(f"Error loading candidate strategies: {e}")
            return []

    def _estimate_regime_compatibility(self, strategy_type: str, timeframe: str) -> Dict[str, float]:
        """Estimate regime compatibility based on strategy characteristics."""
        # Simplified regime compatibility estimation
        # In real implementation, this would be based on historical performance analysis

        compatibility = {
            'TRENDING_UP': 0.7,
            'TRENDING_DOWN': 0.7,
            'SIDEWAYS': 0.6,
            'HIGH_VOLATILITY': 0.5,
            'LOW_VOLATILITY': 0.6,
            'LIQUIDITY_CRUNCH': 0.4,
            'LIQUIDITY_ABUNDANT': 0.6
        }

        # Adjust based on strategy type
        if 'momentum' in strategy_type.lower():
            compatibility['TRENDING_UP'] = 0.9
            compatibility['TRENDING_DOWN'] = 0.9
            compatibility['SIDEWAYS'] = 0.3
        elif 'reversion' in strategy_type.lower():
            compatibility['SIDEWAYS'] = 0.9
            compatibility['TRENDING_UP'] = 0.4
            compatibility['TRENDING_DOWN'] = 0.4

        # Adjust based on timeframe (daily strategies more robust across regimes)
        if timeframe == '1d':
            for regime in compatibility:
                compatibility[regime] = min(compatibility[regime] + 0.1, 1.0)

        return compatibility

    def get_selection_stats(self) -> Dict[str, Any]:
        """Get selection statistics."""
        return {
            'total_selections': self.total_selections,
            'strategies_selected': self.strategies_selected,
            'avg_strategies_per_selection': self.strategies_selected / self.total_selections if self.total_selections > 0 else 0,
            'selections_by_regime': self.selections_by_regime,
            'selection_criteria_weights': {
                criterion.value: weight for criterion, weight in self.criteria_weights.items()
            },
            'max_correlation': self.max_correlation,
            'min_sharpe_ratio': self.min_sharpe_ratio
        }


# Global selector instance
_strategy_selector: Optional[StrategySelector] = None


def get_strategy_selector(db_path: str = f"{CORE_ROOT}/slate_realistic_discoveries.db") -> StrategySelector:
    """Get global strategy selector instance."""
    global _strategy_selector
    if _strategy_selector is None:
        _strategy_selector = StrategySelector(db_path=db_path)
    return _strategy_selector


if __name__ == "__main__":
    # Test the strategy selector
    print("Testing Strategy Selector...")

    selector = get_strategy_selector()

    # Load candidate strategies
    candidates = selector.load_candidate_strategies_from_db(20)
    print(f"Loaded {len(candidates)} candidate strategies")

    if candidates:
        # Create portfolio context
        portfolio_context = PortfolioContext(
            existing_strategies=[],
            current_allocation={},
            portfolio_return=0.0,
            portfolio_volatility=0.0,
            current_regime='TRENDING_UP'
        )

        # Select strategies
        selected, metadata = selector.select_strategies(
            candidates,
            'TRENDING_UP',
            portfolio_context,
            available_capital=10000.0
        )

        print(f"\nSelected {len(selected)} strategies:")
        for i, strategy in enumerate(selected, 1):
            print(f"\n{i}. {strategy.strategy.strategy_id}")
            print(f"   Selection Score: {strategy.selection_score:.3f}")
            print(f"   Allocation Weight: {strategy.allocation_weight:.1%}")
            print(f"   Confidence: {strategy.confidence_level:.1%}")
            print(f"   Reason: {strategy.selection_reason}")

        print(f"\nSelection Statistics:")
        stats = selector.get_selection_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")