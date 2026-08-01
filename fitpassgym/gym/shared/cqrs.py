"""
CQRS (Command Query Responsibility Segregation) Implementation - Session VIII

Separates read and write models for independent scaling and optimization:
- Write Side: Commands that modify state (BookCommand, PurchaseCommand)
- Read Side: Queries that retrieve data (GetBookingsQuery, GetAnalyticsQuery)
- Projections: Event handlers that update read models from domain events
- Read Models: Denormalized, optimized views for fast queries
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
import json


# ============ Read Models (Denormalized Data) ============

@dataclass
class DenormalizedBooking:
    """Optimized booking view for quick queries"""
    booking_id: str
    user_id: str
    class_id: str
    class_name: str
    gym_id: str
    gym_name: str
    trainer_id: str
    trainer_name: str
    booking_date: datetime
    class_start_time: datetime
    class_end_time: datetime
    status: str  # CONFIRMED, WAITLISTED, ATTENDED, NO_SHOW, CANCELLED
    capacity_total: int
    capacity_occupied: int
    position_in_waitlist: Optional[int]
    price: float
    payment_status: str  # PENDING, PAID, REFUNDED
    created_at: datetime
    updated_at: datetime


@dataclass
class DenormalizedGym:
    """Optimized gym view for quick queries"""
    gym_id: str
    name: str
    city: str
    address: str
    phone: str
    email: str
    latitude: float
    longitude: float
    member_count: int
    active_classes_today: int
    total_revenue_month: float
    average_rating: float
    created_at: datetime
    updated_at: datetime


@dataclass
class DenormalizedUser:
    """Optimized user view for quick queries"""
    user_id: str
    email: str
    full_name: str
    phone: str
    membership_status: str  # ACTIVE, INACTIVE, SUSPENDED
    membership_tier: str  # BASIC, PREMIUM, VIP
    total_bookings: int
    attended_bookings: int
    cancelled_bookings: int
    average_rating: float
    credits_balance: float
    joined_date: datetime
    last_login: datetime
    updated_at: datetime


@dataclass
class AnalyticsEvent:
    """Analytics event for business metrics"""
    event_id: str
    event_type: str  # booking_created, payment_processed, user_joined
    gym_id: str
    user_id: str
    amount: Optional[float]
    timestamp: datetime
    metadata: Dict[str, Any]


# ============ CQRS: Command Side (Write Model) ============

class CommandHandler:
    """Base class for command handlers"""
    
    def handle(self, command: Any) -> str:
        """Execute command and return result"""
        raise NotImplementedError


@dataclass
class BookClassCommand:
    """Command to book a class"""
    booking_id: str
    user_id: str
    class_id: str
    gym_id: str
    timestamp: datetime


@dataclass
class PurchaseProductCommand:
    """Command to purchase a product"""
    purchase_id: str
    user_id: str
    product_id: str
    quantity: int
    price: float
    timestamp: datetime


@dataclass
class ProcessPaymentCommand:
    """Command to process payment"""
    payment_id: str
    user_id: str
    amount: float
    currency: str
    reference_id: str
    timestamp: datetime


class BookClassCommandHandler(CommandHandler):
    """Handle booking a class"""
    
    def __init__(self, event_bus):
        self.event_bus = event_bus
    
    def handle(self, command: BookClassCommand) -> str:
        """
        Handle booking command
        Returns: booking_id if successful
        """
        # In real implementation:
        # 1. Validate command
        # 2. Load aggregate from repository
        # 3. Execute aggregate method (produces events)
        # 4. Save aggregate
        # 5. Publish events to event bus
        
        from fitpassgym.gym.shared.events import get_event_bus
        from fitpassgym.gym.scheduling.domain import BookingCreatedEvent
        
        # Publish event (write model)
        event = BookingCreatedEvent(
            aggregate_id=command.booking_id,
            user_id=command.user_id,
            class_id=command.class_id,
            gym_id=command.gym_id,
        )
        get_event_bus().publish(event)
        
        return command.booking_id


class ProcessPaymentCommandHandler(CommandHandler):
    """Handle payment processing"""
    
    def __init__(self, payment_processor):
        self.payment_processor = payment_processor
    
    def handle(self, command: ProcessPaymentCommand) -> str:
        """
        Handle payment command
        Returns: transaction_id if successful
        """
        # 1. Call payment processor
        # 2. Handle success/failure
        # 3. Publish events
        
        transaction_id = f"txn_{command.payment_id}"
        return transaction_id


# ============ CQRS: Query Side (Read Model) ============

class QueryHandler:
    """Base class for query handlers"""
    
    def handle(self, query: Any) -> List[Dict[str, Any]]:
        """Execute query and return results"""
        raise NotImplementedError


@dataclass
class GetMyBookingsQuery:
    """Query to get user's bookings"""
    user_id: str
    status: Optional[str] = None  # Filter by status
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None


@dataclass
class GetGymDetailsQuery:
    """Query to get gym information"""
    gym_id: str


@dataclass
class GetAnalyticsQuery:
    """Query to get analytics"""
    gym_id: str
    start_date: datetime
    end_date: datetime
    metrics: List[str]  # e.g., ["revenue", "bookings", "user_growth"]


class GetMyBookingsQueryHandler(QueryHandler):
    """Handle booking queries"""
    
    def __init__(self, read_model_db):
        self.db = read_model_db
    
    def handle(self, query: GetMyBookingsQuery) -> List[DenormalizedBooking]:
        """
        Query read model for user bookings
        Returns from denormalized_bookings table (very fast)
        """
        # In real implementation:
        # SELECT * FROM denormalized_bookings 
        # WHERE user_id = ? 
        # AND (status = ? OR ? IS NULL)
        # AND class_start_time BETWEEN ? AND ?
        
        result = self.db.query(
            "SELECT * FROM denormalized_bookings WHERE user_id = ?",
            [query.user_id]
        )
        
        if query.status:
            result = [b for b in result if b.status == query.status]
        
        if query.from_date:
            result = [b for b in result if b.class_start_time >= query.from_date]
        
        if query.to_date:
            result = [b for b in result if b.class_start_time <= query.to_date]
        
        return result


class GetGymDetailsQueryHandler(QueryHandler):
    """Handle gym queries"""
    
    def __init__(self, read_model_db):
        self.db = read_model_db
    
    def handle(self, query: GetGymDetailsQuery) -> Optional[DenormalizedGym]:
        """Query read model for gym details"""
        result = self.db.query(
            "SELECT * FROM denormalized_gyms WHERE gym_id = ?",
            [query.gym_id]
        )
        return result[0] if result else None


class GetAnalyticsQueryHandler(QueryHandler):
    """Handle analytics queries"""
    
    def __init__(self, read_model_db):
        self.db = read_model_db
    
    def handle(self, query: GetAnalyticsQuery) -> Dict[str, Any]:
        """Query read model for analytics"""
        metrics_result = {}
        
        for metric in query.metrics:
            if metric == "revenue":
                # SELECT SUM(amount) FROM analytics_events WHERE type='payment_processed'
                result = self.db.query(
                    "SELECT SUM(amount) as total FROM analytics_events "
                    "WHERE gym_id = ? AND event_type = 'payment_processed' "
                    "AND timestamp BETWEEN ? AND ?",
                    [query.gym_id, query.start_date, query.end_date]
                )
                metrics_result["revenue"] = result[0]["total"] if result else 0
            
            elif metric == "bookings":
                # SELECT COUNT(*) FROM analytics_events WHERE type='booking_created'
                result = self.db.query(
                    "SELECT COUNT(*) as count FROM analytics_events "
                    "WHERE gym_id = ? AND event_type = 'booking_created' "
                    "AND timestamp BETWEEN ? AND ?",
                    [query.gym_id, query.start_date, query.end_date]
                )
                metrics_result["bookings"] = result[0]["count"] if result else 0
            
            elif metric == "user_growth":
                # SELECT COUNT(DISTINCT user_id) FROM analytics_events
                result = self.db.query(
                    "SELECT COUNT(DISTINCT user_id) as count FROM analytics_events "
                    "WHERE gym_id = ? AND event_type = 'user_joined' "
                    "AND timestamp BETWEEN ? AND ?",
                    [query.gym_id, query.start_date, query.end_date]
                )
                metrics_result["user_growth"] = result[0]["count"] if result else 0
        
        return metrics_result


# ============ Event Projections (Write Read Model) ============

class EventProjection:
    """Base class for event projections"""
    
    def project(self, event: Any) -> None:
        """Project event to read model"""
        raise NotImplementedError


class BookingProjection(EventProjection):
    """Project booking events to denormalized_bookings"""
    
    def __init__(self, read_model_db):
        self.db = read_model_db
    
    def project(self, event: Any) -> None:
        """
        When BookingCreatedEvent occurs:
        1. Load booking aggregate
        2. Join with class, gym, trainer data
        3. Insert into denormalized_bookings
        """
        if hasattr(event, '__class__') and event.__class__.__name__ == 'BookingCreatedEvent':
            # Denormalize: fetch all related data
            booking_data = {
                "booking_id": event.aggregate_id,
                "user_id": event.user_id,
                "class_id": event.class_id,
                "gym_id": event.gym_id,
                "status": "CONFIRMED",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
            
            # INSERT INTO denormalized_bookings (...)
            self.db.execute(
                "INSERT INTO denormalized_bookings (booking_id, user_id, class_id, gym_id, status) "
                "VALUES (?, ?, ?, ?, ?)",
                [booking_data["booking_id"], booking_data["user_id"], 
                 booking_data["class_id"], booking_data["gym_id"], "CONFIRMED"]
            )


class PaymentProjection(EventProjection):
    """Project payment events to analytics_events"""
    
    def __init__(self, read_model_db):
        self.db = read_model_db
    
    def project(self, event: Any) -> None:
        """
        When PaymentProcessedEvent occurs:
        1. Record analytics event
        2. Update user credit balance
        3. Update gym revenue totals
        """
        if hasattr(event, '__class__') and event.__class__.__name__ == 'PaymentProcessedEvent':
            # INSERT INTO analytics_events
            self.db.execute(
                "INSERT INTO analytics_events (event_id, event_type, gym_id, user_id, amount, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ["evt_" + event.aggregate_id, "payment_processed", event.gym_id, 
                 event.user_id, event.amount, datetime.now()]
            )


# ============ CQRS Bus (Coordinates Commands/Queries/Projections) ============

class CQRSBus:
    """Central CQRS bus for commands, queries, and projections"""
    
    def __init__(self):
        self.command_handlers: Dict[str, CommandHandler] = {}
        self.query_handlers: Dict[str, QueryHandler] = {}
        self.projections: List[EventProjection] = []
    
    def register_command_handler(self, command_type: str, handler: CommandHandler) -> None:
        """Register a command handler"""
        self.command_handlers[command_type] = handler
    
    def register_query_handler(self, query_type: str, handler: QueryHandler) -> None:
        """Register a query handler"""
        self.query_handlers[query_type] = handler
    
    def register_projection(self, projection: EventProjection) -> None:
        """Register an event projection"""
        self.projections.append(projection)
    
    def execute_command(self, command: Any) -> str:
        """Execute a command (write side)"""
        command_type = command.__class__.__name__
        
        if command_type not in self.command_handlers:
            raise ValueError(f"No handler for command: {command_type}")
        
        handler = self.command_handlers[command_type]
        return handler.handle(command)
    
    def execute_query(self, query: Any) -> List[Dict[str, Any]]:
        """Execute a query (read side)"""
        query_type = query.__class__.__name__
        
        if query_type not in self.query_handlers:
            raise ValueError(f"No handler for query: {query_type}")
        
        handler = self.query_handlers[query_type]
        return handler.handle(query)
    
    def project_event(self, event: Any) -> None:
        """Project event to all read models"""
        for projection in self.projections:
            try:
                projection.project(event)
            except Exception as e:
                # Log error but continue with other projections
                print(f"Error projecting event: {e}")


# ============ Consistency Management ============

class ConsistencyManager:
    """Manage eventual consistency between write and read models"""
    
    def __init__(self, consistency_delay_ms: int = 100):
        """
        consistency_delay_ms: Expected delay between event and read model update
        Typical values: 100-500ms for distributed systems
        """
        self.consistency_delay_ms = consistency_delay_ms
        self.projections_pending = {}
    
    def get_consistency_guarantee(self) -> str:
        """
        Returns consistency model
        Options: IMMEDIATE, DELAYED_100MS, DELAYED_500MS, EVENTUAL
        """
        if self.consistency_delay_ms == 0:
            return "IMMEDIATE"
        elif self.consistency_delay_ms < 200:
            return "DELAYED_100MS"
        elif self.consistency_delay_ms < 600:
            return "DELAYED_500MS"
        else:
            return "EVENTUAL"
    
    async def wait_for_consistency(self, event_id: str, timeout_ms: int = 5000) -> bool:
        """
        Wait for read model to be updated with event
        Useful for critical operations that need read-after-write consistency
        """
        import asyncio
        
        start_time = datetime.now()
        
        while True:
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            if elapsed_ms > timeout_ms:
                return False
            
            if event_id not in self.projections_pending:
                return True
            
            await asyncio.sleep(0.01)  # Check every 10ms


# ============ Singleton Instance ============

_cqrs_bus_instance = None


def get_cqrs_bus() -> CQRSBus:
    """Get global CQRS bus instance"""
    global _cqrs_bus_instance
    if _cqrs_bus_instance is None:
        _cqrs_bus_instance = CQRSBus()
    return _cqrs_bus_instance
