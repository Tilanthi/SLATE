#!/usr/bin/env python3
"""
SLATE Orchestration Integration Script
Demonstrates all 5 priority orchestration improvements working together
"""

import asyncio
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add SLATE to path
sys.path.insert(0, str(Path(__file__).parent))

from slate_core.orchestration.event_bus import EventBus, EventType, Event
from slate_core.orchestration.service_mesh import ServiceRegistry, ServiceInstance, ServiceType, ServiceStatus
from slate_core.orchestration.health_monitor import HealthMonitor, HealthStatus, get_health_monitor
from slate_core.orchestration.degradation import GracefulDegradationManager, DegradationLevel
from slate_core.config import get_config_manager, Environment

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SlateOrchestrator:
    """
    Main orchestrator that integrates all orchestration components.

    This class demonstrates how the 5 priority improvements work together:
    1. Event-Driven Architecture
    2. Service Mesh
    3. Unified Configuration
    4. Health Monitoring
    5. Graceful Degradation
    """

    def __init__(self):
        self.event_bus: EventBus = EventBus()
        self.service_registry: ServiceRegistry = ServiceRegistry()
        self.health_monitor: HealthMonitor = HealthMonitor()
        self.degradation_manager: GracefulDegradationManager = GracefulDegradationManager()
        self.config_manager = get_config_manager()

        self.running = False

    async def initialize(self):
        """Initialize all orchestration components."""
        logger.info("=" * 60)
        logger.info("SLATE Orchestration System - Initialization")
        logger.info("=" * 60)

        # 1. Load configuration
        logger.info("\n📋 Priority 3: Loading Configuration...")
        config = self.config_manager.load_config(environment=Environment.DEVELOPMENT)
        logger.info(f"   Environment: {config.environment.value}")
        logger.info(f"   Trading Symbol: {config.trading.default_symbol}")
        logger.info(f"   Initial Capital: ${config.trading.default_initial_capital_usdt:,.0f}")

        # 2. Start event bus
        logger.info("\n📡 Priority 1: Starting Event Bus...")
        await self.event_bus.start()
        logger.info(f"   Event bus started with queue size: {self.event_bus.event_queue.maxsize}")

        # Subscribe to system events
        self.event_bus.subscribe(self._handle_system_event, event_types=[EventType.SYSTEM_ERROR])
        self.event_bus.subscribe(self._handle_strategy_event, event_types=[EventType.STRATEGY_DISCOVERED])

        # 3. Register services
        logger.info("\n🔗 Priority 2: Initializing Service Mesh...")
        await self._register_local_services()
        await self.service_registry.start_health_checks()

        # 4. Setup health monitoring
        logger.info("\n💓 Priority 4: Starting Health Monitoring...")
        await self._setup_health_checks()
        await self.health_monitor.start_monitoring()

        # 5. Setup degradation management
        logger.info("\n🛡️ Priority 5: Configuring Graceful Degradation...")
        await self._setup_fallbacks()

        self.running = True
        logger.info("\n✅ Orchestration system initialized successfully")

    async def _register_local_services(self):
        """Register local services in the service mesh."""
        # Register this orchestrator as a service
        import socket

        service = ServiceInstance(
            instance_id="orchestrator-1",
            service_type=ServiceType.API_SERVER,
            host=socket.gethostname(),
            port=8788,
            status=ServiceStatus.HEALTHY,
            capabilities=["orchestration", "coordination", "monitoring"]
        )

        self.service_registry.register(service)
        logger.info(f"   Registered service: {service.instance_id}")

        # Register data fetcher service
        data_service = ServiceInstance(
            instance_id="data-fetcher-1",
            service_type=ServiceType.DATA_FETCHER,
            host=socket.gethostname(),
            port=8789,
            status=ServiceStatus.HEALTHY,
            capabilities=["binance_api", "caching", "realtime"]
        )

        self.service_registry.register(data_service)
        logger.info(f"   Registered service: {data_service.instance_id}")

    async def _setup_health_checks(self):
        """Setup health monitoring with default checks."""
        from slate_core.orchestration.health_monitor import (
            SystemResourceHealthCheck,
            DatabaseHealthCheck,
            ApiConnectivityHealthCheck,
            DataCacheHealthCheck
        )

        # System resources
        self.health_monitor.register_check(SystemResourceHealthCheck())

        # Database
        self.health_monitor.register_check(DatabaseHealthCheck())

        # API connectivity
        self.health_monitor.register_check(ApiConnectivityHealthCheck())

        # Data cache
        self.health_monitor.register_check(DataCacheHealthCheck())

        # Event bus health
        from slate_core.orchestration.health_monitor import EventHealthCheck
        self.health_monitor.register_check(EventHealthCheck(self.event_bus))

        logger.info(f"   Registered {len(self.health_monitor.checks)} health checks")

    async def _setup_fallbacks(self):
        """Setup fallback strategies."""
        # Setup sample data cache
        data_cache = {}

        await self._setup_fallbacks()
        logger.info("   Fallback chains configured")

    async def _handle_system_event(self, event: Event):
        """Handle system-level events."""
        logger.info(f"📨 System Event: {event.type.value} - {event.data.get('error', 'Unknown')}")

        if event.type == EventType.SYSTEM_ERROR:
            # Could trigger degraded mode, alerts, etc.
            degradation_status = self.degradation_manager.get_degradation_status()
            logger.info(f"   Degradation Level: {degradation_status['degradation_level']}")

    async def _handle_strategy_event(self, event: Event):
        """Handle strategy discovery events."""
        logger.info(f"📨 Strategy Event: {event.type.value} - {event.data.get('strategy_id', 'Unknown')}")

    async def run_demo(self):
        """Run demonstration of orchestration capabilities."""
        logger.info("\n" + "=" * 60)
        logger.info("Running Orchestration Demonstration")
        logger.info("=" * 60)

        # Demo 1: Publish events
        logger.info("\n📡 Demo 1: Publishing Events...")
        await self.event_bus.publish(Event(
            type=EventType.STRATEGY_DISCOVERED,
            data={'strategy_id': 'vi_strategy_001', 'performance': {'sharpe': 1.5}},
            source='demo'
        ))

        await asyncio.sleep(0.5)

        # Demo 2: Service discovery
        logger.info("\n🔗 Demo 2: Service Discovery...")
        services = self.service_registry.discover(ServiceType.DATA_FETCHER)
        logger.info(f"   Found {len(services)} data fetcher services")

        # Demo 3: Health check
        logger.info("\n💓 Demo 3: Health Status...")
        health = await self.health_monitor.check_health()
        logger.info(f"   System Status: {health.status.value}")
        logger.info(f"   Health Checks: {len(health.checks)} performed")

        for check in health.checks:
            status_emoji = "✅" if check.status == HealthStatus.HEALTHY else "⚠️"
            logger.info(f"   {status_emoji} {check.name}: {check.message}")

        # Demo 4: Degradation status
        logger.info("\n🛡️ Demo 4: Degradation Status...")
        degradation = self.degradation_manager.get_degradation_status()
        logger.info(f"   Degradation Level: {degradation['degradation_level']}")
        logger.info(f"   Success Rate: {degradation['success_rate']*100:.1f}%")

        # Demo 5: Event bus statistics
        logger.info("\n📊 Demo 5: Event Bus Statistics...")
        stats = self.event_bus.get_stats()
        logger.info(f"   Events Published: {stats['events_published']}")
        logger.info(f"   Events Processed: {stats['events_processed']}")
        logger.info(f"   Subscribers: {stats['subscriber_count']}")

        logger.info("\n" + "=" * 60)
        logger.info("Orchestration Demonstration Complete")
        logger.info("=" * 60)

    async def shutdown(self):
        """Gracefully shutdown all orchestration components."""
        logger.info("\n🛑 Shutting down orchestration system...")

        # Stop health monitoring
        await self.health_monitor.stop_monitoring()

        # Stop service registry
        await self.service_registry.stop_health_checks()

        # Stop event bus
        await self.event_bus.stop()

        self.running = False

        logger.info("✅ Orchestration system shut down complete")


async def main():
    """Main entry point."""
    orchestrator = SlateOrchestrator()

    try:
        await orchestrator.initialize()
        await orchestrator.run_demo()

        # Keep running for a bit to show continuous operation
        logger.info("\n⏸️  System running. Press Ctrl+C to shutdown...")
        await asyncio.sleep(5)

    except KeyboardInterrupt:
        logger.info("\n⚠️  Shutdown requested by user")
    finally:
        await orchestrator.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
