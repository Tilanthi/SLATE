"""
Health Monitoring System for SLATE
Comprehensive health checks for all system components
"""

import asyncio
import logging
import psutil
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import numpy as np

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    name: str
    status: HealthStatus
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    response_time_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'status': self.status.value,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'response_time_ms': self.response_time_ms,
            'details': self.details,
            'metrics': self.metrics
        }


@dataclass
class SystemHealth:
    """Overall system health."""
    status: HealthStatus
    checks: List[HealthCheckResult] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    uptime_seconds: float = 0.0

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'status': self.status.value,
            'timestamp': self.timestamp.isoformat(),
            'uptime_seconds': self.uptime_seconds,
            'checks': [check.to_dict() for check in self.checks],
            'check_count': len(self.checks),
            'healthy_count': sum(1 for c in self.checks if c.status == HealthStatus.HEALTHY),
            'degraded_count': sum(1 for c in self.checks if c.status == HealthStatus.DEGRADED),
            'unhealthy_count': sum(1 for c in self.checks if c.status == HealthStatus.UNHEALTHY),
            'critical_count': sum(1 for c in self.checks if c.status == HealthStatus.CRITICAL)
        }


class HealthCheck:
    """Base health check class."""

    def __init__(self, name: str, timeout: float = 5.0):
        self.name = name
        self.timeout = timeout
        self.last_check: Optional[datetime] = None
        self.consecutive_failures = 0
        self.enabled = True

    async def check(self) -> HealthCheckResult:
        """
        Execute health check.

        Returns:
        - Health check result
        """
        if not self.enabled:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message="Health check disabled"
            )

        start_time = datetime.utcnow()

        try:
            result = await asyncio.wait_for(
                self.execute_check(),
                timeout=self.timeout
            )

            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            self.last_check = datetime.utcnow()
            self.consecutive_failures = 0

            return HealthCheckResult(
                name=self.name,
                status=result['status'],
                message=result['message'],
                response_time_ms=response_time,
                details=result.get('details', {}),
                metrics=result.get('metrics', {})
            )

        except asyncio.TimeoutError:
            self.consecutive_failures += 1
            self.last_check = datetime.utcnow()

            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check timeout after {self.timeout}s",
                response_time_ms=self.timeout * 1000
            )

        except Exception as e:
            self.consecutive_failures += 1
            self.last_check = datetime.utcnow()

            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                response_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
            )

    async def execute_check(self) -> Dict:
        """
        Execute the actual health check logic.

        Returns:
        - Dict with 'status', 'message', 'details', 'metrics'
        """
        raise NotImplementedError("Subclasses must implement execute_check()")


class SystemResourceHealthCheck(HealthCheck):
    """Check system resources (CPU, memory, disk)."""

    def __init__(self, cpu_threshold: float = 80.0, memory_threshold: float = 85.0, disk_threshold: float = 90.0):
        super().__init__("system_resources")
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
        self.disk_threshold = disk_threshold

    async def execute_check(self) -> Dict:
        """Check system resource usage."""
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)

        # Memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent

        # Disk usage
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent

        # Determine overall status
        status = HealthStatus.HEALTHY
        issues = []

        if cpu_percent > self.cpu_threshold:
            status = HealthStatus.UNHEALTHY
            issues.append(f"High CPU usage: {cpu_percent:.1f}%")

        if memory_percent > self.memory_threshold:
            status = HealthStatus.UNHEALTHY
            issues.append(f"High memory usage: {memory_percent:.1f}%")

        if disk_percent > self.disk_threshold:
            status = HealthStatus.CRITICAL
            issues.append(f"High disk usage: {disk_percent:.1f}%")

        message = "System resources OK" if not issues else "; ".join(issues)

        return {
            'status': status,
            'message': message,
            'details': {
                'cpu_cores': psutil.cpu_count(),
                'memory_total_gb': memory.total / (1024**3),
                'memory_available_gb': memory.available / (1024**3),
                'disk_total_gb': disk.total / (1024**3),
                'disk_free_gb': disk.free / (1024**3)
            },
            'metrics': {
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                'disk_percent': disk_percent
            }
        }


class DatabaseHealthCheck(HealthCheck):
    """Check database connectivity and performance."""

    def __init__(self, db_path: str = "slate_core/slate_realistic_discoveries.db"):
        super().__init__("database")
        self.db_path = db_path

    async def execute_check(self) -> Dict:
        """Check database health."""
        try:
            import sqlite3
            import os

            # Check if database file exists
            if not os.path.exists(self.db_path):
                return {
                    'status': HealthStatus.CRITICAL,
                    'message': f"Database file not found: {self.db_path}",
                    'details': {'db_path': self.db_path}
                }

            # Check database file size
            file_size = os.path.getsize(self.db_path)
            file_size_mb = file_size / (1024 * 1024)

            # Try to connect and query
            start_time = datetime.utcnow()

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Test query
            cursor.execute("SELECT COUNT(*) FROM sqlite_master")
            table_count = cursor.fetchone()[0]

            # Check database integrity
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()[0]

            conn.close()

            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            if integrity_result != "ok":
                return {
                    'status': HealthStatus.CRITICAL,
                    'message': f"Database integrity check failed: {integrity_result}",
                    'details': {'integrity_result': integrity_result}
                }

            return {
                'status': HealthStatus.HEALTHY,
                'message': "Database healthy",
                'details': {
                    'db_path': self.db_path,
                    'table_count': table_count,
                    'file_size_mb': file_size_mb
                },
                'metrics': {
                    'response_time_ms': response_time
                }
            }

        except Exception as e:
            return {
                'status': HealthStatus.CRITICAL,
                'message': f"Database check failed: {str(e)}",
                'details': {'error': str(e)}
            }


class ApiConnectivityHealthCheck(HealthCheck):
    """Check external API connectivity."""

    def __init__(self, api_url: str = "https://api.binance.com/api/v3/ping"):
        super().__init__("api_connectivity")
        self.api_url = api_url

    async def execute_check(self) -> Dict:
        """Check API connectivity."""
        try:
            start_time = datetime.utcnow()

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.api_url,
                    timeout=aiohttp.ClientTimeout(total=5.0)
                ) as response:
                    response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                    if response.status == 200:
                        return {
                            'status': HealthStatus.HEALTHY,
                            'message': "API reachable",
                            'details': {'api_url': self.api_url},
                            'metrics': {
                                'response_time_ms': response_time
                            }
                        }
                    else:
                        return {
                            'status': HealthStatus.UNHEALTHY,
                            'message': f"API returned status {response.status}",
                            'details': {'api_url': self.api_url, 'status': response.status}
                        }

        except asyncio.TimeoutError:
            return {
                'status': HealthStatus.UNHEALTHY,
                'message': "API timeout",
                'details': {'api_url': self.api_url}
            }

        except Exception as e:
            return {
                'status': HealthStatus.UNHEALTHY,
                'message': f"API check failed: {str(e)}",
                'details': {'error': str(e)}
            }


class DataCacheHealthCheck(HealthCheck):
    """Check data cache status."""

    def __init__(self, cache_dir: str = "sol_data_cache"):
        super().__init__("data_cache")
        self.cache_dir = cache_dir

    async def execute_check(self) -> Dict:
        """Check data cache health."""
        try:
            import os
            from pathlib import Path

            cache_path = Path(self.cache_dir)

            # Check if cache directory exists
            if not cache_path.exists():
                return {
                    'status': HealthStatus.HEALTHY,
                    'message': "Cache directory not created yet",
                    'details': {'cache_dir': self.cache_dir}
                }

            # Count cached files
            cache_files = list(cache_path.glob("*.csv"))
            cache_count = len(cache_files)

            # Calculate total cache size
            total_size = sum(f.stat().st_size for f in cache_files)
            total_size_mb = total_size / (1024 * 1024)

            # Check for stale cache (files older than 7 days)
            now = datetime.utcnow()
            stale_threshold = timedelta(days=7)
            stale_files = []

            for cache_file in cache_files:
                mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
                if now - mtime > stale_threshold:
                    stale_files.append(cache_file.name)

            # Determine status
            if cache_count == 0:
                status = HealthStatus.HEALTHY
                message = "No cached data"
            elif len(stale_files) > cache_count / 2:
                status = HealthStatus.DEGRADED
                message = f"Many stale cache files: {len(stale_files)}/{cache_count}"
            else:
                status = HealthStatus.HEALTHY
                message = f"Cache healthy: {cache_count} files"

            return {
                'status': status,
                'message': message,
                'details': {
                    'cache_dir': self.cache_dir,
                    'cache_count': cache_count,
                    'stale_files': len(stale_files)
                },
                'metrics': {
                    'cache_size_mb': total_size_mb,
                    'stale_percentage': len(stale_files) / cache_count if cache_count > 0 else 0
                }
            }

        except Exception as e:
            return {
                'status': HealthStatus.UNHEALTHY,
                'message': f"Cache check failed: {str(e)}",
                'details': {'error': str(e)}
            }


class EventHealthCheck(HealthCheck):
    """Check event bus health."""

    def __init__(self, event_bus):
        super().__init__("event_bus")
        self.event_bus = event_bus

    async def execute_check(self) -> Dict:
        """Check event bus health."""
        try:
            stats = self.event_bus.get_stats()

            # Determine status based on queue sizes
            queue_size = stats['queue_size']
            dead_letter_size = stats['dead_letter_queue_size']

            if queue_size > 5000:
                status = HealthStatus.CRITICAL
                message = f"Event queue overloaded: {queue_size} events"
            elif dead_letter_size > 100:
                status = HealthStatus.UNHEALTHY
                message = f"Many failed events: {dead_letter_size} in dead letter queue"
            elif queue_size > 1000:
                status = HealthStatus.DEGRADED
                message = f"Event queue busy: {queue_size} events"
            else:
                status = HealthStatus.HEALTHY
                message = "Event bus healthy"

            return {
                'status': status,
                'message': message,
                'details': {
                    'subscriber_count': stats['subscriber_count']
                },
                'metrics': {
                    'queue_size': queue_size,
                    'dead_letter_queue_size': dead_letter_size,
                    'events_published': stats['events_published'],
                    'events_processed': stats['events_processed'],
                    'events_failed': stats['events_failed']
                }
            }

        except Exception as e:
            return {
                'status': HealthStatus.UNHEALTHY,
                'message': f"Event bus check failed: {str(e)}",
                'details': {'error': str(e)}
            }


class HealthMonitor:
    """
    Comprehensive health monitoring system.

    Features:
    - Multiple health checks
    - Periodic health monitoring
    - Health status aggregation
    - Alert generation
    - Historical health tracking
    """

    def __init__(self, check_interval: float = 30.0):
        self.checks: List[HealthCheck] = []
        self.check_interval = check_interval
        self.health_history: List[SystemHealth] = []
        self.max_history = 100
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        self.start_time = datetime.utcnow()

        # Alert callbacks
        self.alert_callbacks: List[Callable[[SystemHealth], None]] = []

    def register_check(self, check: HealthCheck):
        """Register a health check."""
        self.checks.append(check)
        logger.info(f"Registered health check: {check.name}")

    def unregister_check(self, name: str):
        """Unregister a health check by name."""
        self.checks = [c for c in self.checks if c.name != name]
        logger.info(f"Unregistered health check: {name}")

    def register_alert_callback(self, callback: Callable[[SystemHealth], None]):
        """Register an alert callback."""
        self.alert_callbacks.append(callback)

    async def check_health(self) -> SystemHealth:
        """
        Execute all health checks and aggregate results.

        Returns:
        - Overall system health
        """
        check_results = []

        for check in self.checks:
            try:
                result = await check.check()
                check_results.append(result)
            except Exception as e:
                logger.error(f"Health check {check.name} failed: {e}")
                check_results.append(HealthCheckResult(
                    name=check.name,
                    status=HealthStatus.CRITICAL,
                    message=f"Health check execution failed: {str(e)}"
                ))

        # Determine overall status
        overall_status = self._aggregate_status(check_results)

        # Calculate uptime
        uptime = (datetime.utcnow() - self.start_time).total_seconds()

        system_health = SystemHealth(
            status=overall_status,
            checks=check_results,
            uptime_seconds=uptime
        )

        # Add to history
        self.health_history.append(system_health)
        if len(self.health_history) > self.max_history:
            self.health_history.pop(0)

        # Trigger alerts if needed
        if overall_status in [HealthStatus.UNHEALTHY, HealthStatus.CRITICAL]:
            await self._trigger_alerts(system_health)

        return system_health

    def _aggregate_status(self, results: List[HealthCheckResult]) -> HealthStatus:
        """Aggregate individual check results into overall status."""
        if not results:
            return HealthStatus.HEALTHY

        # Priority: CRITICAL > UNHEALTHY > DEGRADED > HEALTHY
        if any(r.status == HealthStatus.CRITICAL for r in results):
            return HealthStatus.CRITICAL
        elif any(r.status == HealthStatus.UNHEALTHY for r in results):
            return HealthStatus.UNHEALTHY
        elif any(r.status == HealthStatus.DEGRADED for r in results):
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

    async def _trigger_alerts(self, health: SystemHealth):
        """Trigger alert callbacks."""
        for callback in self.alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(health)
                else:
                    callback(health)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

    async def start_monitoring(self):
        """Start periodic health monitoring."""
        if self._running:
            logger.warning("Health monitor already running")
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Health monitoring started")

    async def stop_monitoring(self):
        """Stop periodic health monitoring."""
        if not self._running:
            return

        self._running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("Health monitoring stopped")

    async def _monitor_loop(self):
        """Health monitoring loop."""
        while self._running:
            try:
                await self.check_health()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in health monitor loop: {e}")
                await asyncio.sleep(1.0)

    def get_health_summary(self) -> Dict:
        """Get summary of current health status."""
        if not self.health_history:
            return {
                'status': 'unknown',
                'message': 'No health checks performed yet'
            }

        latest_health = self.health_history[-1]

        return {
            'overall_status': latest_health.status.value,
            'uptime_hours': latest_health.uptime_seconds / 3600,
            'check_count': len(latest_health.checks),
            'healthy_checks': sum(1 for c in latest_health.checks if c.status == HealthStatus.HEALTHY),
            'unhealthy_checks': sum(1 for c in latest_health.checks if c.status != HealthStatus.HEALTHY),
            'last_check': latest_health.timestamp.isoformat()
        }


# Global health monitor instance
_global_health_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    """Get the global health monitor instance."""
    global _global_health_monitor
    if _global_health_monitor is None:
        _global_health_monitor = HealthMonitor()
    return _global_health_monitor


async def setup_default_health_checks(event_bus=None):
    """Setup default health checks for SLATE."""
    monitor = get_health_monitor()

    # System resources check
    monitor.register_check(SystemResourceHealthCheck())

    # Database check
    monitor.register_check(DatabaseHealthCheck())

    # API connectivity check
    monitor.register_check(ApiConnectivityHealthCheck())

    # Data cache check
    monitor.register_check(DataCacheHealthCheck())

    # Event bus check (if available)
    if event_bus:
        monitor.register_check(EventHealthCheck(event_bus))

    logger.info("Default health checks registered")
