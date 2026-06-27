"""
SLATE Autonomous Resource Manager

Monitors and manages CPU, memory, and time resources for autonomous operations.
Implements throttling and resource constraint enforcement per safety constraints.
"""

import logging
import psutil
import threading
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from collections import deque

from .config import AutonomousConfig, ResourceStatus

logger = logging.getLogger(__name__)


class ResourceManager:
    """
    Manage resources for autonomous SLATE operations.

    This enforces the safety constraints around CPU, memory, and time usage
    to prevent autonomous operations from overwhelming the system.

    SAFETY CONSTRAINTS:
    - Maximum CPU usage: 15% (configurable)
    - Maximum memory usage: 20% (configurable)
    - Maximum weekly hours: 168 hours (configurable)
    - Automatic throttling when limits approached
    """

    def __init__(self, config: AutonomousConfig):
        """
        Initialize resource manager.

        Args:
            config: Autonomous configuration with resource limits
        """
        self.config = config

        # Resource monitoring
        self.cpu_history = deque(maxlen=60)  # Last 60 measurements
        self.memory_history = deque(maxlen=60)
        self.throttling_active = False

        # Time tracking
        self.session_start_time = datetime.now()
        self.weekly_start_time = datetime.now()
        self.weekly_usage_hours = 0.0
        self.active_operation_time = 0.0

        # Monitoring thread
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None

        logger.info("Resource Manager initialized with limits: "
                   f"CPU={self.config.max_cpu_percent}%, "
                   f"Memory={self.config.max_memory_percent}%, "
                   f"Time={self.config.max_hours_per_week}h/week")

    def start_monitoring(self):
        """Start continuous resource monitoring in background thread"""
        if self.monitoring_active:
            logger.warning("Resource monitoring already active")
            return

        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Resource monitoring started")

    def stop_monitoring(self):
        """Stop resource monitoring"""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
        logger.info("Resource monitoring stopped")

    def _monitor_loop(self):
        """Background monitoring loop"""
        while self.monitoring_active:
            try:
                # Sample current resource usage
                cpu_percent = psutil.cpu_percent(interval=1.0)
                memory_percent = psutil.virtual_memory().percent

                # Store in history
                self.cpu_history.append(cpu_percent)
                self.memory_history.append(memory_percent)

                # Check if we need to throttle
                self._update_throttling_status()

                # Small sleep to avoid overwhelming CPU
                time.sleep(2.0)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5.0)

    def _update_throttling_status(self):
        """Update throttling status based on current usage"""
        if not self.cpu_history or not self.memory_history:
            return

        avg_cpu = sum(self.cpu_history) / len(self.cpu_history)
        avg_memory = sum(self.memory_history) / len(self.memory_history)

        # Throttle if approaching limits (> 80% of max)
        cpu_approaching = avg_cpu > (self.config.max_cpu_percent * 0.8)
        memory_approaching = avg_memory > (self.config.max_memory_percent * 0.8)

        was_throttling = self.throttling_active
        self.throttling_active = cpu_approaching or memory_approaching

        if self.throttling_active and not was_throttling:
            logger.warning(f"Throttling activated - CPU: {avg_cpu:.1f}%, Memory: {avg_memory:.1f}%")
        elif not self.throttling_active and was_throttling:
            logger.info("Throttling deactivated")

    def can_start_operation(self, estimated_cost: Optional[Dict[str, Any]] = None) -> bool:
        """
        Check if we have resources to start a new operation.

        Args:
            estimated_cost: Optional estimated resource cost {'cpu_percent': float, 'duration_seconds': float}

        Returns:
            True if operation can proceed, False otherwise
        """
        status = self.get_status()

        # Don't start if already at limits
        if status.approaching_limits:
            logger.debug("Cannot start operation - approaching resource limits")
            return False

        # Check if we have enough weekly time budget
        if status.weekly_hours_used >= self.config.max_hours_per_week:
            logger.warning("Cannot start operation - weekly time limit reached")
            return False

        # If we have an estimate, check if it fits
        if estimated_cost:
            estimated_cpu = estimated_cost.get('cpu_percent', 10.0)
            estimated_duration = estimated_cost.get('duration_seconds', 60.0)
            estimated_hours = (estimated_duration / 3600.0)

            # Would this put us over limits?
            if (status.cpu_percent + estimated_cpu) > self.config.max_cpu_percent:
                logger.debug(f"Cannot start operation - would exceed CPU limit: "
                           f"{status.cpu_percent + estimated_cpu:.1f}% > {self.config.max_cpu_percent}%")
                return False

            if (status.weekly_hours_used + estimated_hours) > self.config.max_hours_per_week:
                logger.debug(f"Cannot start operation - would exceed time limit")
                return False

        return True

    def record_operation_time(self, duration_seconds: float):
        """
        Record time spent on an autonomous operation.

        Args:
            duration_seconds: Time spent on operation in seconds
        """
        hours = duration_seconds / 3600.0
        self.active_operation_time += hours
        self.weekly_usage_hours += hours

        # Reset weekly counter if we've crossed a week boundary
        now = datetime.now()
        if (now - self.weekly_start_time) > timedelta(days=7):
            logger.info(f"Week reset - previous week used {self.weekly_usage_hours:.2f} hours")
            self.weekly_start_time = now
            self.weekly_usage_hours = 0.0

    def get_status(self) -> ResourceStatus:
        """
        Get current resource status.

        Returns:
            ResourceStatus with current usage and throttling state
        """
        # Calculate current averages
        avg_cpu = 0.0
        avg_memory = 0.0

        if self.cpu_history:
            avg_cpu = sum(self.cpu_history) / len(self.cpu_history)
        if self.memory_history:
            avg_memory = sum(self.memory_history) / len(self.memory_history)

        # Check if approaching limits
        cpu_approaching = avg_cpu > (self.config.max_cpu_percent * 0.8)
        memory_approaching = avg_memory > (self.config.max_memory_percent * 0.8)
        time_approaching = self.weekly_usage_hours > (self.config.max_hours_per_week * 0.8)

        approaching_limits = cpu_approaching or memory_approaching or time_approaching

        return ResourceStatus(
            cpu_percent=avg_cpu,
            memory_percent=avg_memory,
            weekly_hours_used=self.weekly_usage_hours,
            approaching_limits=approaching_limits,
            throttling_active=self.throttling_active
        )

    def get_resource_recommendation(self) -> Dict[str, Any]:
        """
        Get recommendation for current resource state.

        Returns:
            Dict with recommendation on how to proceed
        """
        status = self.get_status()

        if status.throttling_active:
            return {
                'action': 'wait',
                'reason': 'Throttling active - resource usage high',
                'wait_seconds': 30,
                'can_proceed': False
            }

        if status.approaching_limits:
            return {
                'action': 'caution',
                'reason': 'Approaching resource limits',
                'can_proceed': True,
                'recommendation': 'Use lighter operations or wait'
            }

        if status.weekly_hours_used >= self.config.max_hours_per_week:
            return {
                'action': 'stop',
                'reason': 'Weekly time limit reached',
                'can_proceed': False,
                'recommendation': 'Wait for weekly reset or increase limits'
            }

        return {
            'action': 'proceed',
            'reason': 'Resources available',
            'can_proceed': True,
            'recommendation': 'Normal operation'
        }

    def get_usage_report(self) -> str:
        """
        Get human-readable resource usage report.

        Returns:
            Formatted string with current usage statistics
        """
        status = self.get_status()
        session_duration = (datetime.now() - self.session_start_time).total_seconds() / 3600.0

        report = f"""
Resource Usage Report
=====================
Current Status:
- CPU: {status.cpu_percent:.1f}% (max: {self.config.max_cpu_percent}%)
- Memory: {status.memory_percent:.1f}% (max: {self.config.max_memory_percent}%)
- Weekly Time: {status.weekly_hours_used:.2f}h (max: {self.config.max_hours_per_week}h)

Session Statistics:
- Session Duration: {session_duration:.2f} hours
- Active Operation Time: {self.active_operation_time:.2f} hours
- Utilization: {(self.active_operation_time / session_duration * 100):.1f}%

Status: {'⚠️ THROTTLING' if status.throttling_active else '✅ Normal'}
        """.strip()

        return report