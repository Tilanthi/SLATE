#!/usr/bin/env python3
"""
Perpetual Futures Swarm Bridge

Connects swarm intelligence agents to the perpetual futures backtesting system.
This replaces the old spot-based discovery pipeline with perpetual futures logic.
"""

import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class PerpetualSwarmBridge:
    """
    Bridge between swarm agents and perpetual futures backtesting.

    This class:
    1. Receives strategy parameters from swarm agents
    2. Converts them to perpetual futures strategies
    3. Runs 12-month brutal backtests
    4. Saves results to perpetual futures database
    """

    def __init__(self):
        self.perpetual_integration = None
        self.is_initialized = False
        self.backtest_stats = {
            'total_strategies_tested': 0,
            'passed_validation': 0,
            'total_profit_usdt': 0,
            'beat_market_count': 0,
            'avg_transaction_costs': 0
        }

    async def initialize(self) -> Dict[str, Any]:
        """Initialize the perpetual futures swarm bridge."""
        try:
            from slate_core.discovery.perpetual_discovery_integration import get_perpetual_integration

            self.perpetual_integration = get_perpetual_integration()
            self.is_initialized = True

            logger.info("✅ Perpetual Swarm Bridge initialized")
            logger.info("📊 Connected to 12-month perpetual futures backtesting")

            return {
                'status': 'success',
                'message': 'Perpetual futures swarm bridge ready',
                'backtest_period': '12 months',
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to initialize perpetual swarm bridge: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }

    async def process_swarm_results(
        self,
        swarm_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Process swarm agent results through perpetual futures backtesting.

        CRITICAL FIX: Ensure all results are saved to database, even if validation fails.

        Args:
            swarm_results: List of agent results with strategy parameters

        Returns:
            Summary of backtesting results
        """
        if not self.is_initialized:
            logger.error("❌ Perpetual swarm bridge not initialized")
            return {
                'status': 'error',
                'message': 'Perpetual swarm bridge not initialized'
            }

        try:
            logger.info(f"🔄 Processing {len(swarm_results)} swarm results through perpetual futures backtest")

            # Convert swarm results to agent parameter format with regime awareness
            agent_params_list = []

            # Import regime-aware mapping
            from slate_core.discovery.regime_aware_agent_mapping import transform_agent_parameters

            # Determine current regime (default to sideways for ranging markets)
            current_regime = 'sideways'  # This could be detected dynamically

            for result in swarm_results:
                if result.get('success', False):
                    params = result.get('parameters', {})
                    params['edge_type'] = result.get('agent_type', 'momentum_mean_reversion')

                    # CRITICAL: Transform to regime-appropriate strategy
                    params = transform_agent_parameters(params, current_regime)

                    agent_params_list.append(params)

            if not agent_params_list:
                logger.warning("⚠️ No valid agent results to process")
                return {
                    'status': 'success',
                    'message': 'No valid agent results to process',
                    'processed': 0,
                    'passed_validation': 0
                }

            logger.info(f"📊 Processing {len(agent_params_list)} agent strategies")

            # Process through perpetual futures backtesting
            backtest_results = await self.perpetual_integration.process_agent_batch(agent_params_list)

            # CRITICAL FIX: Update statistics even if validation fails
            total_tested = backtest_results.get('total_tested', 0)
            passed_validation = backtest_results.get('passed_validation', 0)
            total_profit = backtest_results.get('total_profit_usdt', 0)

            self.backtest_stats['total_strategies_tested'] += total_tested
            self.backtest_stats['passed_validation'] += passed_validation
            self.backtest_stats['total_profit_usdt'] += total_profit

            logger.info(f"✅ Perpetual futures backtesting complete:")
            logger.info(f"  Tested: {total_tested}")
            logger.info(f"  Passed: {passed_validation}")
            logger.info(f"  Failed: {total_tested - passed_validation}")
            logger.info(f"  Total Profit: ${total_profit:.2f}")
            logger.info(f"  Success Rate: {(passed_validation/total_tested)*100:.1f}%" if total_tested > 0 else "  Success Rate: N/A")

            return {
                'status': 'success',
                'processed': total_tested,
                'passed_validation': passed_validation,
                'failed_validation': total_tested - passed_validation,
                'total_profit_usdt': total_profit,
                'results': backtest_results.get('results', []),
                'backtest_stats': self.backtest_stats,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"❌ Failed to process swarm results: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                'status': 'error',
                'message': str(e)
            }

    def get_statistics(self) -> Dict[str, Any]:
        """Get perpetual futures backtesting statistics."""
        return {
            'total_strategies_tested': self.backtest_stats['total_strategies_tested'],
            'passed_validation': self.backtest_stats['passed_validation'],
            'total_profit_usdt': self.backtest_stats['total_profit_usdt'],
            'beat_market_count': self.backtest_stats['beat_market_count'],
            'success_rate': (
                self.backtest_stats['passed_validation'] / self.backtest_stats['total_strategies_tested']
                if self.backtest_stats['total_strategies_tested'] > 0 else 0
            ),
            'backtest_period': '12 months',
            'data_source': 'Binance Futures (real data)',
            'transaction_costs': 'Brutally realistic (fees, slippage, funding rates)'
        }


# Singleton instance
_perpetual_swarm_bridge = None

def get_perpetual_swarm_bridge() -> PerpetualSwarmBridge:
    """Get the singleton perpetual swarm bridge instance."""
    global _perpetual_swarm_bridge
    if _perpetual_swarm_bridge is None:
        _perpetual_swarm_bridge = PerpetualSwarmBridge()
    return _perpetual_swarm_bridge


if __name__ == "__main__":
    # Test the bridge
    print("Testing Perpetual Swarm Bridge...")

    async def test():
        bridge = get_perpetual_swarm_bridge()

        # Initialize
        init_result = await bridge.initialize()
        print(f"Initialization: {init_result['status']}")

        if init_result['status'] == 'success':
            # Mock swarm results
            mock_swarm_results = [
                {
                    'success': True,
                    'agent_type': 'momentum_mean_reversion',
                    'parameters': {
                        'fast_period': 10,
                        'slow_period': 20,
                        'signal_threshold': 0.5,
                        'position_size': 0.03
                    }
                },
                {
                    'success': True,
                    'agent_type': 'volatility_regime',
                    'parameters': {
                        'fast_period': 14,
                        'slow_period': 28,
                        'signal_threshold': 0.6,
                        'position_size': 0.025
                    }
                }
            ]

            # Process results
            process_result = await bridge.process_swarm_results(mock_swarm_results)
            print(f"Processing: {process_result['status']}")
            print(f"Processed: {process_result.get('processed', 0)}")
            print(f"Passed: {process_result.get('passed_validation', 0)}")

    asyncio.run(test())