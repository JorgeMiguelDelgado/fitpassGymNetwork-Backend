"""Event bus infrastructure for domain event publishing and handling.

This implements an in-memory event bus for publishing domain events.
In a future session, this will be replaced with RabbitMQ or Kafka.
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Type

from fitpassgym.gym.shared.domain import DomainEvent


@dataclass
class EventHandler:
    """Wrapper for an event handler function with metadata."""
    handler: Callable
    event_type: Type[DomainEvent]
    name: str


class EventBus:
    """In-memory event bus for publishing and subscribing to domain events."""
    
    def __init__(self):
        # Map from event type to list of handlers
        self._handlers: Dict[Type[DomainEvent], List[EventHandler]] = {}
        # Event history for debugging
        self._event_history: List[DomainEvent] = []
    
    def subscribe(self, event_type: Type[DomainEvent], 
                  handler: Callable[[DomainEvent], None],
                  name: str = None) -> EventHandler:
        """Subscribe a handler to an event type.
        
        Args:
            event_type: The domain event class to subscribe to
            handler: Callable that accepts the event and processes it
            name: Optional name for debugging/logging
        
        Returns:
            EventHandler wrapper (can be used to unsubscribe)
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        
        handler_name = name or getattr(handler, "__name__", "unknown")
        event_handler = EventHandler(handler, event_type, handler_name)
        self._handlers[event_type].append(event_handler)
        
        return event_handler
    
    def unsubscribe(self, event_handler: EventHandler) -> None:
        """Unsubscribe a previously registered handler.
        
        Args:
            event_handler: The EventHandler wrapper returned from subscribe()
        """
        handlers = self._handlers.get(event_handler.event_type, [])
        if event_handler in handlers:
            handlers.remove(event_handler)
    
    def publish(self, event: DomainEvent) -> None:
        """Publish a domain event to all subscribers.
        
        Args:
            event: The domain event to publish
        
        Note: Handlers are called synchronously in subscription order.
              Exceptions in handlers do not prevent other handlers from running.
        """
        self._event_history.append(event)
        
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])
        
        for event_handler in handlers:
            try:
                event_handler.handler(event)
            except Exception as exc:
                # In a real system, this would be logged and potentially retried
                raise EventHandlerException(
                    f"Error in handler '{event_handler.name}' for {event_type.__name__}",
                    event=event,
                    handler=event_handler,
                    cause=exc,
                )
    
    def publish_multiple(self, events: List[DomainEvent]) -> None:
        """Publish multiple events in order.
        
        Args:
            events: List of domain events to publish
        """
        for event in events:
            self.publish(event)
    
    def get_history(self) -> List[DomainEvent]:
        """Get the complete event history (for debugging/testing).
        
        Returns:
            List of all published events in order
        """
        return list(self._event_history)
    
    def get_history_of_type(self, event_type: Type[DomainEvent]) -> List[DomainEvent]:
        """Get all events of a specific type from history.
        
        Args:
            event_type: The domain event class to filter by
        
        Returns:
            Filtered list of events
        """
        return [e for e in self._event_history if isinstance(e, event_type)]
    
    def clear_history(self) -> None:
        """Clear the event history (for testing)."""
        self._event_history.clear()
    
    def get_subscriber_count(self, event_type: Type[DomainEvent]) -> int:
        """Get the number of subscribers for an event type.
        
        Args:
            event_type: The domain event class to check
        
        Returns:
            Number of subscribed handlers
        """
        return len(self._handlers.get(event_type, []))


class EventHandlerException(Exception):
    """Exception raised when an event handler fails."""
    
    def __init__(self, message: str, event: DomainEvent = None, 
                 handler: EventHandler = None, cause: Exception = None):
        super().__init__(message)
        self.event = event
        self.handler = handler
        self.cause = cause


# Global event bus instance (can be replaced with a singleton pattern)
_event_bus: EventBus = None


def get_event_bus() -> EventBus:
    """Get or create the global event bus instance.
    
    This uses a simple lazy initialization pattern. In a production system,
    you might use dependency injection or a more sophisticated singleton.
    """
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def reset_event_bus() -> None:
    """Reset the global event bus (primarily for testing).
    
    Creates a fresh event bus instance, clearing all subscriptions and history.
    """
    global _event_bus
    _event_bus = EventBus()
