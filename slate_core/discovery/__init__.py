"""
SLATE Discovery System

Autonomous strategy discovery using 5 methods.
"""

from .engine import DiscoveryEngine, DiscoveryConfig
from .generator import StrategyGenerator
from .evaluator import StrategyEvaluator
from .memory import DiscoveryMemory

__all__ = ['DiscoveryEngine', 'StrategyGenerator', 'StrategyEvaluator', 'DiscoveryMemory', 'DiscoveryConfig']
