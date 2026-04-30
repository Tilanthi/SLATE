#!/usr/bin/env python3
"""
SLATE Autonomous Discovery Engine

Integrated Phase 1 + Phase 2 System

This is the main discovery engine that combines:
- Phase 1: Market Regime Detection
- Phase 2: ML Strategy Discovery, Genetic Optimization, Ensemble Methods

This is SLATE's autonomous alpha discovery system.

Author: SLATE Evolution
Date: 2026-04-30
Status: OPERATIONAL
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

# Import Phase 1 components
from .market_regime_detector import get_market_intelligence, MarketRegime
from .regime_adaptive_discovery import get_regime_adaptive_generator

# Import Phase 2 components
from .ml_strategy_discovery import get_ml_discovery, MLModelType
from .genetic_optimizer import get_genetic_optimizer
from .ensemble_discovery import get_ensemble_discovery, EnsembleMethod

logger = logging.getLogger(__name__)


class DiscoveryMode(Enum):
    """Discovery modes."""
    EXPLORATORY = "exploratory"  # Broad search for edges
    OPTIMIZATION = "optimization"  # Optimize existing strategies
    ENSEMBLE = "ensemble"  # Build ensemble portfolios
    ADAPTIVE = "adaptive"  # Regime-adaptive discovery


@dataclass
class DiscoveryResult:
    """Results from autonomous discovery cycle."""
    cycle_id: str
    timestamp: datetime
    mode: DiscoveryMode
    symbol: str

    # Market Intelligence
    regime: MarketRegime
    regime_confidence: float

    # ML Discovery
    ml_strategies_found: int
    best_ml_profit: float
    best_ml_sharpe: float

    # Genetic Optimization
    ga_strategies_found: int
    best_ga_profit: float
    best_ga_drawdown: float

    # Ensemble
    ensemble_created: bool
    ensemble_profit: float
    ensemble_diversification: float

    # Overall
    total_strategies: int
    profitable_strategies: int
    best_overall_strategy: Dict[str, Any]
    recommended_action: str


class AutonomousDiscoveryEngine:
    """
    SLATE's Autonomous Discovery Engine.

    Coordinates all discovery components:
    - Market regime detection (Phase 1)
    - ML strategy discovery (Phase 2)
    - Genetic optimization (Phase 2)
    - Ensemble construction (Phase 2)

    This is the main entry point for autonomous alpha discovery.
    """

    def __init__(self):
        # Phase 1 components
        self.market_intel = get_market_intelligence()
        self.regime_adaptive = get_regime_adaptive_generator()

        # Phase 2 components
        self.ml_discovery = get_ml_discovery()
        self.genetic_optimizer = get_genetic_optimizer()
        self.ensemble_discovery = get_ensemble_discovery()

        # Discovery history
        self.discovery_history = []
        self.cycle_counter = 0

        logger.info("AutonomousDiscoveryEngine initialized - Phase 1 + Phase 2 integrated")

    async def run_discovery_cycle(
        self,
        symbol: str,
        data: pd.DataFrame,
        mode: DiscoveryMode = DiscoveryMode.EXPLORATORY
    ) -> DiscoveryResult:
        """
        Run a complete autonomous discovery cycle.

        This is the main method that coordinates all discovery components.
        """

        self.cycle_counter += 1
        cycle_id = f"cycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.cycle_counter}"

        logger.info(f"Starting Discovery Cycle {self.cycle_counter}: {mode.value} for {symbol}")

        # Step 1: Market Intelligence (Phase 1)
        logger.info("Step 1: Market Intelligence...")
        regime_state = await self.market_intel.analyze_market_state(symbol, data)
        logger.info(f"  Regime: {regime_state.regime.value} ({regime_state.confidence:.1%} confidence)")

        # Step 2: Regime-Adaptive Signal Generation (Phase 1)
        logger.info("Step 2: Regime-Adaptive Signals...")
        regime_signals = await self.regime_adaptive.generate_signals(
            symbol, data, regime_state
        )
        logger.info(f"  Signals: {len(regime_signals)} regime-adaptive signals generated")

        # Initialize result
        result = DiscoveryResult(
            cycle_id=cycle_id,
            timestamp=datetime.now(),
            mode=mode,
            symbol=symbol,
            regime=regime_state.regime,
            regime_confidence=regime_state.confidence,
            ml_strategies_found=0,
            best_ml_profit=0.0,
            best_ml_sharpe=-999.0,
            ga_strategies_found=0,
            best_ga_profit=0.0,
            best_ga_drawdown=100.0,
            ensemble_created=False,
            ensemble_profit=0.0,
            ensemble_diversification=0.0,
            total_strategies=0,
            profitable_strategies=0,
            best_overall_strategy={},
            recommended_action=""
        )

        # Step 3: ML Strategy Discovery (Phase 2)
        if mode in [DiscoveryMode.EXPLORATORY, DiscoveryMode.OPTIMIZATION, DiscoveryMode.ADAPTIVE]:
            logger.info("Step 3: ML Strategy Discovery...")

            try:
                # Try multiple model types
                for model_type in [MLModelType.GRADIENT_BOOSTING, MLModelType.RANDOM_FOREST]:
                    try:
                        ml_result = await self.ml_discovery.discover_strategies(
                            symbol, data, model_type, target_horizon=5
                        )

                        result.ml_strategies_found += 1
                        if ml_result.total_profit_usdt > result.best_ml_profit:
                            result.best_ml_profit = ml_result.total_profit_usdt
                            result.best_ml_sharpe = ml_result.sharpe_ratio

                        logger.info(f"  {model_type.value}: Profit=${ml_result.total_profit_usdt:.2f}, "
                                   f"Sharpe={ml_result.sharpe_ratio:.2f}")

                    except Exception as e:
                        logger.warning(f"  ML discovery failed for {model_type}: {e}")

            except Exception as e:
                logger.error(f"ML discovery failed: {e}")

        # Step 4: Genetic Algorithm Optimization (Phase 2)
        if mode in [DiscoveryMode.EXPLORATORY, DiscoveryMode.OPTIMIZATION]:
            logger.info("Step 4: Genetic Algorithm Optimization...")

            try:
                # Use smaller population for speed
                self.genetic_optimizer.population_size = 20
                self.genetic_optimizer.generations = 5

                ga_strategies = await self.genetic_optimizer.optimize(data, symbol)
                result.ga_strategies_found = len(ga_strategies)
                result.best_ga_profit = ga_strategies[0].profit_usdt
                result.best_ga_drawdown = ga_strategies[0].max_drawdown_pct

                logger.info(f"  Best GA Strategy: Profit=${ga_strategies[0].profit_usdt:.2f}, "
                           f"Drawdown={ga_strategies[0].max_drawdown_pct:.2%}")

            except Exception as e:
                logger.error(f"Genetic optimization failed: {e}")

        # Step 5: Ensemble Construction (Phase 2)
        if mode in [DiscoveryMode.EXPLORATORY, DiscoveryMode.ENSEMBLE]:
            logger.info("Step 5: Ensemble Construction...")

            try:
                ensemble = await self.ensemble_discovery.discover_ensemble(
                    symbol, data, EnsembleMethod.CORRELATION_OPTIMIZED, num_strategies=3
                )

                result.ensemble_created = True
                result.ensemble_profit = ensemble.total_profit_usdt
                result.ensemble_diversification = ensemble.diversification_ratio

                logger.info(f"  Ensemble: Profit=${ensemble.total_profit_usdt:.2f}, "
                           f"Diversification={ensemble.diversification_ratio:.2f}")

            except Exception as e:
                logger.error(f"Ensemble construction failed: {e}")

        # Step 6: Analysis and Recommendations
        logger.info("Step 6: Analysis and Recommendations...")

        result.total_strategies = (result.ml_strategies_found +
                                   result.ga_strategies_found +
                                   (1 if result.ensemble_created else 0))

        result.profitable_strategies = sum([
            1 if result.best_ml_profit > 0 else 0,
            1 if result.best_ga_profit > 0 else 0,
            1 if result.ensemble_profit > 0 else 0
        ])

        # Find best overall strategy
        profits = {
            'ml': result.best_ml_profit,
            'ga': result.best_ga_profit,
            'ensemble': result.ensemble_profit
        }

        best_type = max(profits, key=profits.get)
        result.best_overall_strategy = {
            'type': best_type,
            'profit': profits[best_type],
            'sharpe': result.best_ml_sharpe if best_type == 'ml' else 0,
            'drawdown': result.best_ga_drawdown if best_type == 'ga' else 0
        }

        # Generate recommendation
        result.recommended_action = self._generate_recommendation(result, regime_state)

        # Store history
        self.discovery_history.append(result)

        logger.info(f"Discovery Cycle {self.cycle_counter} Complete!")
        logger.info(f"  Total Strategies: {result.total_strategies}")
        logger.info(f"  Profitable: {result.profitable_strategies}")
        logger.info(f"  Best Profit: ${result.best_overall_strategy['profit']:.2f}")
        logger.info(f"  Recommendation: {result.recommended_action}")

        return result

    def _generate_recommendation(self, result: DiscoveryResult, regime_state) -> str:
        """Generate actionable recommendation."""

        if result.profitable_strategies == 0:
            return "No profitable strategies found - continue searching"

        best_profit = result.best_overall_strategy['profit']

        if best_profit > 1000:  # >10% return
            return f"STRONG BUY - {result.best_overall_strategy['type'].upper()} strategy showing >10% returns"
        elif best_profit > 500:  # >5% return
            return f"MODERATE BUY - {result.best_overall_strategy['type'].upper()} strategy showing >5% returns"
        elif best_profit > 0:
            return f"WEAK SIGNAL - {result.best_overall_strategy['type'].upper()} strategy profitable but weak"
        else:
            return "WAIT - No profitable strategies found"

    def generate_discovery_report(self, result: DiscoveryResult) -> str:
        """Generate comprehensive discovery report."""

        report = "\n" + "="*60 + "\n"
        report += "AUTONOMOUS DISCOVERY ENGINE REPORT\n"
        report += "="*60 + "\n\n"

        # Cycle info
        report += "CYCLE INFORMATION\n"
        report += "-" * 40 + "\n"
        report += f"Cycle ID: {result.cycle_id}\n"
        report += f"Timestamp: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += f"Mode: {result.mode.value}\n"
        report += f"Symbol: {result.symbol}\n\n"

        # Market state
        report += "MARKET INTELLIGENCE\n"
        report += "-" * 40 + "\n"
        report += f"Regime: {result.regime.value}\n"
        report += f"Confidence: {result.regime_confidence:.1%}\n\n"

        # ML results
        report += "ML STRATEGY DISCOVERY\n"
        report += "-" * 40 + "\n"
        report += f"Strategies Found: {result.ml_strategies_found}\n"
        report += f"Best Profit: ${result.best_ml_profit:.2f}\n"
        report += f"Best Sharpe: {result.best_ml_sharpe:.2f}\n\n"

        # GA results
        report += "GENETIC OPTIMIZATION\n"
        report += "-" * 40 + "\n"
        report += f"Strategies Found: {result.ga_strategies_found}\n"
        report += f"Best Profit: ${result.best_ga_profit:.2f}\n"
        report += f"Best Drawdown: {result.best_ga_drawdown:.2%}\n\n"

        # Ensemble results
        report += "ENSEMBLE CONSTRUCTION\n"
        report += "-" * 40 + "\n"
        report += f"Ensemble Created: {result.ensemble_created}\n"
        report += f"Ensemble Profit: ${result.ensemble_profit:.2f}\n"
        report += f"Diversification Ratio: {result.ensemble_diversification:.2f}\n\n"

        # Overall
        report += "OVERALL RESULTS\n"
        report += "-" * 40 + "\n"
        report += f"Total Strategies: {result.total_strategies}\n"
        report += f"Profitable Strategies: {result.profitable_strategies}\n"
        report += f"Best Strategy Type: {result.best_overall_strategy.get('type', 'N/A')}\n"
        report += f"Best Profit: ${result.best_overall_strategy.get('profit', 0):.2f}\n\n"

        # Recommendation
        report += "RECOMMENDATION\n"
        report += "-" * 40 + "\n"
        report += f"{result.recommended_action}\n\n"

        return report

    def get_discovery_summary(self) -> Dict[str, Any]:
        """Get summary of all discovery cycles."""

        if not self.discovery_history:
            return {}

        return {
            'total_cycles': len(self.discovery_history),
            'total_strategies_discovered': sum(r.total_strategies for r in self.discovery_history),
            'total_profitable_strategies': sum(r.profitable_strategies for r in self.discovery_history),
            'average_profit_per_cycle': np.mean([r.best_overall_strategy.get('profit', 0)
                                                for r in self.discovery_history]),
            'best_cycle_profit': max([r.best_overall_strategy.get('profit', -999999)
                                     for r in self.discovery_history]),
            'regime_distribution': {
                regime.value: sum(1 for r in self.discovery_history if r.regime == regime)
                for regime in MarketRegime
            }
        }


# Singleton instance
_autonomous_discovery_engine = None


def get_autonomous_discovery_engine() -> AutonomousDiscoveryEngine:
    """Get or create autonomous discovery engine instance."""
    global _autonomous_discovery_engine
    if _autonomous_discovery_engine is None:
        _autonomous_discovery_engine = AutonomousDiscoveryEngine()
    return _autonomous_discovery_engine
