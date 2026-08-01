"""Event handlers for domain events.

Handlers process domain events and perform side effects such as:
- Creating notifications
- Logging important business events
- Triggering subsequent workflows
"""

from typing import Optional

from django.db import transaction

from ..notifications.models import Notification
from ..scheduling.domain import UserPromotedFromWaitlistEvent
from ..commerce.domain import ProductPurchasedEvent, AccessActivatedEvent
from ..access.domain import CheckInRecordedEvent, AccessDeniedEvent


class NotificationEventHandler:
    """Handles event-driven notification creation."""
    
    @staticmethod
    def on_user_promoted_from_waitlist(event: UserPromotedFromWaitlistEvent) -> None:
        """Create a notification when user is promoted from waitlist.
        
        Args:
            event: UserPromotedFromWaitlistEvent containing user and class info
        """
        from ..scheduling.models import FitnessClass
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        try:
            user = User.objects.get(id=event.user_id)
            fitness_class = FitnessClass.objects.get(id=event.class_id)
            
            Notification.objects.create(
                user=user,
                kind=Notification.Kind.WAITLIST_PROMOTED,
                message=f"You've been promoted to confirmed for {fitness_class.title}",
                data={"class_id": fitness_class.id},
            )
        except (User.DoesNotExist, FitnessClass.DoesNotExist):
            # Silently ignore if user or class doesn't exist
            pass
    
    @staticmethod
    def on_product_purchased(event: ProductPurchasedEvent) -> None:
        """Log or notify when a product is purchased.
        
        Args:
            event: ProductPurchasedEvent with purchase details
        """
        # In a real system, this might send a confirmation email, update analytics, etc.
        pass
    
    @staticmethod
    def on_checkin_recorded(event: CheckInRecordedEvent) -> None:
        """Log check-in event for audit trail.
        
        Args:
            event: CheckInRecordedEvent with check-in details
        """
        # In a real system, this might update analytics, trigger door opening, etc.
        pass


class AuditEventHandler:
    """Handles audit logging of domain events."""
    
    @staticmethod
    def log_event(event) -> None:
        """Log a domain event to audit trail.
        
        Args:
            event: The domain event to log
        """
        # In a real system, this would write to an audit log or event store
        pass


class EventHandlerRegistry:
    """Registry and setup for all event handlers.
    
    This centralizes event handler registration so they can be easily
    discovered, managed, and tested.
    """
    
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self._registered_handlers = []
    
    def register_all_handlers(self) -> None:
        """Register all domain event handlers with the event bus."""
        # Scheduling events
        self.event_bus.subscribe(
            UserPromotedFromWaitlistEvent,
            NotificationEventHandler.on_user_promoted_from_waitlist,
            name="NotificationEventHandler.on_user_promoted_from_waitlist",
        )
        
        # Commerce events
        self.event_bus.subscribe(
            ProductPurchasedEvent,
            NotificationEventHandler.on_product_purchased,
            name="NotificationEventHandler.on_product_purchased",
        )
        self.event_bus.subscribe(
            AccessActivatedEvent,
            AuditEventHandler.log_event,
            name="AuditEventHandler.log_event",
        )
        
        # Access events
        self.event_bus.subscribe(
            CheckInRecordedEvent,
            NotificationEventHandler.on_checkin_recorded,
            name="NotificationEventHandler.on_checkin_recorded",
        )
        self.event_bus.subscribe(
            AccessDeniedEvent,
            AuditEventHandler.log_event,
            name="AuditEventHandler.log_event",
        )
