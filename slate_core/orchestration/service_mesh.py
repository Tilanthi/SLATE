"""
Service Mesh for SLATE
Service discovery, registration, and communication
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import uuid
import aiohttp
import backoff

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Service health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ServiceType(Enum):
    """Types of services in SLATE."""
    DATA_FETCHER = "data_fetcher"
    BACKTEST_ENGINE = "backtest_engine"
    STRATEGY_DISCOVERER = "strategy_discoverer"
    VALIDATOR = "validator"
    MARKET_DATA = "market_data"
    NOTIFIER = "notifier"
    API_SERVER = "api_server"


@dataclass
class ServiceHealth:
    """Health check result."""
    status: ServiceStatus
    last_check: datetime
    response_time_ms: float
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceInstance:
    """Represents a service instance."""
    instance_id: str
    service_type: ServiceType
    host: str
    port: int
    status: ServiceStatus = ServiceStatus.UNKNOWN
    health: Optional[ServiceHealth] = None
    registered_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)

    @property
    def endpoint(self) -> str:
        """Get service endpoint URL."""
        return f"http://{self.host}:{self.port}"

    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        if self.health is None:
            return False

        # Check if health check is recent (within 30 seconds)
        if datetime.utcnow() - self.health.last_check > timedelta(seconds=30):
            return False

        return self.health.status == ServiceStatus.HEALTHY

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'instance_id': self.instance_id,
            'service_type': self.service_type.value,
            'host': self.host,
            'port': self.port,
            'status': self.status.value,
            'registered_at': self.registered_at.isoformat(),
            'last_heartbeat': self.last_heartbeat.isoformat(),
            'metadata': self.metadata,
            'capabilities': self.capabilities,
            'health': {
                'status': self.health.status.value if self.health else None,
                'last_check': self.health.last_check.isoformat() if self.health else None,
                'response_time_ms': self.health.response_time_ms if self.health else None,
                'error_message': self.health.error_message if self.health else None
            } if self.health else None
        }


class ServiceRegistry:
    """
    Service registry for dynamic service discovery.

    Features:
    - Service registration and deregistration
    - Health monitoring
    - Load balancing
    - Service discovery
    """

    def __init__(self, health_check_interval: float = 10.0):
        self.services: Dict[str, ServiceInstance] = {}
        self.service_by_type: Dict[ServiceType, List[str]] = {st: [] for st in ServiceType}
        self.health_check_interval = health_check_interval
        self._health_check_task: Optional[asyncio.Task] = None
        self._running = False

    def register(self, service: ServiceInstance) -> bool:
        """
        Register a new service.

        Parameters:
        - service: Service instance to register

        Returns:
        - True if registered successfully
        """
        if service.instance_id in self.services:
            logger.warning(f"Service {service.instance_id} already registered")
            return False

        self.services[service.instance_id] = service
        self.service_by_type[service.service_type].append(service.instance_id)

        logger.info(f"Registered service {service.instance_id} ({service.service_type.value})")
        return True

    def deregister(self, instance_id: str) -> bool:
        """
        Deregister a service.

        Parameters:
        - instance_id: Service instance ID

        Returns:
        - True if deregistered successfully
        """
        if instance_id not in self.services:
            logger.warning(f"Service {instance_id} not found")
            return False

        service = self.services[instance_id]

        # Remove from type index
        if instance_id in self.service_by_type[service.service_type]:
            self.service_by_type[service.service_type].remove(instance_id)

        # Remove from registry
        del self.services[instance_id]

        logger.info(f"Deregistered service {instance_id}")
        return True

    def discover(
        self,
        service_type: ServiceType,
        healthy_only: bool = True,
        capabilities: Optional[List[str]] = None
    ) -> List[ServiceInstance]:
        """
        Discover services by type.

        Parameters:
        - service_type: Type of service to discover
        - healthy_only: Only return healthy services
        - capabilities: Required capabilities

        Returns:
        - List of matching service instances
        """
        instance_ids = self.service_by_type.get(service_type, [])

        services = []
        for instance_id in instance_ids:
            service = self.services.get(instance_id)
            if service is None:
                continue

            if healthy_only and not service.is_healthy():
                continue

            if capabilities and not all(cap in service.capabilities for cap in capabilities):
                continue

            services.append(service)

        return services

    def get_instance(self, instance_id: str) -> Optional[ServiceInstance]:
        """Get service instance by ID."""
        return self.services.get(instance_id)

    async def heartbeat(self, instance_id: str) -> bool:
        """
        Receive heartbeat from service.

        Parameters:
        - instance_id: Service instance ID

        Returns:
        - True if heartbeat processed successfully
        """
        service = self.services.get(instance_id)
        if service is None:
            logger.warning(f"Heartbeat from unknown service {instance_id}")
            return False

        service.last_heartbeat = datetime.utcnow()
        return True

    async def health_check(self, instance_id: str) -> ServiceHealth:
        """
        Perform health check on service.

        Parameters:
        - instance_id: Service instance ID

        Returns:
        - Health check result
        """
        service = self.services.get(instance_id)
        if service is None:
            return ServiceHealth(
                status=ServiceStatus.UNKNOWN,
                last_check=datetime.utcnow(),
                response_time_ms=0,
                error_message="Service not found"
            )

        start_time = datetime.utcnow()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{service.endpoint}/health",
                    timeout=aiohttp.ClientTimeout(total=5.0)
                ) as response:
                    response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                    if response.status == 200:
                        health_data = await response.json()

                        service.health = ServiceHealth(
                            status=ServiceStatus.HEALTHY,
                            last_check=datetime.utcnow(),
                            response_time_ms=response_time,
                            metadata=health_data
                        )
                        service.status = ServiceStatus.HEALTHY
                    else:
                        service.health = ServiceHealth(
                            status=ServiceStatus.UNHEALTHY,
                            last_check=datetime.utcnow(),
                            response_time_ms=response_time,
                            error_message=f"HTTP {response.status}"
                        )
                        service.status = ServiceStatus.UNHEALTHY

        except asyncio.TimeoutError:
            service.health = ServiceHealth(
                status=ServiceStatus.UNHEALTHY,
                last_check=datetime.utcnow(),
                response_time_ms=5000,
                error_message="Health check timeout"
            )
            service.status = ServiceStatus.UNHEALTHY

        except Exception as e:
            service.health = ServiceHealth(
                status=ServiceStatus.UNHEALTHY,
                last_check=datetime.utcnow(),
                response_time_ms=0,
                error_message=str(e)
            )
            service.status = ServiceStatus.UNHEALTHY

        return service.health

    async def start_health_checks(self):
        """Start background health checking."""
        if self._running:
            return

        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("Service registry health checks started")

    async def stop_health_checks(self):
        """Stop background health checking."""
        if not self._running:
            return

        self._running = False

        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        logger.info("Service registry health checks stopped")

    async def _health_check_loop(self):
        """Health check loop."""
        while self._running:
            try:
                for instance_id in list(self.services.keys()):
                    await self.health_check(instance_id)

                await asyncio.sleep(self.health_check_interval)
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(1.0)

    def get_stats(self) -> Dict:
        """Get registry statistics."""
        total_services = len(self.services)
        healthy_services = sum(1 for s in self.services.values() if s.is_healthy())

        return {
            'total_services': total_services,
            'healthy_services': healthy_services,
            'unhealthy_services': total_services - healthy_services,
            'services_by_type': {
                st.value: len(self.service_by_type[st])
                for st in ServiceType
            }
        }


class ServiceMeshClient:
    """
    Client for communicating through the service mesh.

    Features:
    - Automatic service discovery
    - Load balancing
    - Retry logic with exponential backoff
    - Circuit breaker pattern
    """

    def __init__(self, registry: ServiceRegistry):
        self.registry = registry
        self.circuit_breakers: Dict[str, float] = {}
        self.circuit_breaker_threshold = 0.5
        self.circuit_breaker_timeout = 60.0
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, asyncio.TimeoutError),
        max_tries=3,
        max_time=30
    )
    async def call_service(
        self,
        service_type: ServiceType,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: float = 30.0
    ) -> Dict:
        """
        Call a service through the service mesh.

        Parameters:
        - service_type: Type of service to call
        - endpoint: API endpoint
        - method: HTTP method
        - data: Request data
        - headers: Request headers
        - timeout: Request timeout

        Returns:
        - Response data
        """
        # Discover healthy services
        services = await self._discover_services(service_type)

        if not services:
            raise Exception(f"No healthy {service_type.value} services available")

        # Load balance (simple round-robin would be implemented here)
        service = services[0]

        # Check circuit breaker
        if self._is_circuit_open(service.instance_id):
            raise Exception(f"Circuit breaker open for {service.instance_id}")

        # Make request
        url = f"{service.endpoint}{endpoint}"

        try:
            async with self.session.request(
                method,
                url,
                json=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                result = await response.json()

                # Update circuit breaker on success
                self._update_circuit_breaker(service.instance_id, success=True)

                return result

        except Exception as e:
            # Update circuit breaker on failure
            self._update_circuit_breaker(service.instance_id, success=False)
            raise

    async def _discover_services(self, service_type: ServiceType) -> List[ServiceInstance]:
        """Discover services with fallback logic."""
        services = self.registry.discover(service_type, healthy_only=True)

        if not services:
            # Fallback to unhealthy services if no healthy ones
            services = self.registry.discover(service_type, healthy_only=False)

        return services

    def _is_circuit_open(self, instance_id: str) -> bool:
        """Check if circuit breaker is open for service."""
        if instance_id not in self.circuit_breakers:
            return False

        failure_rate = self.circuit_breakers[instance_id]
        return failure_rate > self.circuit_breaker_threshold

    def _update_circuit_breaker(self, instance_id: str, success: bool):
        """Update circuit breaker state."""
        if instance_id not in self.circuit_breakers:
            self.circuit_breakers[instance_id] = 0.0

        if success:
            # Decay failure rate on success
            self.circuit_breakers[instance_id] *= 0.9
        else:
            # Increase failure rate on failure
            self.circuit_breakers[instance_id] = min(
                self.circuit_breakers[instance_id] + 0.1,
                1.0
            )


# Global service registry instance
_global_registry: Optional[ServiceRegistry] = None


def get_service_registry() -> ServiceRegistry:
    """Get the global service registry instance."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ServiceRegistry()
    return _global_registry


async def register_local_service(
    service_type: ServiceType,
    port: int,
    capabilities: Optional[List[str]] = None
) -> str:
    """
    Register the current process as a service.

    Parameters:
    - service_type: Type of service
    - port: Port number
    - capabilities: Service capabilities

    Returns:
    - Instance ID
    """
    import socket

    registry = get_service_registry()

    instance_id = str(uuid.uuid4())
    hostname = socket.gethostname()

    service = ServiceInstance(
        instance_id=instance_id,
        service_type=service_type,
        host=hostname,
        port=port,
        capabilities=capabilities or []
    )

    registry.register(service)
    return instance_id
