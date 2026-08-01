"""
Tests for CQRS Implementation - Session VIII
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from fitpassgym.gym.shared.cqrs import (
    # Read Models
    DenormalizedBooking, DenormalizedGym, DenormalizedUser, AnalyticsEvent,
    
    # Commands
    BookClassCommand, PurchaseProductCommand, ProcessPaymentCommand,
    BookClassCommandHandler, ProcessPaymentCommandHandler,
    
    # Queries
    GetMyBookingsQuery, GetGymDetailsQuery, GetAnalyticsQuery,
    GetMyBookingsQueryHandler, GetGymDetailsQueryHandler, GetAnalyticsQueryHandler,
    
    # Projections
    BookingProjection, PaymentProjection,
    
    # CQRS Bus
    CQRSBus, get_cqrs_bus,
    
    # Consistency
    ConsistencyManager,
)


class TestReadModels:
    """Test read model dataclasses"""
    
    def test_denormalized_booking_creation(self):
        """Test creating denormalized booking"""
        booking = DenormalizedBooking(
            booking_id="b123",
            user_id="u456",
            class_id="c789",
            class_name="Yoga",
            gym_id="g123",
            gym_name="FitPass Downtown",
            trainer_id="t456",
            trainer_name="John Doe",
            booking_date=datetime.now(),
            class_start_time=datetime.now() + timedelta(hours=1),
            class_end_time=datetime.now() + timedelta(hours=2),
            status="CONFIRMED",
            capacity_total=20,
            capacity_occupied=15,
            position_in_waitlist=None,
            price=25.0,
            payment_status="PAID",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        
        assert booking.booking_id == "b123"
        assert booking.status == "CONFIRMED"
        assert booking.payment_status == "PAID"
    
    def test_denormalized_gym_creation(self):
        """Test creating denormalized gym"""
        gym = DenormalizedGym(
            gym_id="g123",
            name="FitPass Downtown",
            city="New York",
            address="123 Main St",
            phone="555-1234",
            email="gym@fitpass.com",
            latitude=40.7128,
            longitude=-74.0060,
            member_count=500,
            active_classes_today=12,
            total_revenue_month=50000.0,
            average_rating=4.8,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        
        assert gym.gym_id == "g123"
        assert gym.member_count == 500
        assert gym.average_rating == 4.8
    
    def test_analytics_event_creation(self):
        """Test creating analytics event"""
        event = AnalyticsEvent(
            event_id="evt_123",
            event_type="booking_created",
            gym_id="g123",
            user_id="u456",
            amount=25.0,
            timestamp=datetime.now(),
            metadata={"class_id": "c789", "status": "CONFIRMED"},
        )
        
        assert event.event_type == "booking_created"
        assert event.amount == 25.0


class TestCommandHandlers:
    """Test command handlers (write side)"""
    
    def test_book_class_command_creation(self):
        """Test creating book class command"""
        command = BookClassCommand(
            booking_id="b123",
            user_id="u456",
            class_id="c789",
            gym_id="g123",
            timestamp=datetime.now(),
        )
        
        assert command.booking_id == "b123"
        assert command.user_id == "u456"
        assert command.class_id == "c789"
    
    def test_process_payment_command_creation(self):
        """Test creating process payment command"""
        command = ProcessPaymentCommand(
            payment_id="p123",
            user_id="u456",
            amount=25.0,
            currency="USD",
            reference_id="booking_b123",
            timestamp=datetime.now(),
        )
        
        assert command.payment_id == "p123"
        assert command.amount == 25.0
        assert command.currency == "USD"
    
    def test_book_class_command_handler(self):
        """Test handling book class command"""
        mock_event_bus = MagicMock()
        handler = BookClassCommandHandler(event_bus=mock_event_bus)
        
        command = BookClassCommand(
            booking_id="b123",
            user_id="u456",
            class_id="c789",
            gym_id="g123",
            timestamp=datetime.now(),
        )
        
        # Mock the event bus publish
        handler.event_bus.publish = MagicMock()
        
        # This will create an event and publish it
        # In real scenario, this would use the actual event bus
        result = handler.handle(command)
        
        # Should return booking_id
        assert result == "b123"


class TestQueryHandlers:
    """Test query handlers (read side)"""
    
    def test_get_my_bookings_query_creation(self):
        """Test creating get bookings query"""
        query = GetMyBookingsQuery(
            user_id="u456",
            status="CONFIRMED",
            from_date=datetime.now(),
            to_date=datetime.now() + timedelta(days=30),
        )
        
        assert query.user_id == "u456"
        assert query.status == "CONFIRMED"
    
    def test_get_gym_details_query_creation(self):
        """Test creating get gym details query"""
        query = GetGymDetailsQuery(gym_id="g123")
        assert query.gym_id == "g123"
    
    def test_get_analytics_query_creation(self):
        """Test creating analytics query"""
        query = GetAnalyticsQuery(
            gym_id="g123",
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now(),
            metrics=["revenue", "bookings", "user_growth"],
        )
        
        assert query.gym_id == "g123"
        assert len(query.metrics) == 3
    
    def test_get_bookings_query_handler(self):
        """Test handling booking query"""
        mock_db = MagicMock()
        handler = GetMyBookingsQueryHandler(read_model_db=mock_db)
        
        # Mock database response
        mock_booking = DenormalizedBooking(
            booking_id="b123",
            user_id="u456",
            class_id="c789",
            class_name="Yoga",
            gym_id="g123",
            gym_name="FitPass",
            trainer_id="t456",
            trainer_name="John",
            booking_date=datetime.now(),
            class_start_time=datetime.now() + timedelta(hours=1),
            class_end_time=datetime.now() + timedelta(hours=2),
            status="CONFIRMED",
            capacity_total=20,
            capacity_occupied=15,
            position_in_waitlist=None,
            price=25.0,
            payment_status="PAID",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        
        mock_db.query = MagicMock(return_value=[mock_booking])
        
        query = GetMyBookingsQuery(user_id="u456")
        results = handler.handle(query)
        
        assert len(results) > 0
        assert results[0].booking_id == "b123"


class TestEventProjections:
    """Test event projections (write read model)"""
    
    def test_booking_projection_creation(self):
        """Test creating booking projection"""
        mock_db = MagicMock()
        projection = BookingProjection(read_model_db=mock_db)
        
        assert projection is not None
    
    def test_payment_projection_creation(self):
        """Test creating payment projection"""
        mock_db = MagicMock()
        projection = PaymentProjection(read_model_db=mock_db)
        
        assert projection is not None
    
    def test_booking_projection_projects_event(self):
        """Test projecting booking event to read model"""
        mock_db = MagicMock()
        projection = BookingProjection(read_model_db=mock_db)
        
        # Mock event
        mock_event = MagicMock()
        mock_event.__class__.__name__ = "BookingCreatedEvent"
        mock_event.aggregate_id = "b123"
        mock_event.user_id = "u456"
        mock_event.class_id = "c789"
        mock_event.gym_id = "g123"
        
        projection.project(mock_event)
        
        # Verify database was called
        # (In actual test, this would verify the INSERT was called)


class TestCQRSBus:
    """Test CQRS bus"""
    
    def test_cqrs_bus_creation(self):
        """Test creating CQRS bus"""
        bus = CQRSBus()
        
        assert bus is not None
        assert len(bus.command_handlers) == 0
        assert len(bus.query_handlers) == 0
        assert len(bus.projections) == 0
    
    def test_register_command_handler(self):
        """Test registering command handler"""
        bus = CQRSBus()
        handler = MagicMock()
        
        bus.register_command_handler("BookClassCommand", handler)
        
        assert "BookClassCommand" in bus.command_handlers
        assert bus.command_handlers["BookClassCommand"] == handler
    
    def test_register_query_handler(self):
        """Test registering query handler"""
        bus = CQRSBus()
        handler = MagicMock()
        
        bus.register_query_handler("GetMyBookingsQuery", handler)
        
        assert "GetMyBookingsQuery" in bus.query_handlers
    
    def test_register_projection(self):
        """Test registering projection"""
        bus = CQRSBus()
        projection = MagicMock()
        
        bus.register_projection(projection)
        
        assert len(bus.projections) == 1
        assert bus.projections[0] == projection
    
    def test_execute_command(self):
        """Test executing command"""
        bus = CQRSBus()
        
        # Create mock handler
        mock_handler = MagicMock()
        mock_handler.handle = MagicMock(return_value="b123")
        
        bus.register_command_handler("BookClassCommand", mock_handler)
        
        # Create command
        command = BookClassCommand(
            booking_id="b123",
            user_id="u456",
            class_id="c789",
            gym_id="g123",
            timestamp=datetime.now(),
        )
        
        # Execute
        result = bus.execute_command(command)
        
        assert result == "b123"
        mock_handler.handle.assert_called_once()
    
    def test_execute_query(self):
        """Test executing query"""
        bus = CQRSBus()
        
        # Create mock handler
        mock_handler = MagicMock()
        mock_handler.handle = MagicMock(return_value=[{"booking_id": "b123"}])
        
        bus.register_query_handler("GetMyBookingsQuery", mock_handler)
        
        # Create query
        query = GetMyBookingsQuery(user_id="u456")
        
        # Execute
        result = bus.execute_query(query)
        
        assert len(result) == 1
        assert result[0]["booking_id"] == "b123"
    
    def test_project_event(self):
        """Test projecting event"""
        bus = CQRSBus()
        
        # Create mock projection
        mock_projection = MagicMock()
        bus.register_projection(mock_projection)
        
        # Create mock event
        mock_event = MagicMock()
        
        # Project
        bus.project_event(mock_event)
        
        # Verify projection was called
        mock_projection.project.assert_called_once_with(mock_event)
    
    def test_project_event_with_multiple_projections(self):
        """Test projecting event to multiple projections"""
        bus = CQRSBus()
        
        # Create multiple mock projections
        mock_projection1 = MagicMock()
        mock_projection2 = MagicMock()
        mock_projection3 = MagicMock()
        
        bus.register_projection(mock_projection1)
        bus.register_projection(mock_projection2)
        bus.register_projection(mock_projection3)
        
        # Create mock event
        mock_event = MagicMock()
        
        # Project
        bus.project_event(mock_event)
        
        # Verify all projections were called
        mock_projection1.project.assert_called_once()
        mock_projection2.project.assert_called_once()
        mock_projection3.project.assert_called_once()


class TestConsistencyManager:
    """Test eventual consistency management"""
    
    def test_consistency_manager_creation(self):
        """Test creating consistency manager"""
        cm = ConsistencyManager(consistency_delay_ms=100)
        
        assert cm.consistency_delay_ms == 100
    
    def test_immediate_consistency(self):
        """Test immediate consistency guarantee"""
        cm = ConsistencyManager(consistency_delay_ms=0)
        
        assert cm.get_consistency_guarantee() == "IMMEDIATE"
    
    def test_delayed_consistency_100ms(self):
        """Test 100ms consistency guarantee"""
        cm = ConsistencyManager(consistency_delay_ms=100)
        
        assert cm.get_consistency_guarantee() == "DELAYED_100MS"
    
    def test_delayed_consistency_500ms(self):
        """Test 500ms consistency guarantee"""
        cm = ConsistencyManager(consistency_delay_ms=500)
        
        assert cm.get_consistency_guarantee() == "DELAYED_500MS"
    
    def test_eventual_consistency(self):
        """Test eventual consistency guarantee"""
        cm = ConsistencyManager(consistency_delay_ms=1000)
        
        assert cm.get_consistency_guarantee() == "EVENTUAL"


class TestCQRSIntegration:
    """Integration tests for full CQRS flow"""
    
    def test_full_cqrs_flow(self):
        """Test complete command → projection → query flow"""
        # Setup
        bus = CQRSBus()
        mock_db = MagicMock()
        
        # Register handlers
        mock_command_handler = MagicMock()
        mock_command_handler.handle = MagicMock(return_value="b123")
        bus.register_command_handler("BookClassCommand", mock_command_handler)
        
        mock_query_handler = MagicMock()
        mock_query_handler.handle = MagicMock(return_value=[{"booking_id": "b123", "status": "CONFIRMED"}])
        bus.register_query_handler("GetMyBookingsQuery", mock_query_handler)
        
        # Register projection
        mock_projection = MagicMock()
        bus.register_projection(mock_projection)
        
        # Execute command
        command = BookClassCommand(
            booking_id="b123",
            user_id="u456",
            class_id="c789",
            gym_id="g123",
            timestamp=datetime.now(),
        )
        booking_id = bus.execute_command(command)
        
        assert booking_id == "b123"
        
        # Execute query
        query = GetMyBookingsQuery(user_id="u456")
        bookings = bus.execute_query(query)
        
        assert len(bookings) == 1
        assert bookings[0]["booking_id"] == "b123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
