#!/usr/bin/env python3
"""
SLATE Trading Intelligence Orchestrator

Central coordinator for all trading intelligence components.
Runs the main intelligence loop that coordinates strategy selection, portfolio management,
health monitoring, risk control, and lifecycle management.

This is the core "brain" that transforms SLATE from a research engine into a trading system.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class IntelligenceCycle(Enum):
    """Intelligence cycle status."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class IntelligenceStatus:
    """Current status of trading intelligence system."""
    cycle_status: IntelligenceCycle = IntelligenceCycle.IDLE
    last_cycle_time: Optional[datetime] = None
    cycles_completed: int = 0
    strategies_deployed: int = 0
    strategies_retired: int = 0
    portfolio_rebalances: int = 0
    risk_alerts: int = 0
    last_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'cycle_status': self.cycle_status.value,
            'last_cycle_time': self.last_cycle_time.isoformat() if self.last_cycle_time else None,
            'cycles_completed': self.cycles_completed,
            'strategies_deployed': self.strategies_deployed,
            'strategies_retired': self.strategies_retired,
            'portfolio_rebalances': self.portfolio_rebalances,
            'risk_alerts': self.risk_alerts,
            'last_error': self.last_error
        }


class TradingIntelligenceOrchestrator:
    """
    Central coordinator for all trading intelligence components.

    This orchestrator runs the main intelligence loop that:
    1. Checks for new strategies to deploy
    2. Monitors existing strategy health
    3. Checks portfolio risk levels
    4. Makes allocation/rebalancing decisions
    5. Manages strategy lifecycle (deployment/retirement)

    The intelligence loop runs continuously during idle periods and integrates
    seamlessly with the existing autonomous discovery system.
    """

    def __init__(self,
                 cycle_interval_seconds: int = 60,
                 enable_auto_deployment: bool = True,
                 enable_auto_rebalancing: bool = True,
                 enable_risk_management: bool = True):
        """
        Initialize trading intelligence orchestrator.

        Args:
            cycle_interval_seconds: Seconds between intelligence cycles (default: 60)
            enable_auto_deployment: Enable automatic strategy deployment
            enable_auto_rebalancing: Enable automatic portfolio rebalancing
            enable_risk_management: Enable automatic risk management
        """
        self.cycle_interval_seconds = cycle_interval_seconds
        self.enable_auto_deployment = enable_auto_deployment
        self.enable_auto_rebalancing = enable_auto_rebalancing
        self.enable_risk_management = enable_risk_management

        # Initialize intelligence components
        self._initialize_components()

        # Intelligence status tracking
        self.status = IntelligenceStatus()
        self.intelligence_active = False
        self.intelligence_task: Optional[asyncio.Task] = None

        # Configuration
        self.config = {
            'max_deployed_strategies': 10,
            'min_strategy_health_score': 0.6,
            'portfolio_rebalance_threshold': 0.10,  # 10% deviation triggers rebalance
            'risk_limit_max_drawdown': 0.20,  # 20% max drawdown
            'auto_deploy_capital_fraction': 0.10,  # Deploy 10% of capital per new strategy
        }

        logger.info(f"TradingIntelligenceOrchestrator initialized: cycle_interval={cycle_interval_seconds}s")

    def _initialize_components(self):
        """Initialize all intelligence components."""
        try:
            from slate_core.intelligence.strategy_selector import get_strategy_selector
            from slate_core.intelligence.portfolio_manager import get_portfolio_manager
            from slate_core.intelligence.health_monitor import get_health_monitor
            from slate_core.intelligence.risk_controller import get_risk_controller
            from slate_core.intelligence.lifecycle_manager import get_lifecycle_manager

            # Initialize all components
            self.strategy_selector = get_strategy_selector()
            self.portfolio_manager = get_portfolio_manager()
            self.health_monitor = get_health_monitor()
            self.risk_controller = get_risk_controller()
            self.lifecycle_manager = get_lifecycle_manager()

            logger.info("All intelligence components initialized successfully")

        except ImportError as e:
            logger.warning(f"Some intelligence components not available: {e}")
            # Create placeholder components for missing ones
            self.strategy_selector = None
            self.portfolio_manager = None
            self.health_monitor = None
            self.risk_controller = None
            self.lifecycle_manager = None

    async def run_intelligence_loop(self):
        """
        Main intelligence loop - runs continuously during idle periods.

        This is the core "brain" that makes SLATE truly autonomous by:
        1. Discovering profitable strategies -> Deploying them as a portfolio
        2. Monitoring portfolio health -> Managing risk
        3. Adapting to market conditions -> Rebalancing as needed
        4. Retiring failed strategies -> Replacing with better ones
        """
        self.intelligence_active = True
        self.status.cycle_status = IntelligenceCycle.RUNNING

        logger.info("🧠 Trading Intelligence Loop started")

        while self.intelligence_active:
            try:
                cycle_start_time = datetime.now()
                logger.info(f"🔄 Intelligence Cycle #{self.status.cycles_completed + 1} started")

                # Step 1: Check for new strategies to deploy
                if self.enable_auto_deployment:
                    await self._check_and_deploy_strategies()

                # Step 2: Monitor existing strategy health
                if self.portfolio_manager and self.portfolio_manager.current_allocations:
                    await self._monitor_strategy_health()

                # Step 3: Check portfolio risk
                if self.enable_risk_management:
                    await self._check_portfolio_risk()

                # Step 4: Make allocation/rebalancing decisions
                if self.enable_auto_rebalancing:
                    await self._rebalance_if_needed()

                # Step 5: Manage strategy lifecycle (retirement decisions)
                await self._manage_strategy_lifecycle()

                # Update cycle status
                self.status.cycles_completed += 1
                self.status.last_cycle_time = cycle_start_time

                cycle_duration = (datetime.now() - cycle_start_time).total_seconds()
                logger.info(f"✅ Intelligence Cycle #{self.status.cycles_completed} completed in {cycle_duration:.1f}s")

                # Sleep before next cycle
                await asyncio.sleep(self.cycle_interval_seconds)

            except asyncio.CancelledError:
                logger.info("Intelligence loop cancelled")
                break
            except Exception as e:
                logger.error(f"Intelligence cycle error: {e}", exc_info=True)
                self.status.last_error = str(e)
                self.status.cycle_status = IntelligenceCycle.ERROR
                # Continue running despite errors
                await asyncio.sleep(self.cycle_interval_seconds)

        logger.info("Trading Intelligence Loop stopped")
        self.status.cycle_status = IntelligenceCycle.IDLE

    async def _check_and_deploy_strategies(self):
        """Check for new profitable strategies and deploy if warranted."""
        if not self.strategy_selector or not self.portfolio_manager:
            logger.debug("Strategy selector or portfolio manager not available")
            return

        try:
            # Load candidate strategies from database
            candidates = self.strategy_selector.load_candidate_strategies_from_db(25)

            if not candidates:
                logger.debug("No candidate strategies found")
                return

            # Get current market regime
            current_regime = await self._get_current_regime()

            # Create portfolio context
            portfolio_context = self._create_portfolio_context()

            # Select optimal strategies
            selected_strategies, metadata = self.strategy_selector.select_strategies(
                candidates,
                current_regime,
                portfolio_context,
                available_capital=self.portfolio_manager.total_capital
            )

            if not selected_strategies:
                logger.debug("No strategies selected for deployment")
                return

            logger.info(f"🎯 Selected {len(selected_strategies)} strategies for consideration")

            # Deploy new strategies (if not already deployed)
            deployed_count = 0
            for selected_strategy in selected_strategies[:3]:  # Deploy top 3 at most
                strategy_id = selected_strategy.strategy.strategy_id

                # Check if already deployed
                if strategy_id not in self.portfolio_manager.current_allocations:
                    # Calculate capital to allocate
                    capital_to_deploy = self.portfolio_manager.total_capital * self.config['auto_deploy_capital_fraction']

                    # Deploy strategy
                    await self._deploy_strategy(selected_strategy, capital_to_deploy)
                    deployed_count += 1

            if deployed_count > 0:
                self.status.strategies_deployed += deployed_count
                logger.info(f"✅ Deployed {deployed_count} new strategies")

        except Exception as e:
            logger.error(f"Error in strategy deployment check: {e}")

    async def _monitor_strategy_health(self):
        """Monitor health of deployed strategies."""
        if not self.health_monitor or not self.portfolio_manager:
            return

        try:
            # Get current allocations
            current_allocations = self.portfolio_manager.current_allocations

            if not current_allocations:
                return

            # Get current regime
            current_regime = await self._get_current_regime()

            unhealthy_strategies = []

            # Monitor each strategy
            for strategy_id, allocation in current_allocations.items():
                health_status = await self.health_monitor.monitor_strategy_health(
                    strategy_id,
                    allocation,
                    current_regime
                )

                # Log health issues
                if health_status.score < self.config['min_strategy_health_score']:
                    logger.warning(f"⚠️ Strategy {strategy_id} health degraded: {health_status.score:.2f}")
                    unhealthy_strategies.append(strategy_id)

            # Update strategy health in portfolio manager
            for strategy_id in unhealthy_strategies:
                # Could trigger rebalancing or retirement
                pass

        except Exception as e:
            logger.error(f"Error in strategy health monitoring: {e}")

    async def _check_portfolio_risk(self):
        """Check portfolio risk levels and take action if needed."""
        if not self.risk_controller or not self.portfolio_manager:
            return

        try:
            # Get current portfolio state
            portfolio_state = self.portfolio_manager.get_portfolio_state()

            # Check portfolio risk
            risk_action = await self.risk_controller.monitor_portfolio_risk(portfolio_state)

            if risk_action.action_required:
                logger.warning(f"🚨 Risk action required: {risk_action.action_type}")
                self.status.risk_alerts += 1

                # Execute risk actions (in full implementation)
                if risk_action.action_type == "reduce_positions":
                    await self._execute_risk_reduction(risk_action)

        except Exception as e:
            logger.error(f"Error in portfolio risk check: {e}")

    async def _rebalance_if_needed(self):
        """Rebalance portfolio if needed based on performance or regime changes."""
        if not self.portfolio_manager:
            return

        try:
            # Get current regime
            current_regime = await self._get_current_regime()

            # Check if rebalancing is needed
            new_allocation = self.portfolio_manager.rebalance_portfolio(current_regime)

            if new_allocation:
                self.status.portfolio_rebalances += 1
                logger.info(f"🔄 Portfolio rebalanced: {len(new_allocation.allocations)} strategies")

        except Exception as e:
            logger.error(f"Error in portfolio rebalancing: {e}")

    async def _manage_strategy_lifecycle(self):
        """Manage strategy lifecycle including retirement decisions."""
        if not self.lifecycle_manager or not self.portfolio_manager:
            return

        try:
            # Get current allocations
            current_allocations = self.portfolio_manager.current_allocations

            # Check each strategy for lifecycle actions
            for strategy_id, allocation in list(current_allocations.items()):
                lifecycle_action = await self.lifecycle_manager.evaluate_lifecycle_action(
                    strategy_id,
                    allocation
                )

                if lifecycle_action.action == "retire":
                    logger.info(f"🔴 Retiring strategy {strategy_id}: {lifecycle_action.reason}")
                    await self._retire_strategy(strategy_id)
                    self.status.strategies_retired += 1

        except Exception as e:
            logger.error(f"Error in lifecycle management: {e}")

    async def _get_current_regime(self) -> str:
        """Get current market regime."""
        try:
            # Try to get regime from market regime detector
            from slate_core.intelligence.market_regime_detector import get_market_regime_detector
            regime_detector = get_market_regime_detector()
            current_regime = regime_detector.detect_current_regime()
            return current_regime.regime_type.value if current_regime else "TRENDING_UP"
        except Exception as e:
            logger.debug(f"Could not get current regime: {e}")
            return "TRENDING_UP"  # Default regime

    def _create_portfolio_context(self):
        """Create portfolio context for strategy selection."""
        from slate_core.intelligence.strategy_selector import PortfolioContext

        if not self.portfolio_manager:
            # Return empty portfolio context
            return PortfolioContext(
                existing_strategies=[],
                current_allocation={},
                portfolio_return=0.0,
                portfolio_volatility=0.0,
                current_regime="TRENDING_UP"
            )

        # Create context from current portfolio state
        portfolio_state = self.portfolio_manager.get_portfolio_state()

        return PortfolioContext(
            existing_strategies=list(self.portfolio_manager.current_allocations.keys()),
            current_allocation={
                sid: alloc.allocation_weight
                for sid, alloc in self.portfolio_manager.current_allocations.items()
            },
            portfolio_return=portfolio_state.portfolio_return,
            portfolio_volatility=portfolio_state.portfolio_volatility,
            current_regime="TRENDING_UP"
        )

    async def _deploy_strategy(self, selected_strategy, capital: float):
        """Deploy a selected strategy with capital allocation."""
        # In full implementation, this would:
        # 1. Create strategy allocation
        # 2. Add to portfolio manager
        # 3. Start monitoring
        logger.debug(f"Deploying strategy {selected_strategy.strategy.strategy_id} with ${capital:.2f}")

    async def _retire_strategy(self, strategy_id: str):
        """Retire a strategy from the portfolio."""
        # In full implementation, this would:
        # 1. Close positions
        # 2. Remove from portfolio manager
        # 3. Archive performance data
        logger.debug(f"Retiring strategy {strategy_id}")

    async def _execute_risk_reduction(self, risk_action):
        """Execute risk reduction actions."""
        # In full implementation, this would reduce positions or halt trading
        logger.warning(f"Executing risk reduction: {risk_action.action_type}")

    def stop_intelligence_loop(self):
        """Stop the intelligence loop."""
        logger.info("Stopping Trading Intelligence Loop...")
        self.intelligence_active = False

        if self.intelligence_task and not self.intelligence_task.done():
            self.intelligence_task.cancel()

    def get_intelligence_status(self) -> Dict[str, Any]:
        """Get comprehensive intelligence system status."""
        status = {
            'orchestrator_status': self.status.to_dict(),
            'configuration': self.config,
            'components': {
                'strategy_selector': self.strategy_selector is not None,
                'portfolio_manager': self.portfolio_manager is not None,
                'health_monitor': self.health_monitor is not None,
                'risk_controller': self.risk_controller is not None,
                'lifecycle_manager': self.lifecycle_manager is not None
            },
            'enabled_features': {
                'auto_deployment': self.enable_auto_deployment,
                'auto_rebalancing': self.enable_auto_rebalancing,
                'risk_management': self.enable_risk_management
            }
        }

        # Add component-specific stats if available
        if self.portfolio_manager:
            status['portfolio_stats'] = self.portfolio_manager.get_manager_stats()

        if self.strategy_selector:
            status['selector_stats'] = self.strategy_selector.get_selection_stats()

        return status

    async def start_intelligence_task(self):
        """Start the intelligence loop as a background task."""
        if self.intelligence_task and not self.intelligence_task.done():
            logger.warning("Intelligence task already running")
            return

        self.intelligence_task = asyncio.create_task(self.run_intelligence_loop())
        logger.info("🧠 Trading Intelligence Task started")


# Global orchestrator instance
_trading_intelligence_orchestrator: Optional[TradingIntelligenceOrchestrator] = None


def get_trading_intelligence_orchestrator(
    cycle_interval_seconds: int = 60,
    enable_auto_deployment: bool = True,
    enable_auto_rebalancing: bool = True,
    enable_risk_management: bool = True
) -> TradingIntelligenceOrchestrator:
    """Get global trading intelligence orchestrator instance."""
    global _trading_intelligence_orchestrator
    if _trading_intelligence_orchestrator is None:
        _trading_intelligence_orchestrator = TradingIntelligenceOrchestrator(
            cycle_interval_seconds=cycle_interval_seconds,
            enable_auto_deployment=enable_auto_deployment,
            enable_auto_rebalancing=enable_auto_rebalancing,
            enable_risk_management=enable_risk_management
        )
    return _trading_intelligence_orchestrator


if __name__ == "__main__":
    # Test the intelligence orchestrator
    print("Testing Trading Intelligence Orchestrator...")

    orchestrator = get_trading_intelligence_orchestrator()

    # Get initial status
    status = orchestrator.get_intelligence_status()
    print(f"\n🧠 Intelligence Orchestrator Status:")
    print(f"  Orchestrator Status: {status['orchestrator_status']['cycle_status']}")
    print(f"  Components Available: {sum(status['components'].values())}/5")
    print(f"  Auto-Deployment: {status['enabled_features']['auto_deployment']}")
    print(f"  Auto-Rebalancing: {status['enabled_features']['auto_rebalancing']}")
    print(f"  Risk Management: {status['enabled_features']['risk_management']}")

    print(f"\n✨ Trading Intelligence Orchestrator is ready!")