"""Base domain infrastructure: value objects, aggregates, events, and repositories."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Protocol, Any

from django.utils import timezone


class DomainException(Exception):
    """Base exception for all domain logic errors."""
    pass


class InvariantViolation(DomainException):
    """Raised when a domain invariant is violated."""
    pass


@dataclass(frozen=True)
class Money:
    """Immutable value object for currency amounts."""
    
    amount: Decimal
    currency: str = "USD"
    
    def __post_init__(self):
        if self.amount < 0:
            raise InvariantViolation("Amount cannot be negative")
        if not self.currency:
            raise InvariantViolation("Currency cannot be empty")
    
    def add(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise InvariantViolation(f"Cannot add {self.currency} and {other.currency}")
        return Money(self.amount + other.amount, self.currency)
    
    def subtract(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise InvariantViolation(f"Cannot subtract {other.currency} from {self.currency}")
        result = self.amount - other.amount
        if result < 0:
            raise InvariantViolation("Subtraction would result in negative amount")
        return Money(result, self.currency)
    
    def multiply(self, factor: Decimal) -> "Money":
        if factor < 0:
            raise InvariantViolation("Multiplication factor cannot be negative")
        return Money(self.amount * factor, self.currency)
    
    def __lt__(self, other: "Money") -> bool:
        if self.currency != other.currency:
            raise InvariantViolation(f"Cannot compare {self.currency} and {other.currency}")
        return self.amount < other.amount
    
    def __le__(self, other: "Money") -> bool:
        if self.currency != other.currency:
            raise InvariantViolation(f"Cannot compare {self.currency} and {other.currency}")
        return self.amount <= other.amount
    
    def __gt__(self, other: "Money") -> bool:
        if self.currency != other.currency:
            raise InvariantViolation(f"Cannot compare {self.currency} and {other.currency}")
        return self.amount > other.amount
    
    def __ge__(self, other: "Money") -> bool:
        if self.currency != other.currency:
            raise InvariantViolation(f"Cannot compare {self.currency} and {other.currency}")
        return self.amount >= other.amount
    
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Money):
            return False
        return self.amount == other.amount and self.currency == other.currency


@dataclass(frozen=True)
class Coordinates:
    """Immutable value object for geographical location."""
    
    latitude: float
    longitude: float
    
    def __post_init__(self):
        if not (-90 <= self.latitude <= 90):
            raise InvariantViolation("Latitude must be between -90 and 90")
        if not (-180 <= self.longitude <= 180):
            raise InvariantViolation("Longitude must be between -180 and 180")


@dataclass(frozen=True)
class Position:
    """Immutable value object for position in waitlist."""
    
    position: int
    
    def __post_init__(self):
        if self.position < 1:
            raise InvariantViolation("Position must be >= 1")
    
    def next_position(self) -> "Position":
        return Position(self.position - 1)


@dataclass(frozen=True)
class Capacity:
    """Immutable value object for fitness class capacity."""
    
    total: int
    occupied: int
    
    def __post_init__(self):
        if self.total < 1:
            raise InvariantViolation("Total capacity must be >= 1")
        if self.occupied < 0:
            raise InvariantViolation("Occupied cannot be negative")
        if self.occupied > self.total:
            raise InvariantViolation("Occupied cannot exceed total")
    
    @property
    def available(self) -> int:
        return self.total - self.occupied
    
    def reserve_spot(self) -> "Capacity":
        if self.available < 1:
            raise InvariantViolation("No available spots")
        return Capacity(self.total, self.occupied + 1)
    
    def release_spot(self) -> "Capacity":
        if self.occupied < 1:
            raise InvariantViolation("Cannot release spot when occupied is 0")
        return Capacity(self.total, self.occupied - 1)


@dataclass
class DomainEvent:
    """Base class for all domain events."""
    
    aggregate_id: int
    timestamp: datetime
    
    def __post_init__(self):
        # aggregate_id can be 0, positive integers, or None (for unsaved aggregates)
        # The requirement is it cannot be a falsy non-int value like empty string
        pass


class AggregateRoot:
    """Base class for aggregate roots with event tracking."""
    
    def __init__(self, aggregate_id: Optional[int] = None):
        self.id = aggregate_id
        self._events: List[DomainEvent] = []
    
    def add_event(self, event: DomainEvent):
        """Record a domain event."""
        self._events.append(event)
    
    def get_uncommitted_events(self) -> List[DomainEvent]:
        """Get all uncommitted events."""
        return list(self._events)
    
    def clear_events(self):
        """Clear uncommitted events (called after persistence)."""
        self._events = []


class Repository(Protocol):
    """Protocol for repository pattern."""
    
    @abstractmethod
    def save(self, aggregate: AggregateRoot) -> None:
        """Save an aggregate root."""
        pass
    
    @abstractmethod
    def get_by_id(self, aggregate_id: int) -> Optional[AggregateRoot]:
        """Retrieve an aggregate root by id."""
        pass
    
    @abstractmethod
    def delete(self, aggregate_id: int) -> None:
        """Delete an aggregate root."""
        pass
