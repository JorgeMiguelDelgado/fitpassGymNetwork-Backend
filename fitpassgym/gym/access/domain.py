"""Domain model for Access bounded context.

Handles check-ins, access validation, and credit consumption.
"""

from datetime import datetime
from typing import Optional

from django.utils import timezone

from ..shared.domain import AggregateRoot, DomainEvent, InvariantViolation


# Domain Events
class CheckInRecordedEvent(DomainEvent):
    """Published when a user checks in to a gym."""
    
    def __init__(self, checkin_id: int, user_id: int, gym_id: int,
                 purchase_id: int, credits_consumed: int, timestamp: datetime):
        super().__init__(checkin_id, timestamp)
        self.user_id = user_id
        self.gym_id = gym_id
        self.purchase_id = purchase_id
        self.credits_consumed = credits_consumed


class AccessDeniedEvent(DomainEvent):
    """Published when check-in is denied."""
    
    def __init__(self, user_id: int, gym_id: int, reason: str, timestamp: datetime):
        super().__init__(user_id, timestamp)
        self.gym_id = gym_id
        self.reason = reason


# Aggregate Roots
class CheckInAggregate(AggregateRoot):
    """A check-in record with access validation."""
    
    def __init__(self, checkin_id: int, user_id: int, gym_id: int,
                 purchase_id: int, credits_consumed: int,
                 checked_in_at: Optional[datetime] = None):
        super().__init__()
        
        # Invariants
        if credits_consumed < 0:
            raise InvariantViolation("Credits consumed cannot be negative")
        
        self.checkin_id = checkin_id
        self.user_id = user_id
        self.gym_id = gym_id
        self.purchase_id = purchase_id
        self.credits_consumed = credits_consumed
        self.checked_in_at = checked_in_at or timezone.now()
    
    def __str__(self) -> str:
        return f"CheckIn #{self.checkin_id}: User {self.user_id} @ Gym {self.gym_id}"


# Domain Services
class AccessService:
    """Domain service for access control."""
    
    @staticmethod
    def validate_access(user_id: int, gym_id: int, purchase) -> bool:
        """Validate if a user can access a gym with their purchase.
        
        Checks:
        - Purchase is not expired
        - Purchase allows this gym (national or local)
        - Product supports physical gym access
        
        Args:
            user_id: User attempting access
            gym_id: Gym being accessed
            purchase: Purchase object with access rights
        
        Returns:
            True if access is granted
        
        Raises:
            InvariantViolation if access is denied
        """
        # Check expiry
        if not purchase.is_valid():
            raise InvariantViolation("Your access has expired")
        
        # Check gym access
        if not purchase.can_be_used_for_gym(gym_id):
            raise InvariantViolation("Your purchase does not include this gym")
        
        # Check if product supports gym access (not virtual-only)
        if purchase.product.access_scope == "virtual":
            raise InvariantViolation("Virtual-only products cannot access physical gyms")
        
        return True
    
    @staticmethod
    def create_checkin(user_id: int, gym_id: int, purchase) -> Optional[tuple]:
        """Create a check-in record and consume credits if applicable.
        
        Returns:
            (CheckInAggregate, credits_consumed) if successful
            None if validation fails
        """
        # Validate access first
        AccessService.validate_access(user_id, gym_id, purchase)
        
        # Determine credits to consume
        credits_to_consume = 0
        if purchase.product.session_credits > 0:
            if purchase.remaining_credits <= 0:
                raise InvariantViolation("No session credits remaining for check-in")
            credits_to_consume = 1
        
        # Create check-in
        checkin = CheckInAggregate(
            checkin_id=None,  # Assigned by repository
            user_id=user_id,
            gym_id=gym_id,
            purchase_id=purchase.purchase_id,
            credits_consumed=credits_to_consume,
        )
        
        checkin.record_event(
            CheckInRecordedEvent(
                checkin.checkin_id,
                user_id,
                gym_id,
                purchase.purchase_id,
                credits_to_consume,
                timezone.now()
            )
        )
        
        return checkin, credits_to_consume
