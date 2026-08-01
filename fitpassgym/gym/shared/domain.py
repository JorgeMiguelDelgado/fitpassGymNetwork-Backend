"""Shared domain infrastructure and value objects.

This module contains core domain concepts that are reused across bounded contexts:
- Value objects: Money, Coordinates, Position
- Base classes: AggregateRoot, Repository, DomainEvent
- Exceptions: Domain-specific errors
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Generic, List, Protocol, TypeVar

T = TypeVar("T")


class DomainException(Exception):
    """Base class for domain-specific exceptions."""
    pass


class InvariantViolation(DomainException):
    """Raised when a business rule invariant is violated."""
    pass


class AggregateRoot:
    """Base class for aggregate roots (entities with business logic)."""
    
    def __init__(self):
        self._events: List["DomainEvent"] = []
    
    def record_event(self, event: "DomainEvent") -> None:
        """Record a domain event that occurred in this aggregate."""
        self._events.append(event)
    
    def get_uncommitted_events(self) -> List["DomainEvent"]:
        """Return events that have not yet been persisted."""
        return list(self._events)
    
    def clear_events(self) -> None:
        """Clear uncommitted events (call after persistence)."""
        self._events.clear()


@dataclass(frozen=True)
class Money:
    """Value object representing a monetary amount.
    
    Immutable and supports common currency operations.
    """
    amount: Decimal
    currency: str = "USD"
    
    def __post_init__(self):
        if self.amount < 0:
            raise InvariantViolation("Money amount cannot be negative")
        if len(self.currency) != 3:
            raise InvariantViolation("Currency code must be 3 characters (ISO 4217)")
    
    def __str__(self) -> str:
        return f"{self.currency} {self.amount:.2f}"
    
    def add(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise InvariantViolation(f"Cannot add {self.currency} and {other.currency}")
        return Money(self.amount + other.amount, self.currency)
    
    def subtract(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise InvariantViolation(f"Cannot subtract {self.currency} and {other.currency}")
        result = self.amount - other.amount
        if result < 0:
            raise InvariantViolation("Subtraction would result in negative money")
        return Money(result, self.currency)
    
    def multiply(self, factor: Decimal) -> "Money":
        if factor < 0:
            raise InvariantViolation("Multiplication factor cannot be negative")
        return Money((self.amount * factor).quantize(Decimal("0.01")), self.currency)
    
    def apply_percent_discount(self, percent: int) -> "Money":
        """Apply a percentage discount (0-100)."""
        if not (0 <= percent <= 100):
            raise InvariantViolation("Discount percent must be 0-100")
        discount = (self.amount * Decimal(percent) / Decimal(100)).quantize(Decimal("0.01"))
        return Money(self.amount - discount, self.currency)


@dataclass(frozen=True)
class Coordinates:
    """Value object representing geographic coordinates."""
    latitude: float
    longitude: float
    
    def __post_init__(self):
        if not (-90 <= self.latitude <= 90):
            raise InvariantViolation("Latitude must be between -90 and 90")
        if not (-180 <= self.longitude <= 180):
            raise InvariantViolation("Longitude must be between -180 and 180")
    
    def __str__(self) -> str:
        return f"({self.latitude}, {self.longitude})"


@dataclass(frozen=True)
class Position:
    """Value object representing a position in a waitlist."""
    position: int
    
    def __post_init__(self):
        if self.position < 1:
            raise InvariantViolation("Position must be >= 1")
    
    def next_position(self) -> "Position":
        """Get the next position in the waitlist."""
        return Position(self.position + 1)
    
    def previous_position(self) -> "Position":
        """Get the previous position (used when someone is promoted)."""
        if self.position <= 1:
            raise InvariantViolation("Cannot get previous position of first in line")
        return Position(self.position - 1)


@dataclass(frozen=True)
class Capacity:
    """Value object representing class capacity and occupancy."""
    total: int
    occupied: int = 0
    
    def __post_init__(self):
        if self.total < 1:
            raise InvariantViolation("Total capacity must be >= 1")
        if self.occupied < 0:
            raise InvariantViolation("Occupied cannot be negative")
        if self.occupied > self.total:
            raise InvariantViolation("Occupied cannot exceed total")
    
    @property
    def available(self) -> int:
        """Number of available spots."""
        return self.total - self.occupied
    
    def is_full(self) -> bool:
        """Check if class is at capacity."""
        return self.occupied >= self.total
    
    def reserve_spot(self) -> "Capacity":
        """Reserve a spot (throw if full)."""
        if self.is_full():
            raise InvariantViolation("Cannot reserve: class is full")
        return Capacity(self.total, self.occupied + 1)
    
    def release_spot(self) -> "Capacity":
        """Release a spot (throw if already empty)."""
        if self.occupied <= 0:
            raise InvariantViolation("Cannot release: no occupied spots")
        return Capacity(self.total, self.occupied - 1)


class DomainEvent:
    """Base class for domain events."""
    
    def __init__(self, aggregate_id: int, timestamp: "datetime"):
        self.aggregate_id = aggregate_id
        self.timestamp = timestamp


class Repository(Protocol[T]):
    """Protocol for repository pattern (data access abstraction)."""
    
    def get_by_id(self, entity_id: int) -> T:
        """Fetch entity by ID."""
        ...
    
    def save(self, entity: T) -> None:
        """Persist entity."""
        ...
    
    def delete(self, entity: T) -> None:
        """Remove entity."""
        ...
