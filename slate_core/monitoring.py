"""
SLATE Health Monitor

System health monitoring and metrics collection.
"""

import logging
import psutil
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ComponentStatus(Enum):
    """Component health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health status of a component."""
    name: str
    status: ComponentStatus
    message: str
    last_check: datetime
    metrics: Dict[str, Any] = field(default_factory=dict)


class HealthMonitor:
    """Monitor system health and component status."""

    def __init__(self):
        self.components: Dict[str, ComponentHealth] = {}
        self.start_time = datetime.now()

    async def initialize(self):
        """Initialize health monitoring."""
        logger.info("Health Monitor initialized")

    async def get_health_summary(self) -> Dict:
        """Get overall system health summary."""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # Determine overall status
        component_statuses = [c.status for c in self.components.values()]
        if ComponentStatus.UNHEALTHY in component_statuses:
            overall = "unhealthy"
        elif ComponentStatus.DEGRADED in component_statuses:
            overall = "degraded"
        elif not self.components:
            overall = "starting"
        else:
            overall = "healthy"

        return {
            "status": overall,
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": memory.available / (1024**3),
                "disk_percent": disk.percent,
                "disk_free_gb": disk.free / (1024**3)
            },
            "components_count": len(self.components),
            "timestamp": datetime.now().isoformat()
        }

    async def get_component_status(self) -> Dict[str, Dict]:
        """Get status of all components."""
        return {
            name: {
                "status": comp.status.value,
                "message": comp.message,
                "last_check": comp.last_check.isoformat(),
                "metrics": comp.metrics
            }
            for name, comp in self.components.items()
        }

    def update_component(
        self,
        name: str,
        status: ComponentStatus,
        message: str,
        metrics: Optional[Dict] = None
    ):
        """Update component health status."""
        self.components[name] = ComponentHealth(
            name=name,
            status=status,
            message=message,
            last_check=datetime.now(),
            metrics=metrics or {}
        )


class MetricsCollector:
    """Collect system and trading metrics."""

    def __init__(self):
        self.running = False
        self.metrics: Dict[str, List] = {}
        self.start_time = None

    async def start(self):
        """Start metrics collection."""
        self.running = True
        self.start_time = datetime.now()
        logger.info("Metrics Collector started")

    async def stop(self):
        """Stop metrics collection."""
        self.running = False
        logger.info("Metrics Collector stopped")

    async def get_metrics(self) -> Dict:
        """Get current metrics."""
        return {
            "running": self.running,
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds() if self.start_time else 0,
            "metrics_count": len(self.metrics),
            "timestamp": datetime.now().isoformat()
        }

    async def get_performance_metrics(self) -> Dict:
        """Get detailed performance metrics."""
        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_io": psutil.disk_io_counters()._asdict() if psutil.disk_io_counters() else {},
            "network_io": psutil.net_io_counters()._asdict() if psutil.net_io_counters() else {},
            "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
            "timestamp": datetime.now().isoformat()
        }

    def record_metric(self, name: str, value: Any):
        """Record a metric value."""
        if name not in self.metrics:
            self.metrics[name] = []

        self.metrics[name].append({
            "value": value,
            "timestamp": datetime.now().isoformat()
        })

        # Keep only last 1000 values
        if len(self.metrics[name]) > 1000:
            self.metrics[name] = self.metrics[name][-1000:]
