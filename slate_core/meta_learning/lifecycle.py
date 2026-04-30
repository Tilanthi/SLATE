#!/usr/bin/env python3
"""
SLATE Lifecycle Management System

Phase 8: Self-Evolution Architecture (Weeks 29-32)

Implements automated strategy lifecycle management:
- Strategy creation
- Deployment pipelines
- Monitoring
- Retirement

Critical for autonomous system evolution.

Author: SLATE Evolution
Date: 2026-04-30
Priority: HIGH - Autonomous lifecycle management
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

logger = logging.getLogger(__name__)


class LifecycleStage(Enum):
    """Strategy lifecycle stages."""
    DISCOVERY = "discovery"  # Being discovered
    VALIDATION = "validation"  # Being validated
    PAPER_TRADING = "paper_trading"  # Paper trading
    LIVE = "live"  # Live trading (if enabled)
    MONITORING = "monitoring"  # Active monitoring
    DEGRADATION = "degradation"  # Performance degrading
    RETIREMENT = "retirement"  # Pending retirement
    RETIRED = "retired"  # Retired


class TransitionReason(Enum):
    """Reasons for lifecycle transitions."""
    VALIDATION_PASSED = "validation_passed"
    VALIDATION_FAILED = "validation_failed"
    PERFORMANCE_TARGET_MET = "performance_target_met"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    RISK_LIMIT_EXCEEDED = "risk_limit_exceeded"
    MARKET_REGIME_CHANGE = "market_regime_change"
    OBSOLESCENCE = "obsolescence"
    MANUAL = "manual"


@dataclass
class LifecycleEvent:
    """A lifecycle transition event."""
    strategy_name: str
    from_stage: LifecycleStage
    to_stage: LifecycleStage
    reason: TransitionReason
    timestamp: datetime
    details: Dict[str, Any]


@dataclass
class StrategyLifecycle:
    """Strategy lifecycle state."""
    strategy_name: str
    current_stage: LifecycleStage
    created_at: datetime
    promoted_at: Optional[datetime]
    retired_at: Optional[datetime]

    # Performance tracking
    validation_metrics: Optional[Dict[str, float]]
    paper_trading_metrics: Optional[Dict[str, float]]
    live_metrics: Optional[Dict[str, float]]

    # Events
    events: List[LifecycleEvent]

    # Health
    health_score: float  # 0-1
    degradation_detected: bool


class StrategyCreator:
    """
    Automated strategy creation.

    Generates new strategies based on learned patterns and market conditions.
    """

    def __init__(self):
        self.created_strategies: List[Dict[str, Any]] = []
        logger.info("StrategyCreator initialized")

    async def create_strategy(
        self,
        template: Dict[str, Any],
        market_context: Dict[str, Any],
        learned_patterns: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Create a new strategy.

        Args:
            template: Strategy template
            market_context: Current market conditions
            learned_patterns: Learned patterns to apply

        Returns:
            Created strategy
        """

        strategy = {
            'name': f"strategy_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'type': template.get('type', 'momentum'),
            'parameters': self._generate_parameters(template, learned_patterns),
            'created_at': datetime.now().isoformat(),
            'market_context': market_context,
            'stage': LifecycleStage.DISCOVERY,
            'status': 'created'
        }

        self.created_strategies.append(strategy)

        logger.info(f"Created strategy: {strategy['name']}")

        return strategy

    def _generate_parameters(
        self,
        template: Dict[str, Any],
        learned_patterns: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Generate strategy parameters."""

        params = template.get('default_parameters', {})

        # Apply learned patterns
        if learned_patterns:
            for pattern in learned_patterns:
                if pattern.get('pattern_type') == 'success_pattern':
                    # Apply successful parameters
                    conditions = pattern.get('conditions', {})
                    params.update(conditions)

        return params


class DeploymentPipeline:
    """
    Automated deployment pipeline.

    Manages strategy progression through lifecycle stages.
    """

    def __init__(self):
        self.pipeline_stages = [
            LifecycleStage.DISCOVERY,
            LifecycleStage.VALIDATION,
            LifecycleStage.PAPER_TRADING,
            LifecycleStage.MONITORING,
            LifecycleStage.LIVE
        ]
        logger.info("DeploymentPipeline initialized")

    async def deploy_strategy(
        self,
        strategy: Dict[str, Any],
        target_stage: LifecycleStage
    ) -> LifecycleEvent:
        """
        Deploy strategy to target stage.

        Args:
            strategy: Strategy to deploy
            target_stage: Target lifecycle stage

        Returns:
            Deployment event
        """

        current_stage = strategy.get('stage', LifecycleStage.DISCOVERY)

        # Validate transition
        if not self._is_valid_transition(current_stage, target_stage):
            raise ValueError(f"Invalid transition: {current_stage} -> {target_stage}")

        # Execute deployment
        event = await self._execute_deployment(strategy, target_stage)

        return event

    def _is_valid_transition(
        self,
        from_stage: LifecycleStage,
        to_stage: LifecycleStage
    ) -> bool:
        """Check if transition is valid."""

        # Can move forward or backward in pipeline
        from_idx = self.pipeline_stages.index(from_stage) if from_stage in self.pipeline_stages else -1
        to_idx = self.pipeline_stages.index(to_stage) if to_stage in self.pipeline_stages else -1

        # Can always move to retirement
        if to_stage == LifecycleStage.RETIREMENT:
            return True

        # Can move forward in pipeline
        if from_idx >= 0 and to_idx >= 0:
            return to_idx > from_idx

        # Degradation and monitoring are special cases
        if to_stage in [LifecycleStage.MONITORING, LifecycleStage.DEGRADATION]:
            return True

        return False

    async def _execute_deployment(
        self,
        strategy: Dict[str, Any],
        target_stage: LifecycleStage
    ) -> LifecycleEvent:
        """Execute deployment to target stage."""

        # Stage-specific deployment logic
        if target_stage == LifecycleStage.VALIDATION:
            # Run validation
            await self._run_validation(strategy)

        elif target_stage == LifecycleStage.PAPER_TRADING:
            # Start paper trading
            await self._start_paper_trading(strategy)

        elif target_stage == LifecycleStage.LIVE:
            # Deploy to live (if enabled)
            await self._deploy_live(strategy)

        # Create event
        event = LifecycleEvent(
            strategy_name=strategy['name'],
            from_stage=strategy.get('stage', LifecycleStage.DISCOVERY),
            to_stage=target_stage,
            reason=TransitionReason.VALIDATION_PASSED,
            timestamp=datetime.now(),
            details={'deployment_status': 'success'}
        )

        return event

    async def _run_validation(self, strategy: Dict[str, Any]):
        """Run strategy validation."""
        # Would integrate with Phase 4 validation system
        logger.info(f"Validating strategy {strategy['name']}")

    async def _start_paper_trading(self, strategy: Dict[str, Any]):
        """Start paper trading."""
        logger.info(f"Starting paper trading for {strategy['name']}")

    async def _deploy_live(self, strategy: Dict[str, Any]):
        """Deploy to live trading."""
        logger.info(f"Deploying {strategy['name']} to live")
        # Note: SLATE is paper-trading only, so this would remain paper trading


class LifecycleManager:
    """
    Manage strategy lifecycle.

    Tracks and manages strategies through their lifecycle.
    """

    def __init__(self):
        self.strategies: Dict[str, StrategyLifecycle] = {}
        self.deployment_pipeline = DeploymentPipeline()

        logger.info("LifecycleManager initialized")

    async def register_strategy(
        self,
        strategy: Dict[str, Any]
    ) -> StrategyLifecycle:
        """
        Register a new strategy.

        Args:
            strategy: Strategy to register

        Returns:
            Strategy lifecycle
        """

        lifecycle = StrategyLifecycle(
            strategy_name=strategy['name'],
            current_stage=LifecycleStage.DISCOVERY,
            created_at=datetime.now(),
            promoted_at=None,
            retired_at=None,
            validation_metrics=None,
            paper_trading_metrics=None,
            live_metrics=None,
            events=[],
            health_score=1.0,
            degradation_detected=False
        )

        self.strategies[strategy['name']] = lifecycle

        logger.info(f"Registered strategy: {strategy['name']}")

        return lifecycle

    async def advance_strategy(
        self,
        strategy_name: str,
        target_stage: LifecycleStage,
        reason: TransitionReason = TransitionReason.MANUAL,
        metrics: Optional[Dict[str, float]] = None
    ) -> bool:
        """
        Advance strategy to next stage.

        Args:
            strategy_name: Strategy name
            target_stage: Target stage
            reason: Transition reason
            metrics: Performance metrics

        Returns:
            Success status
        """

        if strategy_name not in self.strategies:
            logger.error(f"Strategy not found: {strategy_name}")
            return False

        lifecycle = self.strategies[strategy_name]
        current_stage = lifecycle.current_stage

        # Check if transition is valid
        if not self.deployment_pipeline._is_valid_transition(current_stage, target_stage):
            logger.warning(f"Invalid transition: {current_stage} -> {target_stage}")
            return False

        # Deploy strategy
        strategy = {'name': strategy_name, 'stage': current_stage}
        event = await self.deployment_pipeline.deploy_strategy(strategy, target_stage)

        # Update lifecycle
        lifecycle.current_stage = target_stage

        if target_stage == LifecycleStage.PAPER_TRADING:
            lifecycle.promoted_at = datetime.now()

        if target_stage == LifecycleStage.RETIRED:
            lifecycle.retired_at = datetime.now()

        if metrics:
            if target_stage == LifecycleStage.VALIDATION:
                lifecycle.validation_metrics = metrics
            elif target_stage == LifecycleStage.PAPER_TRADING:
                lifecycle.paper_trading_metrics = metrics
            elif target_stage == LifecycleStage.LIVE:
                lifecycle.live_metrics = metrics

        # Record event
        lifecycle.events.append(event)

        logger.info(f"Advanced {strategy_name} to {target_stage.value}")

        return True

    async def check_degradation(
        self,
        strategy_name: str,
        current_metrics: Dict[str, float]
    ) -> bool:
        """
        Check if strategy is degrading.

        Args:
            strategy_name: Strategy name
            current_metrics: Current performance metrics

        Returns:
            True if degradation detected
        """

        if strategy_name not in self.strategies:
            return False

        lifecycle = self.strategies[strategy_name]

        # Get baseline metrics
        baseline = lifecycle.paper_trading_metrics or lifecycle.validation_metrics
        if not baseline:
            return False

        # Check for degradation
        degradation_indicators = []

        # Return degradation
        baseline_return = baseline.get('return', 0)
        current_return = current_metrics.get('return', 0)
        if current_return < baseline_return * 0.5:  # 50% decline
            degradation_indicators.append('return_degradation')

        # Drawdown increase
        baseline_dd = baseline.get('max_drawdown', 0)
        current_dd = current_metrics.get('max_drawdown', 0)
        if current_dd > baseline_dd * 1.5:  # 50% increase
            degradation_indicators.append('drawdown_increase')

        # Sharpe decline
        baseline_sharpe = baseline.get('sharpe', 0)
        current_sharpe = current_metrics.get('sharpe', 0)
        if current_sharpe < baseline_sharpe * 0.7:  # 30% decline
            degradation_indicators.append('sharpe_decline')

        # Update lifecycle
        if degradation_indicators:
            lifecycle.degradation_detected = True
            lifecycle.health_score = max(0, lifecycle.health_score - 0.2)

            # If in monitoring, move to degradation stage
            if lifecycle.current_stage == LifecycleStage.MONITORING:
                await self.advance_strategy(
                    strategy_name,
                    LifecycleStage.DEGRADATION,
                    TransitionReason.PERFORMANCE_DEGRADATION,
                    current_metrics
                )

            logger.warning(f"Degradation detected for {strategy_name}: {degradation_indicators}")
            return True

        return False

    async def retire_strategy(
        self,
        strategy_name: str,
        reason: TransitionReason = TransitionReason.OBSOLESCENCE
    ) -> bool:
        """
        Retire a strategy.

        Args:
            strategy_name: Strategy name
            reason: Retirement reason

        Returns:
            Success status
        """

        if strategy_name not in self.strategies:
            return False

        # Move to retirement
        success = await self.advance_strategy(
            strategy_name,
            LifecycleStage.RETIRED,
            reason
        )

        if success:
            logger.info(f"Retired strategy: {strategy_name}")

        return success


class LifecycleMonitor:
    """
    Monitor strategy lifecycle health.

    Automatically manages lifecycle transitions.
    """

    def __init__(self, lifecycle_manager: LifecycleManager):
        self.lifecycle_manager = lifecycle_manager
        self.monitor_interval = timedelta(hours=1)
        logger.info("LifecycleMonitor initialized")

    async def monitor_strategies(
        self,
        active_strategies: Dict[str, Dict[str, float]]
    ) -> List[Dict[str, Any]]:
        """
        Monitor all active strategies.

        Args:
            active_strategies: Strategy performance metrics

        Returns:
            Actions taken
        """

        actions = []

        for strategy_name, metrics in active_strategies.items():
            lifecycle = self.lifecycle_manager.strategies.get(strategy_name)

            if not lifecycle:
                continue

            # Check for degradation
            if await self.lifecycle_manager.check_degradation(strategy_name, metrics):
                actions.append({
                    'strategy': strategy_name,
                    'action': 'degradation_detected',
                    'details': 'Moved to degradation stage'
                })

            # Check health score
            health = self._calculate_health(lifecycle, metrics)
            lifecycle.health_score = health

            # Auto-retire if health is too low
            if health < 0.2 and lifecycle.current_stage != LifecycleStage.RETIRED:
                await self.lifecycle_manager.retire_strategy(
                    strategy_name,
                    TransitionReason.PERFORMANCE_DEGRADATION
                )
                actions.append({
                    'strategy': strategy_name,
                    'action': 'auto_retired',
                    'details': f'Health score {health:.2f} below threshold'
                })

        return actions

    def _calculate_health(
        self,
        lifecycle: StrategyLifecycle,
        metrics: Dict[str, float]
    ) -> float:
        """Calculate strategy health score."""

        health = 1.0

        # Return component
        target_return = (lifecycle.validation_metrics or {}).get('return', 0)
        current_return = metrics.get('return', 0)
        if target_return > 0:
            return_ratio = current_return / target_return
            health *= min(1.0, max(0.0, return_ratio))

        # Drawdown component
        max_dd = (lifecycle.validation_metrics or {}).get('max_drawdown', 0.2)
        current_dd = metrics.get('drawdown', 0)
        if current_dd > max_dd:
            health *= max(0.0, 1 - (current_dd - max_dd) / max_dd)

        # Sharpe component
        target_sharpe = (lifecycle.validation_metrics or {}).get('sharpe', 1.0)
        current_sharpe = metrics.get('sharpe', 0)
        if target_sharpe > 0:
            sharpe_ratio = current_sharpe / target_sharpe
            health *= min(1.0, max(0.0, sharpe_ratio))

        return max(0.0, min(1.0, health))


class LifecycleManagementSystem:
    """
    Unified lifecycle management system.

    Coordinates all lifecycle components.
    """

    def __init__(self):
        self.creator = StrategyCreator()
        self.pipeline = DeploymentPipeline()
        self.lifecycle_manager = LifecycleManager()
        self.monitor = LifecycleMonitor(self.lifecycle_manager)

        logger.info("LifecycleManagementSystem initialized")

    async def create_and_deploy(
        self,
        template: Dict[str, Any],
        market_context: Dict[str, Any],
        learned_patterns: Optional[List[Dict[str, Any]]] = None,
        target_stage: LifecycleStage = LifecycleStage.VALIDATION
    ) -> Dict[str, Any]:
        """
        Create and deploy a new strategy.

        Args:
            template: Strategy template
            market_context: Market context
            learned_patterns: Learned patterns
            target_stage: Target deployment stage

        Returns:
            Deployment result
        """

        # Create strategy
        strategy = await self.creator.create_strategy(template, market_context, learned_patterns)

        # Register lifecycle
        lifecycle = await self.lifecycle_manager.register_strategy(strategy)

        # Deploy to target stage
        success = await self.lifecycle_manager.advance_strategy(
            strategy['name'],
            target_stage,
            TransitionReason.VALIDATION_PASSED
        )

        return {
            'strategy': strategy,
            'lifecycle': lifecycle,
            'deployment_success': success
        }

    async def monitor_and_manage(
        self,
        active_strategies: Dict[str, Dict[str, float]]
    ) -> Dict[str, Any]:
        """
        Monitor and manage active strategies.

        Args:
            active_strategies: Strategy metrics

        Returns:
            Management actions
        """

        actions = await self.monitor.monitor_strategies(active_strategies)

        # Generate recommendations
        recommendations = []
        for strategy_name, lifecycle in self.lifecycle_manager.strategies.items():
            if lifecycle.current_stage == LifecycleStage.DEGRADATION:
                recommendations.append({
                    'strategy': strategy_name,
                    'action': 'review_parameters',
                    'reason': 'Performance degradation detected'
                })

            elif lifecycle.health_score < 0.5:
                recommendations.append({
                    'strategy': strategy_name,
                    'action': 'reduce_exposure',
                    'reason': f'Health score low: {lifecycle.health_score:.2f}'
                })

        return {
            'actions_taken': actions,
            'recommendations': recommendations,
            'active_strategies': len(self.lifecycle_manager.strategies),
            'retired_strategies': sum(
                1 for lc in self.lifecycle_manager.strategies.values()
                if lc.current_stage == LifecycleStage.RETIRED
            )
        }

    def generate_lifecycle_report(self) -> str:
        """Generate lifecycle management report."""

        report = f"""
{'='*60}
LIFECYCLE MANAGEMENT REPORT
{'='*60}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

STRATEGY COUNT: {len(self.lifecycle_manager.strategies)}

BY STAGE:
"""

        stage_counts = {}
        for lifecycle in self.lifecycle_manager.strategies.values():
            stage = lifecycle.current_stage.value
            stage_counts[stage] = stage_counts.get(stage, 0) + 1

        for stage, count in sorted(stage_counts.items(), key=lambda x: x[0]):
            report += f"  {stage.replace('_', ' ').title()}: {count}\n"

        report += "\nHEALTH DISTRIBUTION:\n"

        healthy = sum(1 for lc in self.lifecycle_manager.strategies.values() if lc.health_score > 0.7)
        warning = sum(1 for lc in self.lifecycle_manager.strategies.values() if 0.3 < lc.health_score <= 0.7)
        critical = sum(1 for lc in self.lifecycle_manager.strategies.values() if lc.health_score <= 0.3)

        report += f"  Healthy (>0.7): {healthy}\n"
        report += f"  Warning (0.3-0.7): {warning}\n"
        report += f"  Critical (<0.3): {critical}\n"

        report += "\nRECENT EVENTS:\n"

        all_events = []
        for lifecycle in self.lifecycle_manager.strategies.values():
            all_events.extend(lifecycle.events[-5:])

        all_events.sort(key=lambda e: e.timestamp, reverse=True)

        for event in all_events[:10]:
            report += f"""
  {event.strategy_name}: {event.from_stage.value} → {event.to_stage.value}
    Reason: {event.reason.value}
    Time: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
"""

        return report


# Singleton instance
_lifecycle_management_system = None


def get_lifecycle_management_system() -> LifecycleManagementSystem:
    """Get or create lifecycle management system instance."""
    global _lifecycle_management_system
    if _lifecycle_management_system is None:
        _lifecycle_management_system = LifecycleManagementSystem()
    return _lifecycle_management_system
