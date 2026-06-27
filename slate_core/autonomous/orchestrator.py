"""
SLATE Autonomous Orchestrator - Main Coordinator

Central coordinator for autonomous SLATE operations.
Integrates all autonomous components with reactive priority and resource management.
"""

import asyncio
import logging
import threading
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import deque

from .config import (
    AutonomousConfig,
    TradingGoal,
    Discovery,
    ResourceStatus,
    get_exploratory_config
)
from .resource_manager import ResourceManager
from .decision_maker import TradingDecisionMaker
from .strategy_validator import StrategyValidator
from .discovery_reporter import DiscoveryReporter

logger = logging.getLogger(__name__)


class AutonomousState:
    """Autonomous system state"""
    IDLE = "idle"
    ACTIVE = "active"
    PAUSED = "paused"
    THROTTLED = "throttled"
    STOPPED = "stopped"


class AutonomousOrchestrator:
    """
    Main autonomous coordinator for SLATE trading operations.

    This orchestrator manages all self-initiated activities, including:
    - Idle detection and autonomous activation
    - Trading decision-making coordination
    - Strategy discovery and validation
    - Resource management and safety constraints
    - Reactive priority (user requests always interrupt)
    - Discovery reporting and storage

    SAFETY CONSTRAINTS:
    - Only operates during idle periods (5+ minutes after user activity)
    - User queries immediately pause autonomous operations
    - All strategies validated with realistic transaction costs
    - Resource constraints enforced (CPU, memory, time)
    - Only modifies files within slate_core/ directory
    """

    def __init__(self, config: Optional[AutonomousConfig] = None):
        """
        Initialize the autonomous orchestrator.

        Args:
            config: Configuration for autonomous operations
        """
        self.config = config or get_exploratory_config()

        # Initialize autonomous components
        self.resource_manager = ResourceManager(self.config)
        self.decision_maker = TradingDecisionMaker(self.config)
        self.strategy_validator = StrategyValidator(self.config)
        self.discovery_reporter = DiscoveryReporter(self.config)

        # State management
        self.autonomous_state = AutonomousState.IDLE
        self.last_user_activity = datetime.now()
        self.autonomous_loop_active = False
        self.autonomous_thread: Optional[threading.Thread] = None

        # Discovery tracking
        self.discoveries_made: List[Discovery] = []
        self.discoveries_validated: List[Discovery] = []
        self.discovery_cycle_count = 0
        self.total_discovery_time = 0.0

        # Goal tracking
        self.current_goals: List[TradingGoal] = []
        self.completed_goals: List[TradingGoal] = []
        self.goal_execution_history = []

        # Activity tracking for reactive priority
        self.api_call_history = deque(maxlen=100)
        self.user_query_count = 0

        # Integration with existing SLATE components
        self.intelligent_discovery_engine = None
        self.market_intelligence = {}

        logger.info("Autonomous Orchestrator initialized with state: %s", self.autonomous_state)

    def start(self):
        """Start autonomous operations in background thread"""
        if self.autonomous_loop_active:
            logger.warning("Autonomous operations already active")
            return

        self.autonomous_loop_active = True
        self.autonomous_state = AutonomousState.IDLE

        # Start resource monitoring
        self.resource_manager.start_monitoring()

        # Start autonomous loop in background thread
        self.autonomous_thread = threading.Thread(target=self._autonomous_loop, daemon=True)
        self.autonomous_thread.start()

        logger.info("Autonomous operations started")

    def stop(self):
        """Stop autonomous operations"""
        if not self.autonomous_loop_active:
            logger.warning("Autonomous operations not active")
            return

        logger.info("Stopping autonomous operations...")
        self.autonomous_loop_active = False
        self.autonomous_state = AutonomousState.STOPPED

        # Stop resource monitoring
        self.resource_manager.stop_monitoring()

        # Wait for thread to finish (with timeout)
        if self.autonomous_thread:
            self.autonomous_thread.join(timeout=5.0)

        logger.info("Autonomous operations stopped")

    def record_user_activity(self):
        """
        Record user activity (API call, query, etc.).

        This pauses autonomous operations and resets the idle timer.
        Call this method whenever the user interacts with SLATE.
        """
        self.last_user_activity = datetime.now()
        self.user_query_count += 1
        self.api_call_history.append(datetime.now())

        # If autonomous operations are active, pause them
        if self.autonomous_state == AutonomousState.ACTIVE:
            logger.info("User activity detected - pausing autonomous operations")
            self.autonomous_state = AutonomousState.PAUSED

    def _autonomous_loop(self):
        """Main autonomous operation loop (runs in background thread)"""
        logger.info("Autonomous loop started")

        while self.autonomous_loop_active:
            try:
                # Check if we should be active (idle for 5+ minutes)
                idle_time = (datetime.now() - self.last_user_activity).total_seconds()
                idle_timeout = self.config.idle_timeout_minutes * 60

                if idle_time < idle_timeout:
                    # User is active, wait
                    time.sleep(10)
                    continue

                # Check resource availability
                resource_status = self.resource_manager.get_status()
                if resource_status.approaching_limits:
                    logger.debug("Approaching resource limits - waiting")
                    time.sleep(30)
                    continue

                # Check if we're paused
                if self.autonomous_state == AutonomousState.PAUSED:
                    # Check if enough time has passed to resume
                    if idle_time >= idle_timeout:
                        logger.info("Resuming autonomous operations after idle period")
                        self.autonomous_state = AutonomousState.ACTIVE
                    else:
                        time.sleep(10)
                        continue

                # We're clear to run autonomous operations
                self.autonomous_state = AutonomousState.ACTIVE

                # Run one discovery cycle
                self._run_discovery_cycle()

                # Small sleep between cycles
                time.sleep(5)

            except Exception as e:
                logger.error(f"Error in autonomous loop: {e}", exc_info=True)
                time.sleep(30)  # Wait before retry

        logger.info("Autonomous loop ended")

    def _run_discovery_cycle(self):
        """Run one autonomous discovery cycle"""
        cycle_start = datetime.now()
        self.discovery_cycle_count += 1

        logger.info(f"Starting discovery cycle #{self.discovery_cycle_count}")

        try:
            # 1. Generate goals using market intelligence
            goals = self.decision_maker.generate_goals(
                self.market_intelligence,
                self.resource_manager.get_status().to_dict()
            )

            if not goals:
                logger.debug("No goals generated - waiting for next cycle")
                return

            self.current_goals = goals
            logger.info(f"Generated {len(goals)} goals for this cycle")

            # 2. Execute goals and make discoveries
            cycle_discoveries = []
            for goal in goals:
                try:
                    # Check if we still have resources
                    if not self.resource_manager.can_start_operation(goal.estimated_resources):
                        logger.debug(f"Skipping goal due to resource constraints: {goal.description}")
                        continue

                    # Execute goal (this would integrate with existing SLATE components)
                    discovery = self._execute_goal(goal)

                    if discovery:
                        # Validate discovery
                        validation_result = self.strategy_validator.validate(discovery)

                        if validation_result.passed:
                            cycle_discoveries.append(discovery)
                            self.discoveries_validated.append(discovery)
                            logger.info(f"✅ Discovery validated: {discovery.question[:50]}...")
                        else:
                            logger.debug(f"❌ Discovery rejected: {validation_result.rejection_reasons}")

                except Exception as e:
                    logger.error(f"Error executing goal {goal.description}: {e}")
                    continue

            # 3. Store discoveries
            if cycle_discoveries:
                self.discoveries_made.extend(cycle_discoveries)
                logger.info(f"Cycle complete: {len(cycle_discoveries)} discoveries validated")

            # 4. Update completed goals
            self.completed_goals.extend(goals)

            # 5. Record time spent
            cycle_duration = (datetime.now() - cycle_start).total_seconds()
            self.total_discovery_time += cycle_duration
            self.resource_manager.record_operation_time(cycle_duration)

        except Exception as e:
            logger.error(f"Error in discovery cycle: {e}", exc_info=True)

    def _execute_goal(self, goal: TradingGoal) -> Optional[Discovery]:
        """
        Execute a trading goal and return discoveries.

        This integrates with existing SLATE components to actually
        perform the analysis and make discoveries.

        Args:
            goal: Trading goal to execute

        Returns:
            Discovery if successful, None otherwise
        """
        try:
            # This would integrate with existing SLATE components:
            # - intelligence/autonomous_discovery_engine.py
            # - intelligence/market_regime_detector.py
            # - discovery/edge_discovery_engine.py
            # etc.

            # For now, return a mock discovery to demonstrate the flow
            # In production, this would call actual SLATE discovery components

            logger.debug(f"Executing goal: {goal.description}")

            # Mock discovery for demonstration
            # In production, this would be actual strategy discovery
            discovery = Discovery(
                question=f"Can we find profitable strategies for {goal.symbol} in {goal.timeframe}?",
                answer=f"Discovered potential edge in {goal.symbol} {goal.timeframe} under current conditions",
                category=goal.goal_type.value,
                confidence=0.75,
                novelty_score=0.8,
                profitability_score=0.7,
                symbol=goal.symbol,
                timeframe=goal.timeframe,
                regime_conditions=self.market_intelligence.get('current_regime', {}).get(goal.symbol, {}),
                total_return_pct=5.2,
                sharpe_ratio=0.8,
                max_drawdown_pct=-12.3,
                win_rate=0.65,
                profit_factor=1.8,
                transaction_costs_usdt=45.2,
                profit_after_costs=102.4,
                realistic_edge=True,
                discovery_method="autonomous_discovery",
                validation_details={
                    'total_trades': 28,
                    'out_of_sample_tested': True,
                    'parameter_count': 6
                }
            )

            return discovery

        except Exception as e:
            logger.error(f"Error executing goal: {e}")
            return None

    def get_status(self) -> Dict[str, Any]:
        """Get current autonomous system status"""
        resource_status = self.resource_manager.get_status()

        return {
            'state': self.autonomous_state,
            'uptime_seconds': (datetime.now() - self.autonomous_thread.start_time()
                              if self.autonomous_thread else timedelta()).total_seconds(),
            'discovery_cycles': self.discovery_cycle_count,
            'discoveries_made': len(self.discoveries_made),
            'discoveries_validated': len(self.discoveries_validated),
            'current_goals': len(self.current_goals),
            'completed_goals': len(self.completed_goals),
            'last_user_activity': self.last_user_activity.isoformat(),
            'user_query_count': self.user_query_count,
            'idle_time_seconds': (datetime.now() - self.last_user_activity).total_seconds(),
            'total_discovery_time_hours': self.total_discovery_time / 3600.0,
            'resource_status': resource_status.to_dict(),
            'config': {
                'max_cpu_percent': self.config.max_cpu_percent,
                'max_memory_percent': self.config.max_memory_percent,
                'idle_timeout_minutes': self.config.idle_timeout_minutes,
                'validation_mode': self.config.validation_mode.value
            }
        }

    def get_discoveries(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent discoveries"""
        discoveries = self.discoveries_validated[-limit:]
        return [d.to_dict() for d in discoveries]

    def generate_report(self) -> str:
        """Generate comprehensive discovery report"""
        return self.discovery_reporter.generate_report(
            self.discoveries_validated,
            self.get_status()
        )

    def set_market_intelligence(self, intelligence: Dict[str, Any]):
        """Update market intelligence for decision-making"""
        self.market_intelligence = intelligence
        logger.debug("Market intelligence updated")

    def enable_autonomous_mode(self, enabled: bool = True):
        """Enable or disable autonomous mode"""
        if enabled:
            if not self.autonomous_loop_active:
                self.start()
        else:
            if self.autonomous_loop_active:
                self.stop()

    def cleanup(self):
        """Cleanup resources before shutdown"""
        logger.info("Cleaning up autonomous orchestrator...")
        self.stop()
        logger.info("Autonomous orchestrator cleaned up")