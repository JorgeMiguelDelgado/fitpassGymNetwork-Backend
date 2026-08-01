"""Access bounded context domain logic."""

from dataclasses import dataclass
from datetime import datetime

from django.utils import timezone

from fitpassgym.gym.shared.domain import (
    AggregateRoot,
    DomainEvent,
    InvariantViolation,
)


@dataclass
class CheckInRecordedEvent(DomainEvent):
    """Event published when a user checks into a gym."""
    user_id: int
    gym_id: int


@dataclass
class AccessDeniedEvent(DomainEvent):
    """Event published when access is denied."""
    user_id: int
    gym_id: int
    reason: str


class CheckInAggregate(AggregateRoot):
    """Aggregate for access records and check-ins."""
    
    def __init__(
        self,
        checkin_id: int,
        user_id: int,
        gym_id: int,
        checked_in_at: datetime,
    ):
        super().__init__(checkin_id)
        self.user_id = user_id
        self.gym_id = gym_id
        self.checked_in_at = checked_in_at
        self._checked_out_at = None
    
    @property
    def checked_out_at(self) -> datetime:
        return self._checked_out_at
    
    def check_out(self, checked_out_at: datetime = None) -> None:
        """Record check-out time."""
        if self._checked_out_at is not None:
            raise InvariantViolation("Already checked out")
        
        self._checked_out_at = checked_out_at or timezone.now()
    
    def duration_minutes(self) -> int:
        """Get duration of the check-in in minutes."""
        if self._checked_out_at is None:
            return 0
        
        delta = self._checked_out_at - self.checked_in_at
        return int(delta.total_seconds() / 60)


class AccessService:
    """Service for access control logic (stateless domain service)."""
    
    @staticmethod
    def validate_access(
        user_id: int,
        gym_id: int,
        has_valid_purchase: bool,
    ) -> bool:
        """
        Validate if user can access the gym.
        
        Returns True if access is allowed, False otherwise.
        """
        if not has_valid_purchase:
            return False
        
        return True
    
    @staticmethod
    def record_check_in(
        user_id: int,
        gym_id: int,
    ) -> CheckInAggregate:
        """
        Record a user check-in at a gym.
        
        Returns a CheckInAggregate.
        """
        checkin = CheckInAggregate(
            checkin_id=None,  # Assigned by persistence layer
            user_id=user_id,
            gym_id=gym_id,
            checked_in_at=timezone.now(),
        )
        
        checkin.add_event(
            CheckInRecordedEvent(
                aggregate_id=None,  # Assigned by persistence layer
                user_id=user_id,
                gym_id=gym_id,
                timestamp=timezone.now(),
            )
        )
        
        return checkin
