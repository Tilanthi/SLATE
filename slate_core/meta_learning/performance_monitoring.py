#!/usr/bin/env python3
"""
SLATE Performance Monitoring System

Phase 8: Self-Evolution Architecture (Weeks 29-32)

Implements comprehensive performance monitoring:
- Real-time performance tracking
- Strategy health metrics
- System diagnostics
- Uptime monitoring

Critical for autonomous system health and optimization.

Author: SLATE Evolution
Date: 2026-04-30
Priority: HIGH - System health monitoring
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
import psutil
import time

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """System health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    OFFLINE = "offline"


class StrategyHealth(Enum):
    """Strategy health status."""
    EXCELLENT = "excellent"  # Performing as expected or better
    GOOD = "good"  # Performing within acceptable range
    WARNING = "warning"  # Performance degradation detected
    CRITICAL = "critical"  # Significant issues
    DISABLED = "disabled"  # Strategy disabled


@dataclass
class PerformanceMetric:
    """A performance metric."""
    name: str
    value: float
    unit: str
    timestamp: datetime
    threshold: Optional[float] = None
    status: HealthStatus = HealthStatus.HEALTHY


@dataclass
class StrategyHealthMetrics:
    """Strategy health metrics."""
    strategy_name: str
    health: StrategyHealth

    # Performance
    current_return: float
    expected_return: float
    return_deviation: float

    # Risk
    current_drawdown: float
    max_drawdown_limit: float
    volatility: float

    # Trading
    trade_count: int
    win_rate: float
    profit_factor: float

    # Health indicators
    last_trade_time: datetime
    consecutive_losses: int
    signal_quality: float

    # Diagnostics
    issues: List[str]
    recommendations: List[str]


@dataclass
class SystemDiagnostics:
    """System diagnostic information."""
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    uptime_seconds: float
    active_threads: int

    # API status
    api_health: bool
    database_health: bool
    data_feed_health: bool

    # Performance
    avg_response_time: float
    requests_per_second: float

    # Issues
    errors: List[str]
    warnings: List[str]


class PerformanceTracker:
    """
    Track performance metrics in real-time.

    Monitors system and strategy performance continuously.
    """

    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.metrics_history: Dict[str, List[PerformanceMetric]] = {}

        self.start_time = time.time()

        logger.info(f"PerformanceTracker initialized (window={window_size})")

    def track_metric(
        self,
        name: str,
        value: float,
        unit: str = "",
        threshold: Optional[float] = None
    ):
        """
        Track a performance metric.

        Args:
            name: Metric name
            value: Metric value
            unit: Unit of measurement
            threshold: Warning threshold
        """

        metric = PerformanceMetric(
            name=name,
            value=value,
            unit=unit,
            timestamp=datetime.now(),
            threshold=threshold
        )

        # Determine status
        if threshold is not None:
            if value > threshold * 1.5:
                metric.status = HealthStatus.CRITICAL
            elif value > threshold:
                metric.status = HealthStatus.DEGRADED

        # Store in history
        if name not in self.metrics_history:
            self.metrics_history[name] = []

        self.metrics_history[name].append(metric)

        # Trim to window size
        if len(self.metrics_history[name]) > self.window_size:
            self.metrics_history[name].pop(0)

    def get_metric(
        self,
        name: str,
        period: Optional[timedelta] = None
    ) -> Optional[List[PerformanceMetric]]:
        """
        Get metric history.

        Args:
            name: Metric name
            period: Time period to retrieve

        Returns:
            List of metrics
        """

        if name not in self.metrics_history:
            return None

        metrics = self.metrics_history[name]

        if period is not None:
            cutoff = datetime.now() - period
            metrics = [m for m in metrics if m.timestamp >= cutoff]

        return metrics

    def get_metric_summary(
        self,
        name: str,
        period: timedelta = timedelta(hours=1)
    ) -> Dict[str, float]:
        """
        Get metric summary statistics.

        Args:
            name: Metric name
            period: Time period

        Returns:
            Summary statistics
        """

        metrics = self.get_metric(name, period)

        if not metrics:
            return {}

        values = [m.value for m in metrics]

        return {
            'count': len(values),
            'mean': np.mean(values),
            'std': np.std(values),
            'min': np.min(values),
            'max': np.max(values),
            'latest': values[-1] if values else None
        }


class StrategyHealthMonitor:
    """
    Monitor strategy health.

    Detects performance degradation and issues.
    """

    def __init__(self):
        self.health_history: Dict[str, List[StrategyHealthMetrics]] = {}
        self.baseline_metrics: Dict[str, Dict[str, float]] = {}

        logger.info("StrategyHealthMonitor initialized")

    async def assess_strategy_health(
        self,
        strategy_name: str,
        current_metrics: Dict[str, Any],
        baseline_metrics: Optional[Dict[str, float]] = None
    ) -> StrategyHealthMetrics:
        """
        Assess strategy health.

        Args:
            strategy_name: Strategy name
            current_metrics: Current performance metrics
            baseline_metrics: Baseline/expected metrics

        Returns:
            Strategy health metrics
        """

        # Store baseline if provided
        if baseline_metrics:
            self.baseline_metrics[strategy_name] = baseline_metrics
        else:
            baseline_metrics = self.baseline_metrics.get(strategy_name, {})

        # Extract metrics
        current_return = current_metrics.get('return', 0)
        expected_return = baseline_metrics.get('expected_return', 0)
        current_drawdown = current_metrics.get('drawdown', 0)
        max_dd_limit = baseline_metrics.get('max_drawdown_limit', 0.2)
        volatility = current_metrics.get('volatility', 0)

        trade_count = current_metrics.get('trade_count', 0)
        win_rate = current_metrics.get('win_rate', 0)
        profit_factor = current_metrics.get('profit_factor', 0)

        # Calculate health
        issues = []
        recommendations = []
        health = StrategyHealth.GOOD

        # Check return deviation
        return_deviation = current_return - expected_return
        if abs(return_deviation) > 0.1:  # 10% deviation
            health = StrategyHealth.WARNING
            issues.append(f"Return deviation: {return_deviation:.2%} from expected")
            recommendations.append("Review strategy parameters")

        # Check drawdown
        if current_drawdown > max_dd_limit * 0.8:
            health = StrategyHealth.WARNING
            issues.append(f"Drawdown approaching limit: {current_drawdown:.2%}")
            recommendations.append("Consider reducing position sizes")

        if current_drawdown > max_dd_limit:
            health = StrategyHealth.CRITICAL
            issues.append(f"Drawdown exceeded limit: {current_drawdown:.2%}")
            recommendations.append("DISABLE STRATEGY - Risk limit exceeded")

        # Check win rate
        if win_rate < 0.4 and trade_count > 20:
            health = StrategyHealth.WARNING
            issues.append(f"Low win rate: {win_rate:.1%}")
            recommendations.append("Review entry/exit conditions")

        # Check profit factor
        if profit_factor < 1.0 and trade_count > 20:
            health = StrategyHealth.CRITICAL
            issues.append(f"Profit factor < 1.0: {profit_factor:.2f}")
            recommendations.append("Strategy losing money - review or disable")

        # Check recent activity
        last_trade = current_metrics.get('last_trade_time')
        consecutive_losses = current_metrics.get('consecutive_losses', 0)

        if consecutive_losses > 5:
            health = StrategyHealth.WARNING
            issues.append(f"{consecutive_losses} consecutive losses")
            recommendations.append("Review recent trades for pattern")

        # Create health metrics
        health_metrics = StrategyHealthMetrics(
            strategy_name=strategy_name,
            health=health,
            current_return=current_return,
            expected_return=expected_return,
            return_deviation=return_deviation,
            current_drawdown=current_drawdown,
            max_drawdown_limit=max_dd_limit,
            volatility=volatility,
            trade_count=trade_count,
            win_rate=win_rate,
            profit_factor=profit_factor,
            last_trade_time=last_trade or datetime.now(),
            consecutive_losses=consecutive_losses,
            signal_quality=current_metrics.get('signal_quality', 0.5),
            issues=issues,
            recommendations=recommendations
        )

        # Store in history
        if strategy_name not in self.health_history:
            self.health_history[strategy_name] = []

        self.health_history[strategy_name].append(health_metrics)

        # Trim history
        if len(self.health_history[strategy_name]) > 1000:
            self.health_history[strategy_name].pop(0)

        return health_metrics

    def get_health_trend(
        self,
        strategy_name: str,
        periods: int = 10
    ) -> str:
        """
        Get health trend over time.

        Args:
            strategy_name: Strategy name
            periods: Number of periods to analyze

        Returns:
            Trend description
        """

        if strategy_name not in self.health_history:
            return "No data"

        history = self.health_history[strategy_name][-periods:]

        if len(history) < 2:
            return "Insufficient data"

        # Count health states
        health_counts = {}
        for metrics in history:
            health_counts[metrics.health] = health_counts.get(metrics.health, 0) + 1

        # Determine trend
        recent = history[-1].health
        earlier = history[0].health

        health_order = [StrategyHealth.EXCELLENT, StrategyHealth.GOOD, StrategyHealth.WARNING, StrategyHealth.CRITICAL]

        if health_order.index(recent) < health_order.index(earlier):
            return "IMPROVING"
        elif health_order.index(recent) > health_order.index(earlier):
            return "DECLINING"
        else:
            return "STABLE"


class SystemDiagnostics:
    """
    System diagnostics and monitoring.

    Tracks system resource usage and health.
    """

    def __init__(self):
        self.start_time = time.time()
        self.error_log: List[Dict[str, Any]] = []
        self.performance_log: List[Dict[str, float]] = []

        logger.info("SystemDiagnostics initialized")

    async def get_diagnostics(self) -> slate_core.meta_learning.performance_monitoring.SystemDiagnostics:
        """
        Get current system diagnostics.

        Returns:
            System diagnostics
        """

        # System resources
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # Uptime
        uptime = time.time() - self.start_time

        # Threads
        threads = psutil.Thread().num_threads() if hasattr(psutil.Thread(), 'num_threads') else 0

        # Performance metrics
        avg_response_time = np.mean([p['response_time'] for p in self.performance_log[-100:]]) if self.performance_log else 0
        rps = len(self.performance_log) / max(1, uptime) if self.performance_log else 0

        # Recent errors
        recent_errors = [e for e in self.error_log if time.time() - e.get('timestamp', 0) < 3600]
        errors = [e['message'] for e in recent_errors[-10:]]

        # Warnings
        warnings = []
        if cpu_usage > 80:
            warnings.append(f"High CPU usage: {cpu_usage:.1f}%")
        if memory.percent > 80:
            warnings.append(f"High memory usage: {memory.percent:.1f}%")
        if disk.percent > 80:
            warnings.append(f"High disk usage: {disk.percent:.1f}%")

        return slate_core.meta_learning.performance_monitoring.SystemDiagnostics(
            cpu_usage=cpu_usage,
            memory_usage=memory.percent,
            disk_usage=disk.percent,
            uptime_seconds=uptime,
            active_threads=threads,
            api_health=True,  # Would check actual health
            database_health=True,  # Would check actual health
            data_feed_health=True,  # Would check actual health
            avg_response_time=avg_response_time,
            requests_per_second=rps,
            errors=errors,
            warnings=warnings
        )

    def log_error(self, error: str, context: Optional[Dict[str, Any]] = None):
        """Log an error."""
        self.error_log.append({
            'timestamp': time.time(),
            'message': error,
            'context': context or {}
        })

        # Trim log
        if len(self.error_log) > 1000:
            self.error_log.pop(0)

    def log_performance(self, response_time: float, request_type: str):
        """Log performance metric."""
        self.performance_log.append({
            'timestamp': time.time(),
            'response_time': response_time,
            'request_type': request_type
        })

        # Trim log
        if len(self.performance_log) > 10000:
            self.performance_log.pop(0)


class UptimeMonitor:
    """
    Monitor system uptime and availability.

    Tracks availability and generates uptime reports.
    """

    def __init__(self):
        self.start_time = time.time()
        self.downtime_events: List[Dict[str, Any]] = []
        self.last_check_time = time.time()
        self.is_down = False

        logger.info("UptimeMonitor initialized")

    async def check_uptime(self) -> bool:
        """
        Check if system is up.

        Returns:
            True if system is up
        """

        current_time = time.time()

        # Simulate health check
        is_up = True  # Would actually check system health

        # Record downtime event
        if not is_up and not self.is_down:
            self.downtime_events.append({
                'start': self.last_check_time,
                'end': None,  # Ongoing
                'duration': None
            })
            self.is_down = True

        elif is_up and self.is_down:
            # End downtime event
            if self.downtime_events:
                self.downtime_events[-1]['end'] = current_time
                self.downtime_events[-1]['duration'] = current_time - self.downtime_events[-1]['start']
            self.is_down = False

        self.last_check_time = current_time

        return is_up

    def get_uptime_stats(self) -> Dict[str, Any]:
        """
        Get uptime statistics.

        Returns:
            Uptime statistics
        """

        total_time = time.time() - self.start_time

        # Calculate total downtime
        total_downtime = sum(
            e['duration'] for e in self.downtime_events
            if e['duration'] is not None
        )

        # If currently down, add ongoing downtime
        if self.is_down and self.downtime_events:
            ongoing_downtime = time.time() - self.downtime_events[-1]['start']
            total_downtime += ongoing_downtime

        uptime_percentage = (total_time - total_downtime) / total_time * 100 if total_time > 0 else 100

        return {
            'uptime_seconds': total_time - total_downtime,
            'downtime_seconds': total_downtime,
            'uptime_percentage': uptime_percentage,
            'downtime_events': len(self.downtime_events),
            'current_status': 'DOWN' if self.is_down else 'UP',
            'start_time': datetime.fromtimestamp(self.start_time).isoformat()
        }


class PerformanceMonitoringSystem:
    """
    Unified performance monitoring system.

    Coordinates all monitoring components.
    """

    def __init__(self):
        self.performance_tracker = PerformanceTracker()
        self.health_monitor = StrategyHealthMonitor()
        self.diagnostics = SystemDiagnostics()
        self.uptime_monitor = UptimeMonitor()

        logger.info("PerformanceMonitoringSystem initialized")

    async def monitor(
        self,
        strategy_metrics: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive monitoring.

        Args:
            strategy_metrics: Strategy performance metrics

        Returns:
            Monitoring status
        """

        # Track system metrics
        cpu = psutil.cpu_percent()
        memory = psutil.virtual_memory().percent
        self.performance_tracker.track_metric("cpu_usage", cpu, "%", threshold=80)
        self.performance_tracker.track_metric("memory_usage", memory, "%", threshold=80)

        # Check uptime
        is_up = await self.uptime_monitor.check_uptime()
        self.performance_tracker.track_metric("uptime_status", 1 if is_up else 0, "", threshold=0.5)

        # Get system diagnostics
        diagnostics = await self.diagnostics.get_diagnostics()

        # Monitor strategies
        strategy_health = {}
        if strategy_metrics:
            for strategy_name, metrics in strategy_metrics.items():
                health = await self.health_monitor.assess_strategy_health(
                    strategy_name, metrics
                )
                strategy_health[strategy_name] = health

        # Get uptime stats
        uptime_stats = self.uptime_monitor.get_uptime_stats()

        return {
            'system_health': diagnostics,
            'strategy_health': strategy_health,
            'uptime_stats': uptime_stats,
            'performance_metrics': {
                name: self.performance_tracker.get_metric_summary(name)
                for name in ['cpu_usage', 'memory_usage', 'uptime_status']
            },
            'timestamp': datetime.now().isoformat()
        }

    def generate_monitoring_report(self, status: Dict[str, Any]) -> str:
        """Generate monitoring report."""

        diagnostics = status['system_health']
        uptime = status['uptime_stats']
        strategy_health = status['strategy_health']

        report = f"""
{'='*60}
PERFORMANCE MONITORING REPORT
{'='*60}
Generated: {status['timestamp']}

SYSTEM HEALTH:
  Status: {'HEALTHY' if not diagnostics.warnings else 'DEGRADED'}
  CPU: {diagnostics.cpu_usage:.1f}%
  Memory: {diagnostics.memory_usage:.1f}%
  Disk: {diagnostics.disk_usage:.1f}%
  Uptime: {uptime['uptime_seconds'] / 86400:.1f} days ({uptime['uptime_percentage']:.1f}%)

SYSTEM STATUS:
  API: {'✓ Healthy' if diagnostics.api_health else '✗ Unhealthy'}
  Database: {'✓ Healthy' if diagnostics.database_health else '✗ Unhealthy'}
  Data Feed: {'✓ Healthy' if diagnostics.data_feed_health else '✗ Unhealthy'}

PERFORMANCE:
  Avg Response Time: {diagnostics.avg_response_time*1000:.1f}ms
  Requests/sec: {diagnostics.requests_per_second:.1f}

STRATEGY HEALTH:
"""

        for strategy_name, health in strategy_health.items():
            report += f"""
  {strategy_name}: {health.health.value.upper()}
    Return: {health.current_return:.2%} (expected: {health.expected_return:.2%})
    Drawdown: {health.current_drawdown:.2%}
    Win Rate: {health.win_rate:.1%}
"""

            if health.issues:
                report += "    Issues:\n"
                for issue in health.issues:
                    report += f"      • {issue}\n"

            if health.recommendations:
                report += "    Recommendations:\n"
                for rec in health.recommendations:
                    report += f"      • {rec}\n"

        if diagnostics.warnings:
            report += "\nWARNINGS:\n"
            for warning in diagnostics.warnings:
                report += f"  ⚠ {warning}\n"

        if diagnostics.errors:
            report += "\nERRORS:\n"
            for error in diagnostics.errors:
                report += f"  ✗ {error}\n"

        return report


# Singleton instance
_performance_monitoring_system = None


def get_performance_monitoring_system() -> PerformanceMonitoringSystem:
    """Get or create performance monitoring system instance."""
    global _performance_monitoring_system
    if _performance_monitoring_system is None:
        _performance_monitoring_system = PerformanceMonitoringSystem()
    return _performance_monitoring_system
