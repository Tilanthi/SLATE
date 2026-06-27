"""
SLATE Autonomous Trading Framework

This module provides autonomous capabilities for SLATE to:
- Continuously discover trading strategies during idle periods
- Adaptively explore market opportunities beyond predefined workflows
- Validate strategies with realistic transaction costs
- Spawn specialized market analysis agents
- Manage resources and report discoveries

SAFETY CONSTRAINTS:
- Only operates within slate_core/ directory
- Paper/backtesting only - no live trading
- User requests always take priority (reactive mode)
- All validation includes realistic transaction costs
"""

from .orchestrator import AutonomousOrchestrator
from .config import AutonomousConfig, TradingGoal, Discovery
from .resource_manager import ResourceManager
from .decision_maker import TradingDecisionMaker
from .strategy_validator import StrategyValidator
from .sub_agent_spawner import MarketSubAgentSpawner
from .discovery_reporter import DiscoveryReporter

__all__ = [
    'AutonomousOrchestrator',
    'AutonomousConfig',
    'TradingGoal',
    'Discovery',
    'ResourceManager',
    'TradingDecisionMaker',
    'StrategyValidator',
    'MarketSubAgentSpawner',
    'DiscoveryReporter'
]

# Version and availability
AUTONOMOUS_VERSION = "1.0.0"
AUTONOMOUS_AVAILABLE = True