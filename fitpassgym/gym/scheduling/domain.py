"""Scheduling bounded context domain logic."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from django.utils import timezone

from fitpassgym.gym.shared.domain import (
    AggregateRoot,
    DomainEvent,
    InvariantViolation,
    Capacity,
    Position,
)


@dataclass
class BookingCreatedEvent(DomainEvent):
    """Event published when a booking is created."""
    user_id: int
    class_id: int
    status: str


@dataclass
class BookingCancelledEvent(DomainEvent):
    """Event published when a booking is cancelled."""
    user_id: int
    class_id: int


@dataclass
class UserPromotedFromWaitlistEvent(DomainEvent):
    """Event published when a user is promoted from waitlist."""
    user_id: int
    booking_id: int
    class_id: int


class BookingAggregate(AggregateRoot):
    """Aggregate for fitness class bookings with waitlist management."""
    
    # Status constants
    CONFIRMED = "confirmed"
    WAITLISTED = "waitlisted"
    CANCELLED = "cancelled"
    ATTENDED = "attended"
    NO_SHOW = "no_show"
    
    VALID_STATUSES = {CONFIRMED, WAITLISTED, CANCELLED, ATTENDED, NO_SHOW}
    
    def __init__(
        self,
        booking_id: int,
        user_id: int,
        class_id: int,
        status: str,
        waitlist_position: int = None,
    ):
        super().__init__(booking_id)
        self.user_id = user_id
        self.class_id = class_id
        self._status = status
        self._waitlist_position = waitlist_position
        
        if status not in self.VALID_STATUSES:
            raise InvariantViolation(f"Invalid status: {status}")
    
    @property
    def status(self) -> str:
        return self._status
    
    @property
    def waitlist_position(self) -> int:
        return self._waitlist_position
    
    def promote_from_waitlist(self) -> None:
        """Promote user from waitlist to confirmed."""
        if self._status != self.WAITLISTED:
            raise InvariantViolation("Can only promote from WAITLISTED status")
        
        self._status = self.CONFIRMED
        self._waitlist_position = None
        
        self.add_event(
            UserPromotedFromWaitlistEvent(
                aggregate_id=self.id,
                user_id=self.user_id,
                booking_id=self.id,
                class_id=self.class_id,
                timestamp=timezone.now(),
            )
        )
    
    def mark_attended(self) -> None:
        """Mark booking as attended."""
        if self._status not in {self.CONFIRMED, self.WAITLISTED}:
            raise InvariantViolation(
                f"Can only mark attended from CONFIRMED or WAITLISTED, current: {self._status}"
            )
        self._status = self.ATTENDED
    
    def mark_no_show(self) -> None:
        """Mark booking as no-show."""
        if self._status not in {self.CONFIRMED, self.WAITLISTED}:
            raise InvariantViolation(
                f"Can only mark no-show from CONFIRMED or WAITLISTED, current: {self._status}"
            )
        self._status = self.NO_SHOW
    
    def cancel(self) -> None:
        """Cancel booking."""
        if self._status == self.CANCELLED:
            raise InvariantViolation("Booking is already cancelled")
        
        self._status = self.CANCELLED
        self.add_event(
            BookingCancelledEvent(
                aggregate_id=self.id,
                user_id=self.user_id,
                class_id=self.class_id,
                timestamp=timezone.now(),
            )
        )


class FitnessClassAggregate(AggregateRoot):
    """Aggregate for fitness classes with capacity and slot management."""
    
    def __init__(
        self,
        class_id: int,
        title: str,
        capacity: Capacity,
    ):
        super().__init__(class_id)
        self.title = title
        self._capacity = capacity
    
    @property
    def capacity(self) -> Capacity:
        return self._capacity
    
    def has_available_slots(self) -> bool:
        """Check if there are available spots."""
        return self._capacity.available > 0
    
    def reserve_spot(self) -> None:
        """Reserve a spot in the class."""
        self._capacity = self._capacity.reserve_spot()
    
    def release_spot(self) -> None:
        """Release a spot in the class."""
        self._capacity = self._capacity.release_spot()


class SchedulingService:
    """Service for booking business logic (stateless domain service)."""
    
    @staticmethod
    def book_class(
        user_id: int,
        class_id: int,
        class_aggregate: FitnessClassAggregate,
    ) -> BookingAggregate:
        """
        Book a fitness class for a user.
        
        Returns a BookingAggregate with either CONFIRMED or WAITLISTED status.
        """
        if class_aggregate.has_available_slots():
            status = BookingAggregate.CONFIRMED
            class_aggregate.reserve_spot()
            waitlist_position = None
        else:
            status = BookingAggregate.WAITLISTED
            waitlist_position = 1  # Simplified: just track if waitlisted
        
        booking = BookingAggregate(
            booking_id=None,  # ID assigned by persistence layer
            user_id=user_id,
            class_id=class_id,
            status=status,
            waitlist_position=waitlist_position,
        )
        
        booking.add_event(
            BookingCreatedEvent(
                aggregate_id=None,  # ID assigned by persistence layer
                user_id=user_id,
                class_id=class_id,
                status=status,
                timestamp=timezone.now(),
            )
        )
        
        return booking
    
    @staticmethod
    def cancel_booking(
        booking: BookingAggregate,
        class_aggregate: FitnessClassAggregate,
    ) -> None:
        """Cancel a booking and release its spot."""
        if booking.status == BookingAggregate.CONFIRMED:
            class_aggregate.release_spot()
        
        booking.cancel()
