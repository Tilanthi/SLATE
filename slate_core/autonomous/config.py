"""
SLATE Autonomous Configuration

Configuration system for autonomous trading operations with safety constraints.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime

class GoalType(Enum):
    """Types of autonomous trading goals"""
    MARKET_REGIME_ANALYSIS = "market_regime_analysis"
    STRATEGY_DISCOVERY = "strategy_discovery"
    RISK_OPTIMIZATION = "risk_optimization"
    PATTERN_RECOGNITION = "pattern_recognition"
    CORRELATION_EXPLORATION = "correlation_exploration"
    PORTFOLIO_OPTIMIZATION = "portfolio_optimization"
    ANOMALY_DETECTION = "anomaly_detection"

class DiscoveryCategory(Enum):
    """Categories of trading discoveries"""
    STRATEGY_EDGE = "strategy_edge"  # Genuine profitable strategy
    MARKET_INSIGHT = "market_insight"  # Market behavior understanding
    RISK_IMPROVEMENT = "risk_improvement"  # Better risk management
    PATTERN_DISCOVERY = "pattern_discovery"  # Trading pattern found
    CORRELATION_FOUND = "correlation_found"  # Market correlation discovered

class ValidationMode(Enum):
    """Strategy validation strictness"""
    STRICT = "strict"  # High confidence, multiple validation criteria
    MODERATE = "moderate"  # Balanced validation
    TRADING = "trading"  # Trading-focused with realistic costs
    PERMISSIVE = "permissive"  # Lower threshold for exploration

@dataclass
class TradingGoal:
    """Autonomous trading goal for exploration"""
    goal_type: GoalType
    description: str
    symbol: str
    timeframe: str
    priority: float  # 0.0 to 1.0
    estimated_resources: Dict[str, Any]
    success_criteria: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'goal_type': self.goal_type.value,
            'description': self.description,
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'priority': self.priority,
            'estimated_resources': self.estimated_resources,
            'success_criteria': self.success_criteria,
            'created_at': self.created_at.isoformat()
        }

@dataclass
class Discovery:
    """Trading discovery from autonomous exploration"""
    question: str  # What was explored
    answer: str  # What was discovered
    category: DiscoveryCategory
    confidence: float  # 0.0 to 1.0
    novelty_score: float  # 0.0 to 1.0
    profitability_score: float  # 0.0 to 1.0

    # Trading specifics
    symbol: str
    timeframe: str
    regime_conditions: Dict[str, Any]

    # Validation metrics
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    profit_factor: float

    # Transaction cost validation (CRITICAL)
    transaction_costs_usdt: float
    profit_after_costs: float
    realistic_edge: bool  # Only true if profitable AFTER costs

    # Meta information
    discovery_method: str
    timestamp: datetime = field(default_factory=datetime.now)
    validation_details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'question': self.question,
            'answer': self.answer,
            'category': self.category.value,
            'confidence': self.confidence,
            'novelty_score': self.novelty_score,
            'profitability_score': self.profitability_score,
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'regime_conditions': self.regime_conditions,
            'total_return_pct': self.total_return_pct,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown_pct': self.max_drawdown_pct,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'transaction_costs_usdt': self.transaction_costs_usdt,
            'profit_after_costs': self.profit_after_costs,
            'realistic_edge': self.realistic_edge,
            'discovery_method': self.discovery_method,
            'timestamp': self.timestamp.isoformat(),
            'validation_details': self.validation_details
        }

@dataclass
class ValidationResult:
    """Result of strategy validation"""
    passed: bool
    confidence: float
    validation_scores: Dict[str, float]
    rejection_reasons: List[str]
    warnings: List[str]

    # Trading-specific validation
    realistic_costs: bool
    statistical_significance: bool
    market_regime_specific: bool
    overfitting_check: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            'passed': self.passed,
            'confidence': self.confidence,
            'validation_scores': self.validation_scores,
            'rejection_reasons': self.rejection_reasons,
            'warnings': self.warnings,
            'realistic_costs': self.realistic_costs,
            'statistical_significance': self.statistical_significance,
            'market_regime_specific': self.market_regime_specific,
            'overfitting_check': self.overfitting_check
        }

@dataclass
class ResourceStatus:
    """Current resource usage status"""
    cpu_percent: float
    memory_percent: float
    weekly_hours_used: float
    approaching_limits: bool
    throttling_active: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            'cpu_percent': self.cpu_percent,
            'memory_percent': self.memory_percent,
            'weekly_hours_used': self.weekly_hours_used,
            'approaching_limits': self.approaching_limits,
            'throttling_active': self.throttling_active
        }

@dataclass
class AutonomousConfig:
    """
    Configuration for SLATE autonomous operations.

    SAFETY CONSTRAINTS:
    - All discovery must include realistic transaction costs
    - Only paper/backtesting operations allowed
    - Resource limits to prevent system overload
    - Scope limited to slate_core/ directory
    """

    # Resource limits (safety constraints)
    max_cpu_percent: float = 15.0  # Maximum CPU usage
    max_memory_percent: float = 20.0  # Maximum memory usage
    max_hours_per_week: float = 168.0  # 24x7 operation
    idle_timeout_minutes: int = 5  # Wait 5 minutes after user activity

    # Validation thresholds (trading-focused)
    validation_mode: ValidationMode = ValidationMode.TRADING
    min_confidence_to_store: float = 0.7  # 70% confidence required
    min_profitability_score: float = 0.6  # Must be genuinely profitable
    min_sharpe_ratio: float = 0.5  # Risk-adjusted returns required
    max_drawdown_pct: float = 25.0  # Maximum acceptable drawdown

    # Transaction cost requirements (CRITICAL - per CLAUDE.md)
    require_realistic_costs: bool = True  # Always enforce
    maker_fee: float = 0.0002  # 0.02% (actual Binance maker fee)
    taker_fee: float = 0.0005  # 0.05% (actual Binance taker fee)
    base_slippage_bps: float = 10.0  # 10 bps realistic slippage
    partial_fill_probability: float = 0.15  # 15% partial fills

    # Statistical requirements
    min_trades_for_significance: int = 20  # Minimum trade count
    require_out_of_sample: bool = True  # Must validate on unseen data
    overfitting_penalty: float = 0.3  # Penalize complexity

    # Domain and market constraints
    allowed_symbols: List[str] = field(default_factory=lambda: ["SOLUSDT", "BTCUSDT"])
    allowed_timeframes: List[str] = field(default_factory=lambda: ["1h", "4h", "1d"])
    max_positions: int = 5  # Maximum concurrent strategies

    # Discovery preferences
    enable_regime_analysis: bool = True
    enable_strategy_discovery: bool = True
    enable_pattern_recognition: bool = True
    enable_correlation_exploration: bool = True

    # Safety and scope constraints
    modification_scope: List[str] = field(default_factory=lambda: ["slate_core/"])
    require_human_approval_for_deployment: bool = True
    emergency_stop_enabled: bool = True

    # Operation modes
    continuous_operation: bool = True  # Run continuously when idle
    spawn_sub_agents: bool = True  # Enable autonomous agent spawning
    report_discoveries_automatically: bool = True

def get_conservative_config() -> AutonomousConfig:
    """Conservative configuration - low resource usage, strict validation"""
    return AutonomousConfig(
        max_cpu_percent=10.0,
        max_memory_percent=15.0,
        max_hours_per_week=84.0,  # 12 hours/day
        min_confidence_to_store=0.8,  # Higher threshold
        validation_mode=ValidationMode.STRICT,
        enable_correlation_exploration=False  # Fewer activities
    )

def get_exploratory_config() -> AutonomousConfig:
    """Exploratory configuration - higher resource usage, permissive validation"""
    return AutonomousConfig(
        max_cpu_percent=20.0,
        max_memory_percent=25.0,
        max_hours_per_week=168.0,  # 24x7
        min_confidence_to_store=0.6,  # Lower threshold
        validation_mode=ValidationMode.MODERATE,
        enable_correlation_exploration=True  # More activities
    )