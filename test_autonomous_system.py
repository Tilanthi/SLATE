#!/usr/bin/env python3
"""
SLATE Autonomous System - Comprehensive Testing Suite

Tests all autonomous system components with focus on safety constraints,
transaction cost validation, and resource management.
"""

import unittest
import sys
import os
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
import time

# Add slate_core to path
slate_root = Path(__file__).parent.parent
sys.path.insert(0, str(slate_root))

from slate_core.autonomous.config import (
    AutonomousConfig,
    TradingGoal,
    Discovery,
    ValidationResult,
    GoalType,
    DiscoveryCategory,
    ValidationMode,
    get_conservative_config,
    get_exploratory_config
)

from slate_core.autonomous.resource_manager import ResourceManager
from slate_core.autonomous.strategy_validator import StrategyValidator
from slate_core.autonomous.decision_maker import TradingDecisionMaker
from slate_core.autonomous.sub_agent_spawner import MarketSubAgentSpawner, AgentType
from slate_core.autonomous.discovery_reporter import DiscoveryReporter


class TestAutonomousConfiguration(unittest.TestCase):
    """Test autonomous configuration system"""

    def test_default_configuration(self):
        """Test default configuration has appropriate safety constraints"""
        config = AutonomousConfig()

        # Verify safety constraints
        self.assertEqual(config.max_cpu_percent, 15.0)
        self.assertEqual(config.max_memory_percent, 20.0)
        self.assertEqual(config.max_hours_per_week, 168.0)
        self.assertTrue(config.require_realistic_costs)
        self.assertEqual(config.maker_fee, 0.0002)  # 0.02%
        self.assertEqual(config.taker_fee, 0.0005)  # 0.05%
        self.assertEqual(config.base_slippage_bps, 10.0)
        self.assertEqual(config.partial_fill_probability, 0.15)

        # Verify trading requirements
        self.assertEqual(config.min_sharpe_ratio, 0.5)
        self.assertEqual(config.max_drawdown_pct, 25.0)
        self.assertTrue(config.require_out_of_sample)
        self.assertEqual(config.min_trades_for_significance, 20)

    def test_conservative_configuration(self):
        """Test conservative configuration is more restrictive"""
        config = get_conservative_config()

        self.assertLess(config.max_cpu_percent, 15.0)
        self.assertLess(config.max_hours_per_week, 168.0)
        self.assertEqual(config.validation_mode, ValidationMode.STRICT)

    def test_exploratory_configuration(self):
        """Test exploratory configuration is more permissive"""
        config = get_exploratory_config()

        self.assertGreater(config.max_cpu_percent, 15.0)
        self.assertEqual(config.max_hours_per_week, 168.0)
        self.assertEqual(config.validation_mode, ValidationMode.MODERATE)

    def test_trading_goal_creation(self):
        """Test trading goal dataclass"""
        goal = TradingGoal(
            goal_type=GoalType.STRATEGY_DISCOVERY,
            description="Test strategy discovery",
            symbol="BTCUSDT",
            timeframe="1h",
            priority=0.8,
            estimated_resources={'cpu_percent': 10.0, 'duration_seconds': 120},
            success_criteria={'strategies_found': 5}
        )

        self.assertEqual(goal.goal_type, GoalType.STRATEGY_DISCOVERY)
        self.assertEqual(goal.symbol, "BTCUSDT")
        self.assertTrue(goal.to_dict()['goal_type'] == 'strategy_discovery')

    def test_discovery_creation(self):
        """Test discovery dataclass with transaction costs"""
        discovery = Discovery(
            question="Can we profit from mean reversion?",
            answer="Yes, RSI-based mean reversion shows edge",
            category=DiscoveryCategory.STRATEGY_EDGE,
            confidence=0.75,
            novelty_score=0.8,
            profitability_score=0.7,
            symbol="BTCUSDT",
            timeframe="1h",
            regime_conditions={'trend': 'ranging', 'volatility': 'medium'},
            total_return_pct=5.2,
            sharpe_ratio=0.8,
            max_drawdown_pct=-12.3,
            win_rate=0.65,
            profit_factor=1.8,
            transaction_costs_usdt=45.2,
            profit_after_costs=102.4,
            realistic_edge=True,
            discovery_method="autonomous_discovery"
        )

        self.assertTrue(discovery.realistic_edge)
        self.assertGreater(discovery.profit_after_costs, 0)
        self.assertEqual(discovery.transaction_costs_usdt, 45.2)
        self.assertTrue(discovery.to_dict()['realistic_edge'])


class TestStrategyValidator(unittest.TestCase):
    """Test strategy validation with transaction cost enforcement"""

    def setUp(self):
        """Set up test validator"""
        self.config = get_exploratory_config()
        self.validator = StrategyValidator(self.config)

    def test_transaction_cost_validation_critical(self):
        """Test that transaction cost validation is CRITICAL and enforced"""
        # Create discovery that fails cost validation
        bad_discovery = Discovery(
            question="Test strategy",
            answer="Test answer",
            category=DiscoveryCategory.STRATEGY_EDGE,
            confidence=0.9,
            novelty_score=0.8,
            profitability_score=0.7,
            symbol="BTCUSDT",
            timeframe="1h",
            regime_conditions={'trend': 'up'},
            total_return_pct=5.0,
            sharpe_ratio=0.8,
            max_drawdown_pct=-10.0,
            win_rate=0.6,
            profit_factor=1.5,
            transaction_costs_usdt=100.0,  # High costs
            profit_after_costs=-5.0,  # LOSING money after costs
            realistic_edge=False,
            discovery_method="test"
        )

        result = self.validator.validate(bad_discovery)

        # Must reject due to transaction costs
        self.assertFalse(result.passed)
        self.assertFalse(result.realistic_costs)
        self.assertIn('transaction_costs', result.validation_scores.keys())

    def test_transaction_cost_validation_pass(self):
        """Test that profitable strategies after costs pass validation"""
        good_discovery = Discovery(
            question="Test strategy",
            answer="Test answer",
            category=DiscoveryCategory.STRATEGY_EDGE,
            confidence=0.8,
            novelty_score=0.7,
            profitability_score=0.7,
            symbol="BTCUSDT",
            timeframe="1h",
            regime_conditions={'trend': 'up', 'volatility': 'medium'},
            total_return_pct=8.0,
            sharpe_ratio=0.9,
            max_drawdown_pct=-15.0,
            win_rate=0.65,
            profit_factor=1.8,
            transaction_costs_usdt=35.0,
            profit_after_costs=85.0,  # Profitable after costs
            realistic_edge=True,
            discovery_method="test",
            validation_details={'total_trades': 25, 'out_of_sample_tested': True}
        )

        result = self.validator.validate(good_discovery)

        # Should pass with good transaction cost efficiency
        self.assertTrue(result.passed)
        self.assertTrue(result.realistic_costs)

    def test_statistical_significance_validation(self):
        """Test statistical significance requirements"""
        # Discovery with insufficient trades
        insufficient_trades = Discovery(
            question="Test",
            answer="Test",
            category=DiscoveryCategory.STRATEGY_EDGE,
            confidence=0.8,
            novelty_score=0.7,
            profitability_score=0.7,
            symbol="BTCUSDT",
            timeframe="1h",
            regime_conditions={},
            total_return_pct=5.0,
            sharpe_ratio=0.8,
            max_drawdown_pct=-12.0,
            win_rate=0.6,
            profit_factor=1.5,
            transaction_costs_usdt=20.0,
            profit_after_costs=50.0,
            realistic_edge=True,
            discovery_method="test",
            validation_details={'total_trades': 10}  # Too few
        )

        result = self.validator.validate(insufficient_trades)

        # Should fail due to insufficient trades
        self.assertFalse(result.passed)
        self.assertFalse(result.statistical_significance)

    def test_risk_adjusted_returns_validation(self):
        """Test risk-adjusted return requirements"""
        # Discovery with poor Sharpe ratio
        poor_sharpe = Discovery(
            question="Test",
            answer="Test",
            category=DiscoveryCategory.STRATEGY_EDGE,
            confidence=0.7,
            novelty_score=0.6,
            profitability_score=0.6,
            symbol="BTCUSDT",
            timeframe="1h",
            regime_conditions={},
            total_return_pct=5.0,
            sharpe_ratio=0.3,  # Below minimum 0.5
            max_drawdown_pct=-12.0,
            win_rate=0.55,
            profit_factor=1.3,
            transaction_costs_usdt=20.0,
            profit_after_costs=50.0,
            realistic_edge=True,
            discovery_method="test",
            validation_details={'total_trades': 25}
        )

        result = self.validator.validate(poor_sharpe)

        # Should fail due to poor Sharpe ratio
        self.assertFalse(result.passed)

    def test_validation_mode_strict(self):
        """Test strict validation mode is more restrictive"""
        strict_config = AutonomousConfig(validation_mode=ValidationMode.STRICT)
        strict_validator = StrategyValidator(strict_config)

        marginal_discovery = Discovery(
            question="Test",
            answer="Test",
            category=DiscoveryCategory.STRATEGY_EDGE,
            confidence=0.75,  # Below strict 0.8 threshold
            novelty_score=0.7,
            profitability_score=0.7,
            symbol="BTCUSDT",
            timeframe="1h",
            regime_conditions={},
            total_return_pct=5.0,
            sharpe_ratio=0.8,
            max_drawdown_pct=-15.0,
            win_rate=0.65,
            profit_factor=1.8,
            transaction_costs_usdt=25.0,
            profit_after_costs=60.0,
            realistic_edge=True,
            discovery_method="test",
            validation_details={'total_trades': 25}
        )

        result = strict_validator.validate(marginal_discovery)

        # Should fail in strict mode
        self.assertFalse(result.passed)


class TestResourceManager(unittest.TestCase):
    """Test resource management and constraint enforcement"""

    def setUp(self):
        """Set up test resource manager"""
        self.config = AutonomousConfig(max_cpu_percent=15.0, max_memory_percent=20.0)
        self.resource_manager = ResourceManager(self.config)

    def test_resource_status_tracking(self):
        """Test resource status is tracked correctly"""
        status = self.resource_manager.get_status()

        self.assertIsNotNone(status)
        self.assertIn('cpu_percent', status.to_dict().keys())
        self.assertIn('memory_percent', status.to_dict().keys())

    def test_operation_approval_with_resources(self):
        """Test operations are approved when resources available"""
        estimated_cost = {'cpu_percent': 5.0, 'duration_seconds': 60}

        can_proceed = self.resource_manager.can_start_operation(estimated_cost)

        # Should allow operation within limits
        self.assertTrue(can_proceed)

    def test_operation_rejection_over_limit(self):
        """Test operations are rejected when over resource limits"""
        # Request operation that exceeds CPU limit
        expensive_operation = {'cpu_percent': 20.0, 'duration_seconds': 300}

        can_proceed = self.resource_manager.can_start_operation(expensive_operation)

        # Should reject operation exceeding limits
        self.assertFalse(can_proceed)

    def test_resource_recommendation_system(self):
        """Test resource recommendation system"""
        recommendation = self.resource_manager.get_resource_recommendation()

        self.assertIn('action', recommendation.keys())
        self.assertIn('can_proceed', recommendation.keys())


class TestTradingDecisionMaker(unittest.TestCase):
    """Test adaptive decision-making for trading goals"""

    def setUp(self):
        """Set up test decision maker"""
        self.config = get_exploratory_config()
        self.decision_maker = TradingDecisionMaker(self.config)

    def test_goal_generation_types(self):
        """Test different types of goals are generated"""
        market_intelligence = {
            'current_regime': {'BTCUSDT': {'trend': 'bullish', 'volatility': 'medium'}},
            'volatility_level': 'medium'
        }
        resource_status = {'cpu_percent': 5.0, 'memory_percent': 10.0}

        goals = self.decision_maker.generate_goals(market_intelligence, resource_status)

        # Should generate various goal types
        self.assertGreater(len(goals), 0)
        goal_types = [g.goal_type for g in goals]
        self.assertIn(GoalType.STRATEGY_DISCOVERY, goal_types)

    def test_goal_ranking_by_priority(self):
        """Test goals are ranked by priority and expected value"""
        goals = self.decision_maker.generate_goals({}, {})

        # Check that goals have priorities
        priorities = [g.priority for g in goals]
        self.assertTrue(all(0.0 <= p <= 1.0 for p in priorities))

    def test_market_gap_analysis(self):
        """Test market gap identification"""
        market_intelligence = {
            'current_regime': {},
            'volatility_level': 'unknown'
        }

        gaps = self.decision_maker.analyze_market_gaps(market_intelligence)

        # Should identify gaps in market intelligence
        self.assertIsInstance(gaps, list)


class TestSubAgentSpawner(unittest.TestCase):
    """Test market sub-agent spawning system"""

    def setUp(self):
        """Set up test agent spawner"""
        self.config = AutonomousConfig()
        self.spawner = MarketSubAgentSpawner(self.config)

    def test_agent_spawn_for_goal(self):
        """Test agents are spawned for trading goals"""
        goal = TradingGoal(
            goal_type=GoalType.PATTERN_RECOGNITION,
            description="Discover patterns in BTCUSDT",
            symbol="BTCUSDT",
            timeframe="1h",
            priority=0.7,
            estimated_resources={'cpu_percent': 10.0, 'duration_seconds': 120},
            success_criteria={'patterns_found': 3}
        )

        task_ids = self.spawner.spawn_agents_for_goal(goal)

        # Should spawn agents for the goal
        self.assertGreater(len(task_ids), 0)

    def test_agent_execution_concurrent(self):
        """Test agents execute concurrently"""
        # Spawn multiple agents
        task_id1 = self.spawner.spawn_agent(AgentType.PATTERN_DISCOVERY, {'symbol': 'BTCUSDT'})
        task_id2 = self.spawner.spawn_agent(AgentType.MARKET_REGIME_ANALYST, {'symbol': 'ETHUSDT'})

        # Execute tasks
        results = self.spawner.execute_tasks()

        # Should complete both tasks
        self.assertEqual(len(results), 2)

    def test_agent_result_structure(self):
        """Test agent results have correct structure"""
        task_id = self.spawner.spawn_agent(AgentType.VOLATILITY_ANALYZER, {'symbol': 'BTCUSDT'})
        results = self.spawner.execute_tasks()

        result = results[0]
        self.assertIn('task_id', result.to_dict().keys())
        self.assertIn('success', result.to_dict().keys())
        self.assertIn('execution_time_seconds', result.to_dict().keys())


class TestDiscoveryReporter(unittest.TestCase):
    """Test discovery reporting system"""

    def setUp(self):
        """Set up test reporter"""
        self.config = AutonomousConfig()
        self.reporter = DiscoveryReporter(self.config)

    def test_empty_report_generation(self):
        """Test report handles no discoveries gracefully"""
        system_status = {
            'state': 'active',
            'discovery_cycles': 5,
            'discoveries_made': 0
        }

        report = self.reporter.generate_report([], system_status)

        self.assertIn('No validated discoveries yet', report)

    def test_report_with_discoveries(self):
        """Test report includes discovery statistics"""
        discoveries = [
            Discovery(
                question="Strategy 1",
                answer="Profitable strategy found",
                category=DiscoveryCategory.STRATEGY_EDGE,
                confidence=0.8,
                novelty_score=0.7,
                profitability_score=0.8,
                symbol="BTCUSDT",
                timeframe="1h",
                regime_conditions={'trend': 'bullish'},
                total_return_pct=8.5,
                sharpe_ratio=1.2,
                max_drawdown_pct=-12.0,
                win_rate=0.7,
                profit_factor=2.0,
                transaction_costs_usdt=35.0,
                profit_after_costs=95.0,
                realistic_edge=True,
                discovery_method="autonomous"
            )
        ]

        system_status = {
            'state': 'active',
            'discovery_cycles': 10,
            'discoveries_made': 1
        }

        report = self.reporter.generate_report(discoveries, system_status)

        # Should include discovery statistics
        self.assertIn('8.50%', report)  # Return percentage with proper decimal
        self.assertIn('1.2', report)  # Sharpe ratio

    def test_alert_generation(self):
        """Test alerts are generated for significant discoveries"""
        high_profit_discovery = Discovery(
            question="High profit strategy",
            answer="Very profitable",
            category=DiscoveryCategory.STRATEGY_EDGE,
            confidence=0.9,
            novelty_score=0.8,
            profitability_score=0.9,
            symbol="BTCUSDT",
            timeframe="1h",
            regime_conditions={},
            total_return_pct=25.0,  # High profit
            sharpe_ratio=1.8,
            max_drawdown_pct=-15.0,
            win_rate=0.8,
            profit_factor=2.5,
            transaction_costs_usdt=50.0,
            profit_after_costs=250.0,
            realistic_edge=True,
            discovery_method="test"
        )

        alerts = self.reporter.generate_alerts([high_profit_discovery])

        # Should generate alert for high profit
        self.assertGreater(len(alerts), 0)
        self.assertIn('HIGH PROFIT', alerts[0])


class TestSafetyConstraints(unittest.TestCase):
    """Test critical safety constraints are enforced"""

    def test_transaction_cost_enforcement(self):
        """Test transaction costs are ALWAYS enforced (CRITICAL per CLAUDE.md)"""
        config = AutonomousConfig(require_realistic_costs=True)
        validator = StrategyValidator(config)

        # Discovery with unrealistic costs (profit before costs, loss after)
        unrealistic_discovery = Discovery(
            question="Unrealistic strategy",
            answer="Only works without costs",
            category=DiscoveryCategory.STRATEGY_EDGE,
            confidence=0.9,
            novelty_score=0.8,
            profitability_score=0.7,
            symbol="BTCUSDT",
            timeframe="1h",
            regime_conditions={},
            total_return_pct=10.0,
            sharpe_ratio=1.5,
            max_drawdown_pct=-8.0,
            win_rate=0.7,
            profit_factor=2.0,
            transaction_costs_usdt=150.0,  # High costs
            profit_after_costs=-10.0,  # LOSING after costs
            realistic_edge=False,  # Not validated
            discovery_method="test"
        )

        result = validator.validate(unrealistic_discovery)

        # MUST reject - transaction cost reality is critical
        self.assertFalse(result.passed)
        self.assertFalse(result.realistic_costs)

    def test_scope_constraints_observance(self):
        """Test system respects scope boundaries (slate_core/ only)"""
        config = AutonomousConfig()
        self.assertEqual(config.modification_scope, ["slate_core/"])
        self.assertTrue(config.require_human_approval_for_deployment)

    def test_risk_limits_enforcement(self):
        """Test risk limits are enforced"""
        config = AutonomousConfig()
        validator = StrategyValidator(config)

        # Discovery exceeding drawdown limit
        risky_discovery = Discovery(
            question="Risky strategy",
            answer="Too risky",
            category=DiscoveryCategory.STRATEGY_EDGE,
            confidence=0.7,
            novelty_score=0.6,
            profitability_score=0.6,
            symbol="BTCUSDT",
            timeframe="1h",
            regime_conditions={},
            total_return_pct=15.0,
            sharpe_ratio=1.2,
            max_drawdown_pct=-35.0,  # Exceeds 25% limit
            win_rate=0.6,
            profit_factor=1.8,
            transaction_costs_usdt=40.0,
            profit_after_costs=110.0,
            realistic_edge=True,
            discovery_method="test",
            validation_details={'total_trades': 25}
        )

        result = validator.validate(risky_discovery)

        # Should reject due to excessive drawdown
        self.assertFalse(result.passed)


def run_tests():
    """Run all tests with detailed output"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestAutonomousConfiguration))
    suite.addTests(loader.loadTestsFromTestCase(TestStrategyValidator))
    suite.addTests(loader.loadTestsFromTestCase(TestResourceManager))
    suite.addTests(loader.loadTestsFromTestCase(TestTradingDecisionMaker))
    suite.addTests(loader.loadTestsFromTestCase(TestSubAgentSpawner))
    suite.addTests(loader.loadTestsFromTestCase(TestDiscoveryReporter))
    suite.addTests(loader.loadTestsFromTestCase(TestSafetyConstraints))

    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Tests Run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")

    if result.wasSuccessful():
        print("\n✅ ALL TESTS PASSED - Autonomous system is ready for deployment")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED - Review failures before deployment")
        return 1


if __name__ == '__main__':
    sys.exit(run_tests())