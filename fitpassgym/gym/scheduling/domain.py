"""Domain model and services for the Scheduling bounded context.

This layer contains pure domain logic independent of persistence and HTTP.
"""

from datetime import datetime
from typing import List, Optional, Tuple

from django.utils import timezone

from ..shared.domain import (
    AggregateRoot,
    Capacity,
    DomainEvent,
    DomainException,
    InvariantViolation,
)


class BookingStatus:
    """Enumeration of booking statuses."""
    CONFIRMED = "confirmed"
    WAITLISTED = "waitlisted"
    CANCELLED = "cancelled"
    ATTENDED = "attended"
    NO_SHOW = "no_show"


class ClassStatus:
    """Enumeration of fitness class statuses."""
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


# Domain Events
class BookingCreatedEvent(DomainEvent):
    """Published when a user successfully books a class."""
    
    def __init__(self, booking_id: int, user_id: int, class_id: int, 
                 status: str, position: Optional[int], timestamp: datetime):
        super().__init__(booking_id, timestamp)
        self.user_id = user_id
        self.class_id = class_id
        self.status = status
        self.position = position


class BookingCancelledEvent(DomainEvent):
    """Published when a booking is cancelled."""
    
    def __init__(self, booking_id: int, user_id: int, class_id: int, 
                 was_confirmed: bool, timestamp: datetime):
        super().__init__(booking_id, timestamp)
        self.user_id = user_id
        self.class_id = class_id
        self.was_confirmed = was_confirmed


class UserPromotedFromWaitlistEvent(DomainEvent):
    """Published when a user is promoted from waitlist to confirmed."""
    
    def __init__(self, booking_id: int, user_id: int, class_id: int, 
                 timestamp: datetime):
        super().__init__(booking_id, timestamp)
        self.user_id = user_id
        self.class_id = class_id


class WaitlistPositionsCompactedEvent(DomainEvent):
    """Published after waitlist positions are renumbered."""
    
    def __init__(self, class_id: int, timestamp: datetime):
        super().__init__(class_id, timestamp)


# Aggregate Roots
class FitnessClassAggregate(AggregateRoot):
    """Aggregate root for a fitness class with business invariants."""
    
    def __init__(self, class_id: int, title: str, gym_id: int, 
                 instructor_id: int, starts_at: datetime, ends_at: datetime, 
                 capacity: int, status: str = ClassStatus.SCHEDULED):
        super().__init__()
        
        # Invariants
        if ends_at <= starts_at:
            raise InvariantViolation("Class end time must be after start time")
        if capacity < 1:
            raise InvariantViolation("Class capacity must be at least 1")
        
        self.class_id = class_id
        self.title = title
        self.gym_id = gym_id
        self.instructor_id = instructor_id
        self.starts_at = starts_at
        self.ends_at = ends_at
        self.capacity = Capacity(capacity)
        self.status = status
        self.bookings: List["BookingAggregate"] = []
    
    def can_accept_booking(self) -> bool:
        """Check if the class can accept new bookings."""
        now = timezone.now()
        return (
            self.status == ClassStatus.SCHEDULED
            and self.starts_at > now
        )
    
    def get_confirmed_count(self) -> int:
        """Count confirmed (non-waitlisted) bookings."""
        return sum(1 for b in self.bookings if b.status == BookingStatus.CONFIRMED)
    
    def has_space_available(self) -> bool:
        """Check if class has available spots."""
        confirmed_count = self.get_confirmed_count()
        return confirmed_count < self.capacity.total
    
    def reserve_for_booking(self, booking: "BookingAggregate") -> None:
        """Register a booking in this class."""
        if not self.can_accept_booking():
            raise InvariantViolation("This class cannot accept bookings")
        
        self.bookings.append(booking)
    
    def promote_from_waitlist(self) -> Optional["BookingAggregate"]:
        """Promote the first waitlisted user to confirmed (if available)."""
        if not self.has_space_available():
            return None
        
        for booking in self.bookings:
            if booking.status == BookingStatus.WAITLISTED:
                booking.promote_from_waitlist()
                self.record_event(
                    UserPromotedFromWaitlistEvent(
                        booking.booking_id,
                        booking.user_id,
                        self.class_id,
                        timezone.now()
                    )
                )
                return booking
        return None


class BookingAggregate(AggregateRoot):
    """Aggregate root for a booking with business invariants."""
    
    def __init__(self, booking_id: int, user_id: int, class_id: int,
                 status: str = BookingStatus.CONFIRMED, 
                 position: Optional[int] = None,
                 created_at: Optional[datetime] = None):
        super().__init__()
        
        # Invariants
        if status == BookingStatus.WAITLISTED and position is None:
            raise InvariantViolation("Waitlisted booking must have a position")
        if status == BookingStatus.CONFIRMED and position is not None:
            raise InvariantViolation("Confirmed booking must not have a position")
        if position is not None and position < 1:
            raise InvariantViolation("Position must be >= 1")
        
        self.booking_id = booking_id
        self.user_id = user_id
        self.class_id = class_id
        self.status = status
        self.position = position
        self.created_at = created_at or timezone.now()
    
    def promote_from_waitlist(self) -> None:
        """Promote this booking from waitlist to confirmed."""
        if self.status != BookingStatus.WAITLISTED:
            raise InvariantViolation("Only waitlisted bookings can be promoted")
        
        self.status = BookingStatus.CONFIRMED
        self.position = None
    
    def compact_position(self, new_position: int) -> None:
        """Update position when other waitlisted bookings are removed."""
        if self.status != BookingStatus.WAITLISTED:
            raise InvariantViolation("Only waitlisted bookings have positions")
        if new_position < 1:
            raise InvariantViolation("Position must be >= 1")
        
        self.position = new_position
    
    def mark_attended(self) -> None:
        """Mark as attended (only confirmed bookings)."""
        if self.status != BookingStatus.CONFIRMED:
            raise InvariantViolation("Only confirmed bookings can be marked attended")
        
        self.status = BookingStatus.ATTENDED
    
    def mark_no_show(self) -> None:
        """Mark as no-show (only confirmed bookings)."""
        if self.status != BookingStatus.CONFIRMED:
            raise InvariantViolation("Only confirmed bookings can be marked no-show")
        
        self.status = BookingStatus.NO_SHOW
    
    def cancel(self) -> bool:
        """Cancel this booking. Returns True if was confirmed (triggers promotion)."""
        if self.status not in (BookingStatus.CONFIRMED, BookingStatus.WAITLISTED):
            raise InvariantViolation("Cannot cancel a booking in this status")
        
        was_confirmed = self.status == BookingStatus.CONFIRMED
        self.status = BookingStatus.CANCELLED
        self.position = None
        
        self.record_event(
            BookingCancelledEvent(
                self.booking_id,
                self.user_id,
                self.class_id,
                was_confirmed,
                timezone.now()
            )
        )
        
        return was_confirmed


# Domain Services (Pure Business Logic)
class SchedulingService:
    """Domain service for scheduling operations (no persistence)."""
    
    @staticmethod
    def create_booking(user_id: int, fitness_class: FitnessClassAggregate) -> Tuple[BookingAggregate, bool]:
        """Create a booking or add to waitlist.
        
        Returns:
            (booking, created): The booking and whether it's new (False if re-booking)
        """
        if not fitness_class.can_accept_booking():
            raise InvariantViolation("This class cannot be booked")
        
        # Determine if confirmed or waitlisted
        if fitness_class.has_space_available():
            booking = BookingAggregate(
                booking_id=None,  # Will be assigned by repository
                user_id=user_id,
                class_id=fitness_class.class_id,
                status=BookingStatus.CONFIRMED,
            )
        else:
            # Calculate next position
            waitlisted = [b for b in fitness_class.bookings 
                         if b.status == BookingStatus.WAITLISTED]
            next_position = max([b.position for b in waitlisted], default=0) + 1
            
            booking = BookingAggregate(
                booking_id=None,
                user_id=user_id,
                class_id=fitness_class.class_id,
                status=BookingStatus.WAITLISTED,
                position=next_position,
            )
        
        booking.record_event(
            BookingCreatedEvent(
                booking.booking_id,
                user_id,
                fitness_class.class_id,
                booking.status,
                booking.position,
                timezone.now()
            )
        )
        
        return booking, True
    
    @staticmethod
    def cancel_and_promote(booking: BookingAggregate, 
                           fitness_class: FitnessClassAggregate) -> None:
        """Cancel a booking and promote next from waitlist if applicable."""
        was_confirmed = booking.cancel()
        
        if was_confirmed:
            promoted = fitness_class.promote_from_waitlist()
            if promoted:
                # Compact remaining waitlist
                waitlisted = [b for b in fitness_class.bookings 
                             if b.status == BookingStatus.WAITLISTED]
                for idx, wb in enumerate(sorted(waitlisted, key=lambda x: x.created_at), 1):
                    wb.compact_position(idx)
                
                fitness_class.record_event(
                    WaitlistPositionsCompactedEvent(
                        fitness_class.class_id,
                        timezone.now()
                    )
                )
    
    @staticmethod
    def record_attendance(booking: BookingAggregate, attended: bool) -> None:
        """Mark a booking as attended or no-show."""
        if attended:
            booking.mark_attended()
        else:
            booking.mark_no_show()
