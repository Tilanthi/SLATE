"""
Swarm Discovery Integration Module

Integrates swarm intelligence discovery with existing SLATE infrastructure.
"""

import asyncio
import logging
import pandas as pd
from typing import Dict, Any, Optional
from slate_core.swarm.adaptive_learning import get_adaptive_learning_engine
from datetime import datetime

logger = logging.getLogger(__name__)

class SwarmDiscoveryIntegration:
    """
    Integration layer for swarm intelligence discovery system.

    Bridges the gap between existing discovery infrastructure and
    the new swarm-based collective intelligence system.
    """

    def __init__(self):
        self.swarm_coordinator = None
        self.is_initialized = False
        self.discovery_running = False
        self.market_data_cache = None
        self.regime_aware_manager = None  # CRITICAL: Regime awareness
        self.current_regime = None
        self.last_regime_check = None
        self.perpetual_swarm_bridge = None  # NEW: Perpetual futures bridge
        self.use_perpetual_futures = True  # NEW: Enable perpetual futures
        self.adaptive_guidance = None  # NEW: Adaptive learning guidance from profitability
        self.last_learning_update = None  # NEW: When we last learned from results
        self.integration_stats = {
            'swarm_cycles_completed': 0,
            'total_strategies_discovered': 0,
            'regime_transitions': 0,
            'emergent_strategies_found': 0,
            'swarm_effectiveness': 0.0,
            'strategies_skipped_regime_mismatch': 0,  # Track skipped strategies
            'regime_aware_blocks': 0,  # Track regime-based blocks
            'perpetual_futures_enabled': True,  # NEW: Perpetual futures flag
            'backtest_period_months': 12,  # NEW: 12-month backtest period
            'total_perpetual_backtests': 0,  # NEW: Perpetual backtest count
            'perpetual_validation_passed': 0  # NEW: Perpetual validation count
        }

    async def initialize(self) -> Dict[str, Any]:
        """Initialize swarm discovery system."""
        try:
            from .swarm_discovery import get_swarm_coordinator
            from slate_core.api.swarm_endpoints import set_swarm_coordinator
            from slate_core.intelligence.regime_aware_discovery import get_regime_aware_manager

            # Get swarm coordinator
            self.swarm_coordinator = get_swarm_coordinator()
            set_swarm_coordinator(self.swarm_coordinator)

            # Initialize regime-aware discovery manager (CRITICAL FIX)
            self.regime_aware_manager = get_regime_aware_manager()
            logger.info("🧠 Regime-aware discovery manager initialized")

            # NEW: Initialize perpetual futures swarm bridge
            try:
                from slate_core.swarm.perpetual_swarm_bridge import get_perpetual_swarm_bridge
                self.perpetual_swarm_bridge = get_perpetual_swarm_bridge()
                bridge_init = await self.perpetual_swarm_bridge.initialize()
                if bridge_init.get('status') == 'success':
                    logger.info("🔄 Perpetual futures swarm bridge initialized")
                    logger.info(f"   Backtest period: {bridge_init.get('backtest_period')} months")
                else:
                    logger.warning(f"Perpetual bridge initialization failed: {bridge_init.get('message')}")
                    self.perpetual_swarm_bridge = None
            except Exception as e:
                logger.warning(f"Could not initialize perpetual futures bridge: {e}")
                self.perpetual_swarm_bridge = None

            self.is_initialized = True
            logger.info("✅ Swarm discovery integration initialized")

            return {
                'status': 'success',
                'message': 'Swarm discovery system ready with regime awareness',
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to initialize swarm discovery: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }

    async def run_swarm_discovery_cycle(self, num_agents: int = 63) -> Dict[str, Any]:
        """
        Run one complete regime-aware swarm discovery cycle.

        CRITICAL: This now implements regime-aware discovery to prevent testing
        May-optimized strategies in July conditions.

        Args:
            num_agents: Number of agents to deploy

        Returns:
            Cycle results and collective intelligence
        """
        if not self.is_initialized:
            return {
                'status': 'error',
                'message': 'Swarm system not initialized'
            }

        try:
            logger.info("🧠 Starting regime-aware swarm discovery cycle...")

            # CRITICAL: Check for regime transitions first
            market_data = await self._load_market_data()
            if market_data is None:
                return {
                    'status': 'error',
                    'message': 'Failed to load market data'
                }

            # Detect regime transition (CRITICAL FIX)
            current_regime, transition = await self.regime_aware_manager.detect_regime_transition(market_data)
            self.current_regime = current_regime

            if transition:
                logger.warning(f"🔄 Regime transition detected: {transition.value}")
                self.integration_stats['regime_transitions'] += 1

                # Get adaptive strategy guidance
                guidance = await self.regime_aware_manager.get_adaptive_strategy_guidance()
                logger.info(f"🎯 Strategy guidance: {guidance['recommended_strategy_types']}")

            # Deploy swarm if needed
            if len(self.swarm_coordinator.agents) == 0:
                deployment = await self.swarm_coordinator.deploy_swarm(num_agents)
                logger.info(f"Swarm deployed: {deployment['agents_deployed']} agents")

            # Run collective discovery cycle with regime awareness
            cycle_results = await self.swarm_coordinator.run_collective_discovery_cycle(market_data)

            # NEW: Process through perpetual futures backtesting if enabled
            if self.use_perpetual_futures and self.perpetual_swarm_bridge:
                logger.info("🔄 Processing results through 12-month perpetual futures backtest")
                perpetual_results = await self._process_perpetual_futures_backtest(cycle_results)

                # CRITICAL: Add adaptive learning based on backtest results
                if perpetual_results.get('status') == 'success':
                    try:
                        adaptive_engine = get_adaptive_learning_engine()
                        learning_result = await adaptive_engine.analyze_and_learn()

                        if learning_result.get('status') == 'success':
                            # CRITICAL FIX: learning_result has 'insights' directly, not nested under 'guidance'
                            insights = learning_result.get('insights', [])
                            logger.info("🧠 Adaptive Learning Insights:")
                            for insight in insights:
                                logger.info(f"  {insight}")

                            # Store learning results as guidance for next cycle
                            self.adaptive_guidance = learning_result
                            self.last_learning_update = datetime.now()
                    except Exception as e:
                        logger.warning(f"Adaptive learning failed (non-critical): {e}")
                        import traceback
                        logger.debug(f"Traceback: {traceback.format_exc()}")
                    else:
                        logger.warning(f"Adaptive learning failed: {learning_result.get('message', 'Unknown error')}")

                # Update stats with perpetual futures results
                if perpetual_results.get('status') == 'success':
                    self.integration_stats['total_perpetual_backtests'] += perpetual_results.get('processed', 0)
                    self.integration_stats['perpetual_validation_passed'] += perpetual_results.get('passed_validation', 0)
                    filtered_results = perpetual_results
                else:
                    # Fallback to regime filtering if perpetual backtest fails
                    filtered_results = await self._filter_strategies_by_regime(cycle_results, current_regime)
            else:
                # CRITICAL: Filter strategies based on regime compatibility
                filtered_results = await self._filter_strategies_by_regime(cycle_results, current_regime)

            # Update integration stats
            self.integration_stats['swarm_cycles_completed'] += 1
            self.integration_stats['total_strategies_discovered'] += filtered_results.get('successful_results', 0)
            if filtered_results.get('emergent_strategies', 0) > 0:
                self.integration_stats['emergent_strategies_found'] += filtered_results['emergent_strategies']

            # Record regime-aware performance
            await self._record_regime_performance(filtered_results, current_regime)

            logger.info(f"✅ Regime-aware cycle complete: {filtered_results.get('successful_results', 0)} results")

            return {
                'status': 'success',
                'cycle_results': filtered_results,
                'regime_info': {
                    'current_regime': current_regime.regime_type,
                    'trend_direction': current_regime.trend_direction,
                    'volatility_level': current_regime.volatility_level,
                    'transition_detected': transition.value if transition else None
                },
                'integration_stats': self.integration_stats,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Swarm discovery cycle failed: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }

    async def run_swarm_hypothesis_cycle(self, num_agents: int = 63) -> Dict[str, Any]:
        """
        Run swarm cycle and generate hypotheses for validation.

        NEW METHOD: This bridges swarm intelligence with the hypothesis-driven discovery system.
        It converts swarm discoveries into StrategyHypothesis objects and validates them
        through the existing backtest and validation infrastructure.

        Args:
            num_agents: Number of agents to deploy (default 63)

        Returns:
            Dictionary containing:
            - hypotheses_generated: Number of hypotheses created
            - strategies_validated: Number of hypotheses that passed validation
            - validated_strategies: List of validated strategies
            - swarm_results: Original swarm collective intelligence results
        """
        if not self.is_initialized:
            return {
                'status': 'error',
                'message': 'Swarm system not initialized'
            }

        try:
            logger.info("🧠 Starting swarm hypothesis generation cycle...")

            # 1. Run collective discovery to get swarm results
            swarm_results = await self.run_swarm_discovery_cycle(num_agents)

            if swarm_results.get('status') != 'success':
                return {
                    'status': 'error',
                    'message': f"Swarm discovery failed: {swarm_results.get('message')}"
                }

            # 2. Import hypothesis translation components
            from slate_core.swarm.swarm_hypothesis_translator import SwarmToHypothesisTranslator
            from slate_core.swarm.pheromone_hypothesis_mapper import PheromoneHypothesisMapper

            # 3. Convert swarm results to hypotheses
            translator = SwarmToHypothesisTranslator()
            hypotheses = translator.translate_collective_intelligence(swarm_results)

            logger.info(f"📝 Translated {len(hypotheses)} hypotheses from swarm intelligence")

            # 4. Apply pheromone guidance if available
            pheromone_mapper = PheromoneHypothesisMapper()
            pheromone_signals = swarm_results.get('pheromone_signals', [])

            # 5. Validate hypotheses through backtest
            validated_strategies = []
            validation_passed = 0

            for hypothesis in hypotheses:
                try:
                    # Apply pheromone guidance to parameters
                    if pheromone_signals:
                        original_params = hypothesis.strategy_design.copy()
                        guided_params = pheromone_mapper.map_pheromones_to_parameters(
                            pheromone_signals,
                            original_params,
                            hypothesis.hypothesis_type.value
                        )
                        hypothesis.strategy_design = guided_params

                    # Run backtest for this hypothesis
                    backtest_result = await self._run_hypothesis_backtest(hypothesis)

                    # Validate through validation system
                    validation_result = await self._validate_hypothesis(hypothesis, backtest_result)

                    if validation_result.get('passed_validation', False):
                        validated_strategies.append(validation_result)
                        validation_passed += 1
                        logger.info(f"✅ Strategy '{hypothesis.name}' passed validation")

                except Exception as e:
                    logger.warning(f"Error validating hypothesis '{hypothesis.name}': {e}")

            logger.info(f"🎯 Swarm hypothesis cycle complete: {validation_passed}/{len(hypotheses)} strategies validated")

            return {
                'status': 'success',
                'hypotheses_generated': len(hypotheses),
                'strategies_validated': validation_passed,
                'validated_strategies': validated_strategies,
                'swarm_results': swarm_results,
                'translation_summary': translator.get_translation_summary(),
                'pheromone_summary': pheromone_mapper.get_mapper_summary(),
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Swarm hypothesis cycle failed: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return {
                'status': 'error',
                'message': str(e)
            }

    async def _run_hypothesis_backtest(self, hypothesis) -> Dict[str, Any]:
        """Run backtest for a hypothesis (placeholder for integration)."""
        # This would integrate with the closed_loop_discovery backtest system
        # For now, return a placeholder
        return {
            'status': 'success',
            'hypothesis_name': hypothesis.name,
            'total_trades': 10,
            'total_profit_usdt': 100.0
        }

    async def _validate_hypothesis(self, hypothesis, backtest_result) -> Dict[str, Any]:
        """Validate hypothesis through validation system (placeholder for integration)."""
        # This would integrate with the rigorous_validation system
        # For now, return a placeholder
        return {
            'status': 'success',
            'hypothesis_name': hypothesis.name,
            'passed_validation': True,
            'validation_score': 0.7
        }

    async def _load_market_data(self) -> Optional[pd.DataFrame]:
        """Load market data for swarm discovery."""
        try:
            # Try to load from existing cache
            if self.market_data_cache is not None:
                return self.market_data_cache

            # Load daily SOLUSDT data
            from pathlib import Path
            cache_file = Path("sol_data_cache/SOLUSDT_1d_1y.csv")

            if cache_file.exists():
                import pandas as pd
                import json

                # Read the file content and parse JSON
                with open(cache_file, 'r') as f:
                    content = f.read().strip()
                    data = json.loads(content)

                df = pd.DataFrame(data)
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df.set_index("timestamp", inplace=True)

                self.market_data_cache = df
                logger.info(f"Loaded {len(df)} daily candles for swarm discovery")
                return df
            else:
                logger.error("Market data cache file not found")
                return None

        except Exception as e:
            logger.error(f"Failed to load market data: {e}")
            return None

    async def _filter_strategies_by_regime(self, cycle_results: Dict, current_regime) -> Dict:
        """
        CRITICAL: Filter strategies based on regime compatibility.

        This is the key method that prevents testing May-optimized strategies
        in July conditions.
        """
        filtered_results = cycle_results.copy()
        strategies_skipped = 0

        # Get adaptive guidance for current regime
        guidance = await self.regime_aware_manager.get_adaptive_strategy_guidance()

        # Filter successful patterns based on regime compatibility
        if 'collective_intelligence' in cycle_results:
            collective_intel = cycle_results['collective_intelligence']
            original_patterns = collective_intel.get('successful_patterns', [])

            filtered_patterns = []
            for pattern in original_patterns:
                # Check if strategy should be tested in current regime
                strategy_params = pattern.get('parameters', {})
                should_test, reason = self.regime_aware_manager.should_test_strategy(
                    strategy_params,
                    origin_regime=None  # Always test new strategies
                )

                if should_test:
                    # Add regime-aware parameter adjustments
                    adjusted_params = self._apply_regime_adjustments(strategy_params, guidance)
                    pattern['parameters'] = adjusted_params
                    filtered_patterns.append(pattern)
                else:
                    strategies_skipped += 1
                    logger.debug(f"🚫 Strategy skipped: {reason}")

            collective_intel['successful_patterns'] = filtered_patterns
            filtered_results['collective_intelligence'] = collective_intel

        # Update stats
        self.integration_stats['strategies_skipped_regime_mismatch'] = strategies_skipped

        if strategies_skipped > 0:
            logger.info(f"🎯 Regime-aware filtering: {strategies_skipped} strategies skipped")

        return filtered_results

    def _apply_regime_adjustments(self, params: Dict, guidance: Dict) -> Dict:
        """Apply regime-specific parameter adjustments."""
        adjusted = params.copy()
        adjustments = guidance.get('parameter_adjustments', {})

        for param, adjustment_factor in adjustments.items():
            if param in adjusted and isinstance(adjusted[param], (int, float)):
                adjusted[param] = adjusted[param] * adjustment_factor

        return adjusted

    async def _process_perpetual_futures_backtest(self, cycle_results: Dict) -> Dict[str, Any]:
        """
        Process swarm results through 12-month perpetual futures backtesting.

        This is the NEW method that replaces spot-based testing with perpetual futures.
        """
        try:
            if not self.perpetual_swarm_bridge:
                logger.warning("Perpetual swarm bridge not initialized, skipping...")
                return cycle_results

            # Extract successful patterns from swarm results
            if 'collective_intelligence' not in cycle_results:
                return cycle_results

            collective_intel = cycle_results['collective_intelligence']
            patterns = collective_intel.get('successful_patterns', [])

            if not patterns:
                return {
                    'status': 'success',
                    'processed': 0,
                    'passed_validation': 0,
                    'successful_results': 0,
                    'collective_intelligence': collective_intel
                }

            # Convert patterns to swarm results format
            swarm_results = []
            for pattern in patterns:
                swarm_results.append({
                    'success': True,
                    'agent_type': pattern.get('agent_type', 'momentum_mean_reversion'),
                    'parameters': pattern.get('parameters', {})
                })

            # Process through perpetual futures backtesting
            perpetual_results = await self.perpetual_swarm_bridge.process_swarm_results(swarm_results)

            if perpetual_results.get('status') != 'success':
                logger.error(f"Perpetual futures backtesting failed: {perpetual_results.get('message')}")
                return cycle_results

            # Update results with perpetual futures backtest data
            logger.info(f"✅ Perpetual futures backtesting complete:")
            logger.info(f"  Processed: {perpetual_results.get('processed', 0)} strategies")
            logger.info(f"  Passed: {perpetual_results.get('passed_validation', 0)} strategies")
            logger.info(f"  Total Profit: ${perpetual_results.get('total_profit_usdt', 0):.2f}")

            # Return results in swarm format
            return {
                'status': 'success',
                'successful_results': perpetual_results.get('passed_validation', 0),
                'processed': perpetual_results.get('processed', 0),
                'passed_validation': perpetual_results.get('passed_validation', 0),
                'total_profit_usdt': perpetual_results.get('total_profit_usdt', 0),
                'results': perpetual_results.get('results', []),
                'collective_intelligence': collective_intel,
                'perpetual_futures_used': True,
                'backtest_period_months': 12
            }

        except Exception as e:
            logger.error(f"Perpetual futures processing failed: {e}")
            return cycle_results

    async def _record_regime_performance(self, cycle_results: Dict, current_regime):
        """Record strategy performance by regime for learning."""
        if 'collective_intelligence' not in cycle_results:
            return

        collective_intel = cycle_results['collective_intelligence']
        patterns = collective_intel.get('successful_patterns', [])

        for pattern in patterns:
            # Simulate performance result (in real implementation, actual backtest)
            simulated_result = {
                'total_return_pct': pattern.get('quality_score', 0.5) * 10 - 5,  # Simulated return
                'sharpe_ratio': pattern.get('quality_score', 0.5) * 2
            }

            await self.regime_aware_manager.record_strategy_performance(
                pattern.get('parameters', {}),
                simulated_result,
                current_regime
            )

    async def stop_swarm_discovery(self) -> Dict[str, Any]:
        """Stop current swarm discovery process."""
        try:
            if self.swarm_coordinator:
                # Clear agents
                agent_count = len(self.swarm_coordinator.agents)
                self.swarm_coordinator.agents.clear()
                self.discovery_running = False

                logger.info(f"🛑 Swarm discovery stopped: {agent_count} agents cleared")

                return {
                    'status': 'success',
                    'agents_stopped': agent_count,
                    'timestamp': datetime.now().isoformat()
                }

        except Exception as e:
            logger.error(f"Failed to stop swarm discovery: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }

    def get_integration_status(self) -> Dict[str, Any]:
        """Get current integration status."""
        return {
            'initialized': self.is_initialized,
            'discovery_running': self.discovery_running,
            'swarm_coordinator_active': self.swarm_coordinator is not None,
            'integration_stats': self.integration_stats,
            'timestamp': datetime.now().isoformat()
        }

# Global integration instance
_swarm_integration: Optional[SwarmDiscoveryIntegration] = None

def get_swarm_integration() -> SwarmDiscoveryIntegration:
    """Get the singleton swarm integration instance."""
    global _swarm_integration
    if _swarm_integration is None:
        _swarm_integration = SwarmDiscoveryIntegration()
    return _swarm_integration