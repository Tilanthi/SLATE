#!/usr/bin/env python3
"""
SLATE Meta-Learning Module

Phase 8: Self-Evolution Architecture (Weeks 29-32)

Components:
- Performance Monitoring: Real-time system and strategy health tracking
- Meta-Learning: Learn from experience and transfer knowledge
- Lifecycle Management: Automated strategy creation and retirement

This phase enables continuous self-improvement and autonomous evolution.

Author: SLATE Evolution
Date: 2026-04-30
Status: OPERATIONAL
"""

from .performance_monitoring import (
    HealthStatus,
    StrategyHealth,
    PerformanceMetric,
    StrategyHealthMetrics,
    SystemDiagnostics,
    PerformanceTracker,
    StrategyHealthMonitor,
    SystemDiagnostics,
    UptimeMonitor,
    PerformanceMonitoringSystem,
    get_performance_monitoring_system
)

from .meta_learning import (
    LearningType,
    LearnedPattern,
    BestPractice,
    PatternExtractor,
    TransferLearning,
    BestPracticesExtractor,
    MistakeAvoidance,
    MetaLearningEngine,
    get_meta_learning_engine
)

from .lifecycle import (
    LifecycleStage,
    TransitionReason,
    LifecycleEvent,
    StrategyLifecycle,
    StrategyCreator,
    DeploymentPipeline,
    LifecycleManager,
    LifecycleMonitor,
    LifecycleManagementSystem,
    get_lifecycle_management_system
)

__all__ = [
    'HealthStatus',
    'StrategyHealth',
    'PerformanceMetric',
    'StrategyHealthMetrics',
    'SystemDiagnostics',
    'PerformanceTracker',
    'StrategyHealthMonitor',
    'SystemDiagnostics',
    'UptimeMonitor',
    'PerformanceMonitoringSystem',
    'get_performance_monitoring_system',

    'LearningType',
    'LearnedPattern',
    'BestPractice',
    'PatternExtractor',
    'TransferLearning',
    'BestPracticesExtractor',
    'MistakeAvoidance',
    'MetaLearningEngine',
    'get_meta_learning_engine',

    'LifecycleStage',
    'TransitionReason',
    'LifecycleEvent',
    'StrategyLifecycle',
    'StrategyCreator',
    'DeploymentPipeline',
    'LifecycleManager',
    'LifecycleMonitor',
    'LifecycleManagementSystem',
    'get_lifecycle_management_system'
]
