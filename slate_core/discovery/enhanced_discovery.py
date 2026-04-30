#!/usr/bin/env python3
"""
SLATE Enhanced Discovery System

Integrates all advanced discovery modules into a unified system:
- Ensemble strategies combining multiple approaches
- Walk-forward validation to prevent overfitting
- Regime-aware strategy selection
- Portfolio-level risk management
- Technical feature engineering
- Online learning for parameter adaptation
- Multi-objective optimization using Pareto frontiers
- Advanced backtesting with realistic execution simulation
"""

import asyncio
import logging
import random
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import numpy as np

# Import existing discovery system
try:
    from .realistic_backtester import (
        ContinuousDiscoverySystem,
        BacktestResult,
        BacktestConfig,
        HistoricalDataArchive,
        RealisticBacktester
    )
except ImportError:
    logger.warning("Could not import from realistic_backtester")
    ContinuousDiscoverySystem = None

# Import new enhancement modules
try:
    from .ensemble_strategies import (
        EnsembleStrategy,
        EnsembleGenerator,
        EnsembleMember
    )
except ImportError:
    logger.warning("Ensemble strategies module not available")
    EnsembleStrategy = None

try:
    from .walk_forward import (
        WalkForwardValidator,
        WalkForwardConfig,
        WalkForwardResult
    )
except ImportError:
    logger.warning("Walk-forward validation module not available")
    WalkForwardValidator = None

try:
    from .regime_aware import (
        RegimeDetector,
        RegimeAwareStrategySelector,
        MarketRegime
    )
except ImportError:
    logger.warning("Regime-aware selection module not available")
    RegimeDetector = None

try:
    from .portfolio_risk import (
        PortfolioRiskManager,
        Position,
        RiskMetrics,
        RiskLimit
    )
except ImportError:
    logger.warning("Portfolio risk management module not available")
    PortfolioRiskManager = None

try:
    from .technical_features import (
        FeatureEngineering,
        TechnicalFeatures,
        FeatureSelector
    )
except ImportError:
    logger.warning("Technical features module not available")
    FeatureEngineering = None

try:
    from .online_learning import (
        OnlineLearner,
        AdaptiveOptimizer,
        PerformanceSnapshot
    )
except ImportError:
    logger.warning("Online learning module not available")
    OnlineLearner = None

try:
    from .multi_objective import (
        MultiObjectiveOptimizer,
        ParetoSolution,
        PreferenceManager
    )
except ImportError:
    logger.warning("Multi-objective optimization module not available")
    MultiObjectiveOptimizer = None

try:
    from .advanced_backtest import (
        AdvancedBacktestSimulator,
        AdvancedSlippageCalculator,
        AdvancedFillModel,
        MarketImpactCalculator,
        OrderBookSimulator
    )
except ImportError:
    logger.warning("Advanced backtest module not available")
    AdvancedBacktestSimulator = None

logger = logging.getLogger(__name__)


@dataclass
class EnhancedDiscoveryConfig:
    """Configuration for enhanced discovery system."""
    # Base discovery settings
    cycles: int = 100
    workers: int = 10

    # Ensemble settings
    enable_ensembles: bool = True
    max_ensemble_size: int = 5
    min_diversity_score: float = 0.3

    # Walk-forward validation settings
    enable_walk_forward: bool = True
    wf_train_periods: int = 3
    wf_test_periods: int = 1
    wf_min_stability_score: float = 0.6

    # Regime-aware settings
    enable_regime_aware: bool = True
    regime_detection_window: int = 100

    # Portfolio risk settings
    enable_portfolio_risk: bool = True
    max_portfolio_var: float = 0.02
    max_correlation: float = 0.7
    max_concentration: float = 0.4

    # Technical features settings
    enable_feature_engineering: bool = True
    feature_lookback: int = 50

    # Online learning settings
    enable_online_learning: bool = True
    learning_rate: float = 0.01
    adaptation_threshold: float = 0.5

    # Multi-objective settings
    enable_multi_objective: bool = True
    objective_weights: Optional[Dict[str, float]] = None

    # Advanced backtesting settings
    enable_advanced_backtest: bool = True
    slippage_model: str = 'volume_dependent'
    fill_model: str = 'probability_based'


class EnhancedDiscoverySystem:
    """
    Enhanced discovery system with all advanced modules integrated.

    This system extends the base ContinuousDiscoverySystem with:
    1. Ensemble generation and optimization
    2. Walk-forward validation for robustness
    3. Regime-aware strategy selection
    4. Portfolio-level risk management
    5. Technical feature engineering
    6. Online learning and adaptation
    7. Multi-objective optimization
    8. Advanced backtesting simulation
    """

    def __init__(self, config: EnhancedDiscoveryConfig = None):
        """Initialize enhanced discovery system."""
        self.config = config or EnhancedDiscoveryConfig()

        # Initialize base discovery system
        if ContinuousDiscoverySystem:
            self.base_system = ContinuousDiscoverySystem(
                use_multipath=True,
                num_paths=50,
                multipath_sample_rate=0.2
            )
        else:
            self.base_system = None
            logger.warning("Base discovery system not available")

        # Initialize enhancement modules
        self._init_enhancement_modules()

        # Tracking
        self.discovery_stats = {
            'total_strategies_tested': 0,
            'ensembles_created': 0,
            'walk_forward_validations': 0,
            'regime_transitions': 0,
            'risk_adjustments': 0,
            'parameter_adaptations': 0,
            'start_time': datetime.now().isoformat()
        }

        logger.info("Enhanced Discovery System initialized")

    def _init_enhancement_modules(self):
        """Initialize all enhancement modules."""
        # Ensemble system
        if self.config.enable_ensembles and EnsembleGenerator:
            self.ensemble_generator = EnsembleGenerator(
                max_size=self.config.max_ensemble_size,
                min_diversity=self.config.min_diversity_score
            )
            logger.info("Ensemble generator initialized")
        else:
            self.ensemble_generator = None

        # Walk-forward validator
        if self.config.enable_walk_forward and WalkForwardValidator:
            self.walk_forward_validator = WalkForwardValidator(
                config=WalkForwardConfig(
                    train_periods=self.config.wf_train_periods,
                    test_periods=self.config.wf_test_periods,
                    min_stability_score=self.config.wf_min_stability_score
                )
            )
            logger.info("Walk-forward validator initialized")
        else:
            self.walk_forward_validator = None

        # Regime detector
        if self.config.enable_regime_aware and RegimeDetector:
            self.regime_detector = RegimeDetector(
                detection_window=self.config.regime_detection_window
            )
            self.regime_selector = RegimeAwareStrategySelector()
            logger.info("Regime-aware selector initialized")
        else:
            self.regime_detector = None
            self.regime_selector = None

        # Portfolio risk manager
        if self.config.enable_portfolio_risk and PortfolioRiskManager:
            self.risk_manager = PortfolioRiskManager(
                initial_capital=10000.0
            )
            self.risk_manager.risk_limits = RiskLimit(
                max_portfolio_var=self.config.max_portfolio_var,
                max_correlation_exposure=self.config.max_correlation,
                max_concentration_ratio=self.config.max_concentration
            )
            logger.info("Portfolio risk manager initialized")
        else:
            self.risk_manager = None

        # Feature engineering
        if self.config.enable_feature_engineering and FeatureEngineering:
            self.feature_engineering = FeatureEngineering()
            self.feature_selector = FeatureSelector()
            logger.info("Feature engineering initialized")
        else:
            self.feature_engineering = None

        # Online learning
        if self.config.enable_online_learning and AdaptiveOptimizer:
            self.online_optimizer = AdaptiveOptimizer()
            logger.info("Online learning optimizer initialized")
        else:
            self.online_optimizer = None

        # Multi-objective optimizer
        if self.config.enable_multi_objective and MultiObjectiveOptimizer:
            self.multi_objective = MultiObjectiveOptimizer()
            if self.config.objective_weights:
                self.multi_objective.objectives.update(self.config.objective_weights)
            logger.info("Multi-objective optimizer initialized")
        else:
            self.multi_objective = None

        # Advanced backtest simulator
        if self.config.enable_advanced_backtest and AdvancedBacktestSimulator:
            self.advanced_backtester = AdvancedBacktestSimulator()
            logger.info("Advanced backtest simulator initialized")
        else:
            self.advanced_backtester = None

    async def discover_strategies(
        self,
        cycles: Optional[int] = None,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Run enhanced discovery with all modules integrated.

        Args:
            cycles: Number of discovery cycles (overrides config)
            progress_callback: Optional callback for progress updates

        Returns:
            Discovery results with statistics
        """
        cycles = cycles or self.config.cycles
        logger.info(f"Starting enhanced discovery: {cycles} cycles")

        results = {
            'strategies': [],
            'ensembles': [],
            'validated_strategies': [],
            'pareto_optimal': [],
            'adapted_strategies': [],
            'statistics': self.discovery_stats.copy()
        }

        for cycle in range(cycles):
            cycle_start = datetime.now()

            # Update progress
            if progress_callback:
                await progress_callback({
                    'cycle': cycle + 1,
                    'total_cycles': cycles,
                    'progress': (cycle / cycles) * 100
                })

            # Detect current market regime
            current_regime = await self._detect_regime()

            # Generate and test strategies
            cycle_strategies = await self._generate_and_test_strategies(cycle, current_regime)

            # Apply walk-forward validation
            validated_strategies = await self._apply_walk_forward_validation(
                cycle_strategies, current_regime
            )

            # Generate ensembles from validated strategies
            ensembles = await self._generate_ensembles(validated_strategies)

            # Apply multi-objective optimization
            pareto_optimal = await self._apply_multi_objective_optimization(
                validated_strategies + ensembles
            )

            # Apply online learning for parameter adaptation
            adapted_strategies = await self._apply_online_learning(
                pareto_optimal, current_regime
            )

            # Portfolio risk checks
            await self._apply_portfolio_risk_checks(adapted_strategies)

            # Collect results
            results['strategies'].extend(cycle_strategies)
            results['ensembles'].extend(ensembles)
            results['validated_strategies'].extend(validated_strategies)
            results['pareto_optimal'].extend(pareto_optimal)
            results['adapted_strategies'].extend(adapted_strategies)

            # Update statistics
            self.discovery_stats['total_strategies_tested'] += len(cycle_strategies)
            self.discovery_stats['ensembles_created'] += len(ensembles)
            self.discovery_stats['walk_forward_validations'] += len(validated_strategies)

            cycle_duration = (datetime.now() - cycle_start).total_seconds()
            logger.info(
                f"Cycle {cycle + 1}/{cycles} completed in {cycle_duration:.2f}s: "
                f"{len(cycle_strategies)} strategies, "
                f"{len(ensembles)} ensembles, "
                f"{len(pareto_optimal)} Pareto-optimal"
            )

        results['statistics'] = self.discovery_stats.copy()
        results['statistics']['end_time'] = datetime.now().isoformat()

        logger.info("Enhanced discovery completed")
        return results

    async def _detect_regime(self) -> str:
        """Detect current market regime."""
        if self.regime_detector:
            # Use base system to get recent data
            if self.base_system and self.base_system.historical_archive:
                data = await self.base_system.historical_archive.get_test_data(
                    symbol='BTCUSDT',
                    timeframe='1h'
                )
                if data:
                    regime = await self.regime_detector.detect_regime(data)
                    self.discovery_stats['regime_transitions'] += 1
                    return regime.value if hasattr(regime, 'value') else regime
        return 'unknown'

    async def _generate_and_test_strategies(
        self,
        cycle: int,
        current_regime: str
    ) -> List[Dict]:
        """Generate and test strategies for this cycle."""
        if not self.base_system:
            return []

        # Generate strategies using base system
        workers = min(self.config.workers, self.base_system.workers)

        # Use regime-aware generation if available
        if self.regime_selector and current_regime != 'unknown':
            # Generate strategies suited for current regime
            strategy_types = self.regime_selector.get_strategies_for_regime(current_regime)
            logger.info(f"Generating strategies for regime: {current_regime}")
        else:
            strategy_types = None

        # Generate strategies (using base system's generator)
        from .realistic_backtester import StrategyGenerator
        generator = StrategyGenerator()

        strategies = generator.generate_adaptive_strategies(
            count=workers,
            preferred_types=strategy_types
        )

        # Test strategies
        tasks = []
        for strategy in strategies:
            task = self.base_system.backtester.run_backtest(
                strategy,
                symbol=strategy.get('symbol', 'BTCUSDT'),
                timeframe=strategy.get('timeframe', '1m')
            )
            tasks.append((strategy, task))

        # Run tests and collect results
        results = []
        completed = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)

        for i, (strategy, task_result) in enumerate(zip(strategies, completed)):
            if isinstance(task_result, BacktestResult):
                # Enhance with technical features if available
                if self.feature_engineering and self.advanced_backtester:
                    # Add advanced execution metrics
                    strategy_with_features = await self._add_technical_features(
                        strategy, task_result
                    )
                    results.append(strategy_with_features)
                else:
                    results.append(strategy)

                # Store regime information
                if self.regime_selector:
                    results[-1]['suitable_regimes'] = (
                        self.regime_selector.get_suitable_regimes(strategy)
                    )

        return results

    async def _add_technical_features(
        self,
        strategy: Dict,
        backtest_result: BacktestResult
    ) -> Dict:
        """Add technical features and advanced metrics to strategy."""
        enhanced_strategy = strategy.copy()

        # Calculate technical features from backtest data
        if backtest_result.trades and len(backtest_result.trades) > 0:
            # Create feature data from trades
            feature_data = []
            for trade in backtest_result.trades[-self.config.feature_lookback:]:
                feature_data.append({
                    'close': trade.get('exit_price', trade.get('price', 0)),
                    'high': trade.get('high', trade.get('price', 0)),
                    'low': trade.get('low', trade.get('price', 0)),
                    'volume': trade.get('size', 1.0)
                })

            if feature_data:
                features = self.feature_engineering.calculate_features(feature_data)

                # Add feature-based recommendations
                enhanced_strategy['technical_features'] = {
                    'roc_5': features.roc_5,
                    'rsi_14': features.rsi_14,
                    'atr_ratio': features.atr_ratio,
                    'volatility_regime': features.volatility_regime,
                    'trend_direction': features.trend_direction,
                    'trend_strength': features.trend_strength
                }

                # Select most relevant features for strategy type
                selected_features = self.feature_selector.select_features(
                    features,
                    strategy.get('type', 'momentum')
                )
                enhanced_strategy['selected_features'] = selected_features

        return enhanced_strategy

    async def _apply_walk_forward_validation(
        self,
        strategies: List[Dict],
        current_regime: str
    ) -> List[Dict]:
        """Apply walk-forward validation to filter robust strategies."""
        if not self.walk_forward_validator:
            return strategies

        validated = []

        for strategy in strategies:
            # Get historical data for validation
            if self.base_system and self.base_system.historical_archive:
                data = await self.base_system.historical_archive.load_data(
                    symbol=strategy.get('symbol', 'BTCUSDT'),
                    timeframe=strategy.get('timeframe', '1m')
                )

                if data and len(data) > 1000:
                    # Run walk-forward validation
                    wf_result = await self.walk_forward_validator.validate_walk_forward(
                        strategy,
                        data
                    )

                    if wf_result.is_valid:
                        # Store validation metrics
                        strategy['walk_forward_result'] = {
                            'stability_score': wf_result.stability_score,
                            'avg_sharpe': wf_result.avg_test_sharpe,
                            'avg_return': wf_result.avg_test_return,
                            'validation_periods': wf_result.validation_periods
                        }
                        validated.append(strategy)
                        self.discovery_stats['walk_forward_validations'] += 1
                    else:
                        logger.debug(
                            f"Strategy {strategy.get('name')} failed walk-forward: "
                            f"stability={wf_result.stability_score:.2f}"
                        )
                else:
                    # Not enough data, skip validation
                    validated.append(strategy)

        return validated if validated else strategies

    async def _generate_ensembles(
        self,
        strategies: List[Dict]
    ) -> List[Dict]:
        """Generate ensemble strategies from individual strategies."""
        if not self.ensemble_generator or len(strategies) < 2:
            return []

        ensembles = []

        # Generate multiple ensemble configurations
        num_ensembles = min(5, len(strategies) // 2)

        for i in range(num_ensembles):
            # Select diverse strategies
            ensemble = await self.ensemble_generator.generate_diverse_ensemble(
                strategies,
                target_size=min(self.config.max_ensemble_size, len(strategies))
            )

            if ensemble and ensemble.members:
                # Calculate ensemble performance
                performance = await self.ensemble_generator.evaluate_ensemble(
                    ensemble,
                    strategies
                )

                if performance:
                    ensemble_dict = {
                        'id': f"ensemble_{datetime.now().timestamp()}_{i}",
                        'name': f"Ensemble_{i}",
                        'type': 'ensemble',
                        'members': [
                            {
                                'strategy_id': m.strategy_id,
                                'weight': m.weight,
                                'correlation': m.correlation_score
                            }
                            for m in ensemble.members
                        ],
                        'performance': performance,
                        'diversity_score': ensemble.diversity_score,
                        'regime': 'all'  # Ensembles work across regimes
                    }
                    ensembles.append(ensemble_dict)
                    self.discovery_stats['ensembles_created'] += 1

        return ensembles

    async def _apply_multi_objective_optimization(
        self,
        strategies: List[Dict]
    ) -> List[Dict]:
        """Apply multi-objective optimization to find Pareto-optimal strategies."""
        if not self.multi_objective or len(strategies) < 2:
            return strategies

        # Run multi-objective optimization
        pareto_solutions = self.multi_objective.optimize(strategies)

        if not pareto_solutions:
            return strategies

        # Select best solution based on default preferences
        try:
            best_solution = self.multi_objective.select_best_solution(pareto_solutions)
            logger.info(
                f"Best Pareto solution: {best_solution.strategy_name} "
                f"utility={self.multi_objective.calculate_utility_score(best_solution):.2f}"
            )
        except ValueError:
            best_solution = None

        # Mark Pareto-optimal strategies
        pareto_optimal_ids = {s.strategy_id for s in pareto_solutions}

        result = []
        for strategy in strategies:
            strategy_copy = strategy.copy()
            strategy_copy['is_pareto_optimal'] = strategy.get('id') in pareto_optimal_ids

            if strategy_copy['is_pareto_optimal']:
                # Add Pareto metrics
                for solution in pareto_solutions:
                    if solution.strategy_id == strategy.get('id'):
                        strategy_copy['pareto_rank'] = solution.pareto_rank
                        strategy_copy['utility_score'] = (
                            self.multi_objective.calculate_utility_score(solution)
                        )
                        break

            result.append(strategy_copy)

        # Get Pareto frontier summary
        frontier_summary = self.multi_objective.get_pareto_frontier_summary(pareto_solutions)
        logger.info(
            f"Pareto frontier: {frontier_summary['frontier_size']} strategies, "
            f"diversity spread={frontier_summary['diversity']['spread']:.2f}"
        )

        return result

    async def _apply_online_learning(
        self,
        strategies: List[Dict],
        current_regime: str
    ) -> List[Dict]:
        """Apply online learning for parameter adaptation."""
        if not self.online_optimizer:
            return strategies

        adapted = []

        for strategy in strategies:
            # Simulate recent performance for adaptation
            recent_performance = {
                'sharpe_ratio': strategy.get('performance', {}).get('sharpe_ratio', 0),
                'total_return': strategy.get('performance', {}).get('total_return', 0),
                'win_rate': strategy.get('performance', {}).get('win_rate', 0.5),
                'recent_returns': strategy.get('performance', {}).get('returns', [])
            }

            # Try to adapt parameters
            adapted_strategy = await self.online_optimizer.optimize_and_adapt(
                strategy,
                [{'sharpe_ratio': recent_performance['sharpe_ratio']}],  # Simplified
                current_regime
            )

            if adapted_strategy:
                adapted_strategy['adapted'] = True
                adapted_strategy['adaptation_count'] = (
                    adapted_strategy.get('adaptation_count', 0) + 1
                )
                adapted.append(adapted_strategy)
                self.discovery_stats['parameter_adaptations'] += 1
            else:
                adapted.append(strategy)

        return adapted

    async def _apply_portfolio_risk_checks(self, strategies: List[Dict]):
        """Apply portfolio risk management checks."""
        if not self.risk_manager:
            return

        # Check if strategies would fit within risk limits
        for strategy in strategies:
            # Simulate position size
            current_price = strategy.get('performance', {}).get('avg_entry_price', 1000)
            portfolio_value = 10000.0  # Default portfolio value

            suggested_size = self.risk_manager.suggest_position_size(
                strategy,
                current_price,
                portfolio_value
            )

            strategy['recommended_position_size'] = suggested_size

            # Check risk metrics
            is_safe, violations = await self.risk_manager.monitor_and_rebalance()

            if not is_safe:
                strategy['risk_warnings'] = violations
                self.discovery_stats['risk_adjustments'] += 1
            else:
                strategy['risk_warnings'] = []

    async def get_discovery_summary(self) -> Dict[str, Any]:
        """Get summary of discovery results."""
        return {
            'statistics': self.discovery_stats.copy(),
            'modules_enabled': {
                'ensembles': self.ensemble_generator is not None,
                'walk_forward': self.walk_forward_validator is not None,
                'regime_aware': self.regime_detector is not None,
                'portfolio_risk': self.risk_manager is not None,
                'feature_engineering': self.feature_engineering is not None,
                'online_learning': self.online_optimizer is not None,
                'multi_objective': self.multi_objective is not None,
                'advanced_backtest': self.advanced_backtester is not None
            },
            'config': {
                'cycles': self.config.cycles,
                'workers': self.config.workers,
                'enable_ensembles': self.config.enable_ensembles,
                'enable_walk_forward': self.config.enable_walk_forward,
                'enable_regime_aware': self.config.enable_regime_aware,
                'enable_portfolio_risk': self.config.enable_portfolio_risk,
                'enable_feature_engineering': self.config.enable_feature_engineering,
                'enable_online_learning': self.config.enable_online_learning,
                'enable_multi_objective': self.config.enable_multi_objective,
                'enable_advanced_backtest': self.config.enable_advanced_backtest
            }
        }


# Global instance
_enhanced_discovery_system = None


def get_enhanced_discovery_system(config: EnhancedDiscoveryConfig = None) -> EnhancedDiscoverySystem:
    """Get the global enhanced discovery system instance."""
    global _enhanced_discovery_system
    if _enhanced_discovery_system is None:
        _enhanced_discovery_system = EnhancedDiscoverySystem(config)
    return _enhanced_discovery_system
