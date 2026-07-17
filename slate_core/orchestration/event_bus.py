"""
Event-Driven Architecture for SLATE
Async event bus for decoupled component communication
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import uuid

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Standard event types in SLATE."""
    # Strategy events
    STRATEGY_DISCOVERED = "strategy.discovered"
    STRATEGY_VALIDATED = "strategy.validated"
    STRATEGY_DEPLOYED = "strategy.deployed"
    STRATEGY_FAILED = "strategy.failed"
    STRATEGY_PAUSED = "strategy.paused"
    STRATEGY_RESUMED = "strategy.resumed"

    # Data events
    DATA_FETCHED = "data.fetched"
    DATA_CACHED = "data.cached"
    DATA_VALIDATED = "data.validated"

    # Backtest events
    BACKTEST_STARTED = "backtest.started"
    BACKTEST_COMPLETED = "backtest.completed"
    BACKTEST_FAILED = "backtest.failed"

    # Market events
    MARKET_TICK = "market.tick"
    MARKET_VOLATILITY_SPIKE = "market.volatility_spike"
    MARKET_REGIME_CHANGE = "market.regime_change"

    # System events
    SYSTEM_ERROR = "system.error"
    SYSTEM_WARNING = "system.warning"
    SYSTEM_SHUTDOWN = "system.shutdown"


@dataclass
class Event:
    """Base event class."""
    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = "unknown"
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert event to dictionary for serialization."""
        return {
            'type': self.type.value,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'event_id': self.event_id,
            'source': self.source,
            'correlation_id': self.correlation_id,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Event':
        """Create event from dictionary."""
        return cls(
            type=EventType(data['type']),
            data=data.get('data', {}),
            timestamp=datetime.fromisoformat(data['timestamp']),
            event_id=data['event_id'],
            source=data.get('source', 'unknown'),
            correlation_id=data.get('correlation_id'),
            metadata=data.get('metadata', {})
        )


T = TypeVar('T')


class EventSubscriber:
    """Event subscriber with filtering and transformation capabilities."""

    def __init__(
        self,
        handler: Callable[[Event], T],
        event_types: Optional[List[EventType]] = None,
        filter_func: Optional[Callable[[Event], bool]] = None,
        transform_func: Optional[Callable[[Event], Event]] = None
    ):
        self.handler = handler
        self.event_types = set(event_types or [])
        self.filter_func = filter_func
        self.transform_func = transform_func

    def should_process(self, event: Event) -> bool:
        """Check if subscriber should process this event."""
        if self.event_types and event.type not in self.event_types:
            return False

        if self.filter_func and not self.filter_func(event):
            return False

        return True

    async def process(self, event: Event) -> T:
        """Process event through transformation pipeline."""
        if self.transform_func:
            event = self.transform_func(event)

        if asyncio.iscoroutinefunction(self.handler):
            return await self.handler(event)
        else:
            return self.handler(event)


class EventBus:
    """
    Asynchronous event bus for decoupled communication.

    Features:
    - Publish-subscribe pattern
    - Event filtering and transformation
    - Async processing
    - Dead letter queue for failed events
    - Event replay for debugging
    """

    def __init__(self, max_queue_size: int = 10000):
        self.subscribers: Dict[EventType, List[EventSubscriber]] = defaultdict(list)
        self.global_subscribers: List[EventSubscriber] = []
        self.event_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self.dead_letter_queue: asyncio.Queue = asyncio.Queue()
        self.event_history: List[Event] = []
        self.max_history = 1000
        self._running = False
        self._processor_task: Optional[asyncio.Task] = None

        # Event statistics
        self.stats = {
            'events_published': 0,
            'events_processed': 0,
            'events_failed': 0,
            'subscribers_notified': 0
        }

    def subscribe(
        self,
        handler: Callable[[Event], Any],
        event_types: Optional[List[EventType]] = None,
        filter_func: Optional[Callable[[Event], bool]] = None,
        transform_func: Optional[Callable[[Event], Event]] = None
    ) -> str:
        """
        Subscribe to events.

        Parameters:
        - handler: Function to call when event occurs
        - event_types: List of event types to subscribe to (None = all)
        - filter_func: Optional function to filter events
        - transform_func: Optional function to transform events before handling

        Returns:
        - Subscription ID
        """
        subscriber = EventSubscriber(handler, event_types, filter_func, transform_func)
        subscriber_id = str(uuid.uuid4())
        subscriber.id = subscriber_id

        if event_types is None:
            # Global subscriber - receives all events
            self.global_subscribers.append(subscriber)
        else:
            # Type-specific subscribers
            for event_type in event_types:
                self.subscribers[event_type].append(subscriber)

        logger.info(f"Added subscriber {subscriber_id} for events: {[e.value for e in event_types] if event_types else 'all'}")
        return subscriber_id

    def unsubscribe(self, subscriber_id: str):
        """Unsubscribe by ID."""
        # Remove from type-specific subscribers
        for event_type, subscribers in self.subscribers.items():
            self.subscribers[event_type] = [
                s for s in subscribers if getattr(s, 'id', None) != subscriber_id
            ]

        # Remove from global subscribers
        self.global_subscribers = [
            s for s in self.global_subscribers if getattr(s, 'id', None) != subscriber_id
        ]

        logger.info(f"Removed subscriber {subscriber_id}")

    async def publish(self, event: Event) -> bool:
        """
        Publish event to the bus.

        Parameters:
        - event: Event to publish

        Returns:
        - True if event was queued successfully
        """
        try:
            await self.event_queue.put(event)
            self.stats['events_published'] += 1

            # Add to history
            self.event_history.append(event)
            if len(self.event_history) > self.max_history:
                self.event_history.pop(0)

            logger.debug(f"Published event {event.type.value} ({event.event_id})")
            return True
        except asyncio.QueueFull:
            logger.error(f"Event queue full, dropping event {event.type.value}")
            return False

    async def publish_and_wait(self, event: Event, timeout: float = 5.0) -> List[Any]:
        """
        Publish event and wait for all subscribers to process it.

        Parameters:
        - event: Event to publish
        - timeout: Maximum time to wait for processing

        Returns:
        - List of results from subscribers
        """
        # Create a future to track completion
        processed = asyncio.Event()
        results = []

        async def tracking_wrapper(original_event: Event):
            nonlocal results
            result = await self._notify_subscribers(original_event)
            results.extend(result)
            processed.set()

        # Subscribe temporary handler
        self.subscribe(tracking_wrapper, [event.type])

        # Publish event
        await self.publish(event)

        # Wait for processing
        try:
            await asyncio.wait_for(processed.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for event {event.type.value} processing")

        return results

    async def start(self):
        """Start the event processor."""
        if self._running:
            logger.warning("Event bus already running")
            return

        self._running = True
        self._processor_task = asyncio.create_task(self._process_events())
        logger.info("Event bus started")

    async def stop(self):
        """Stop the event processor."""
        if not self._running:
            return

        self._running = False

        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass

        logger.info("Event bus stopped")

    async def _process_events(self):
        """Process events from the queue."""
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self.event_queue.get(),
                    timeout=1.0
                )

                await self._notify_subscribers(event)
                self.stats['events_processed'] += 1

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing event: {e}")
                self.stats['events_failed'] += 1

    async def _notify_subscribers(self, event: Event) -> List[Any]:
        """Notify all relevant subscribers of an event."""
        results = []

        # Get relevant subscribers
        relevant_subscribers = []
        relevant_subscribers.extend(self.global_subscribers)
        relevant_subscribers.extend(self.subscribers.get(event.type, []))

        # Filter and process
        for subscriber in relevant_subscribers:
            if subscriber.should_process(event):
                try:
                    result = await subscriber.process(event)
                    results.append(result)
                    self.stats['subscribers_notified'] += 1
                except Exception as e:
                    logger.error(f"Subscriber error: {e}")
                    await self.dead_letter_queue.put({
                        'event': event,
                        'error': str(e),
                        'subscriber': subscriber
                    })

        return results

    def get_stats(self) -> Dict:
        """Get event bus statistics."""
        return {
            **self.stats,
            'queue_size': self.event_queue.qsize(),
            'dead_letter_queue_size': self.dead_letter_queue.qsize(),
            'subscriber_count': sum(len(s) for s in self.subscribers.values()) + len(self.global_subscribers),
            'history_size': len(self.event_history)
        }

    async def replay_events(self, event_type: Optional[EventType] = None, count: int = 100):
        """Replay historical events for debugging."""
        events = self.event_history[-count:]

        if event_type:
            events = [e for e in events if e.type == event_type]

        for event in events:
            await self.publish(event)

        logger.info(f"Replayed {len(events)} events")


# Global event bus instance
_global_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = EventBus()
    return _global_event_bus


# Convenience functions for common event publishing
async def publish_strategy_discovered(strategy_id: str, metadata: Dict):
    """Publish strategy discovered event."""
    event = Event(
        type=EventType.STRATEGY_DISCOVERED,
        data={'strategy_id': strategy_id, **metadata},
        source='discovery_engine'
    )
    await get_event_bus().publish(event)


async def publish_backtest_completed(strategy_id: str, results: Dict):
    """Publish backtest completed event."""
    event = Event(
        type=EventType.BACKTEST_COMPLETED,
        data={'strategy_id': strategy_id, 'results': results},
        source='backtest_engine'
    )
    await get_event_bus().publish(event)


async def publish_system_error(error: str, context: Dict):
    """Publish system error event."""
    event = Event(
        type=EventType.SYSTEM_ERROR,
        data={'error': error, **context},
        source='system'
    )
    await get_event_bus().publish(event)
