"""Tests for event bus and event handling infrastructure."""

from datetime import datetime

from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from fitpassgym.gym.shared.events import (
    EventBus,
    EventHandler,
    EventHandlerException,
    get_event_bus,
    reset_event_bus,
)
from fitpassgym.gym.shared.domain import DomainEvent
from fitpassgym.gym.scheduling.domain import UserPromotedFromWaitlistEvent
from fitpassgym.gym.notifications.models import Notification
from fitpassgym.gym.models import FitnessClass, Gym, Instructor


User = get_user_model()


class TestEvent(DomainEvent):
    """Test event for use in unit tests."""
    
    def __init__(self, aggregate_id: int, test_data: str, timestamp=None):
        if timestamp is None:
            from django.utils import timezone
            timestamp = timezone.now()
        
        # Allow 0 for testing
        if aggregate_id is None:
            raise InvariantViolation("aggregate_id cannot be None")
        
        self.aggregate_id = aggregate_id
        self.timestamp = timestamp
        self.test_data = test_data


class EventBusTests(SimpleTestCase):
    """Test EventBus core functionality."""
    
    def setUp(self):
        self.bus = EventBus()
        self.handled_events = []
    
    def test_subscribe_and_publish_single_handler(self):
        """Test subscribing to an event and publishing it."""
        def handler(event):
            self.handled_events.append(event)
        
        self.bus.subscribe(TestEvent, handler)
        event = TestEvent(1, "test")
        self.bus.publish(event)
        
        self.assertEqual(len(self.handled_events), 1)
        self.assertEqual(self.handled_events[0].test_data, "test")
    
    def test_subscribe_multiple_handlers_same_event(self):
        """Test multiple handlers for the same event type."""
        results = []
        
        def handler1(event):
            results.append("handler1")
        
        def handler2(event):
            results.append("handler2")
        
        self.bus.subscribe(TestEvent, handler1, name="handler1")
        self.bus.subscribe(TestEvent, handler2, name="handler2")
        self.bus.publish(TestEvent(1, "test"))
        
        self.assertEqual(results, ["handler1", "handler2"])
    
    def test_unsubscribe_handler(self):
        """Test unsubscribing a handler."""
        def handler(event):
            self.handled_events.append(event)
        
        event_handler = self.bus.subscribe(TestEvent, handler)
        self.bus.unsubscribe(event_handler)
        self.bus.publish(TestEvent(1, "test"))
        
        self.assertEqual(len(self.handled_events), 0)
    
    def test_publish_multiple_events(self):
        """Test publishing multiple events at once."""
        def handler(event):
            self.handled_events.append(event)
        
        self.bus.subscribe(TestEvent, handler)
        events = [TestEvent(i, f"test{i}") for i in range(3)]
        self.bus.publish_multiple(events)
        
        self.assertEqual(len(self.handled_events), 3)
    
    def test_event_history(self):
        """Test event history tracking."""
        event1 = TestEvent(1, "test1")
        event2 = TestEvent(2, "test2")
        
        self.bus.publish(event1)
        self.bus.publish(event2)
        
        history = self.bus.get_history()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].test_data, "test1")
        self.assertEqual(history[1].test_data, "test2")
    
    def test_get_history_of_type(self):
        """Test filtering event history by type."""
        class OtherEvent(DomainEvent):
            pass
        
        self.bus.publish(TestEvent(1, "test"))
        self.bus.publish(OtherEvent(2, timezone.now()))
        self.bus.publish(TestEvent(3, "test2"))
        
        test_events = self.bus.get_history_of_type(TestEvent)
        self.assertEqual(len(test_events), 2)
        self.assertIsInstance(test_events[0], TestEvent)
    
    def test_clear_history(self):
        """Test clearing event history."""
        self.bus.publish(TestEvent(1, "test"))
        self.bus.clear_history()
        
        self.assertEqual(len(self.bus.get_history()), 0)
    
    def test_get_subscriber_count(self):
        """Test counting subscribers for an event type."""
        self.bus.subscribe(TestEvent, lambda e: None)
        self.bus.subscribe(TestEvent, lambda e: None)
        
        count = self.bus.get_subscriber_count(TestEvent)
        self.assertEqual(count, 2)
    
    def test_handler_exception_propagates(self):
        """Test that exceptions in handlers are propagated."""
        def failing_handler(event):
            raise ValueError("Handler failed")
        
        self.bus.subscribe(TestEvent, failing_handler)
        
        with self.assertRaises(EventHandlerException):
            self.bus.publish(TestEvent(1, "test"))
    
    def test_handler_exception_has_context(self):
        """Test that handler exceptions include debugging context."""
        def failing_handler(event):
            raise ValueError("Original error")
        
        self.bus.subscribe(TestEvent, failing_handler, name="test_handler")
        
        try:
            self.bus.publish(TestEvent(1, "test"))
        except EventHandlerException as e:
            self.assertIn("test_handler", str(e))
            self.assertIsNotNone(e.event)
            self.assertIsNotNone(e.handler)
            self.assertIsNotNone(e.cause)


class GlobalEventBusTests(SimpleTestCase):
    """Test the global event bus singleton."""
    
    def tearDown(self):
        # Reset event bus after each test
        reset_event_bus()
    
    def test_get_event_bus_returns_same_instance(self):
        """Test that get_event_bus returns the same instance."""
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        
        self.assertIs(bus1, bus2)
    
    def test_reset_event_bus_creates_new_instance(self):
        """Test that reset creates a fresh bus."""
        bus1 = get_event_bus()
        bus1.publish(TestEvent(1, "test"))
        
        reset_event_bus()
        bus2 = get_event_bus()
        
        self.assertIsNot(bus1, bus2)
        self.assertEqual(len(bus2.get_history()), 0)


class UserPromotedEventTests(TestCase):
    """Integration tests for UserPromotedFromWaitlistEvent."""
    
    def setUp(self):
        reset_event_bus()
        self.user1 = User.objects.create_user("user1", password="pass1234")
        self.user2 = User.objects.create_user("user2", password="pass1234")
        self.instructor_user = User.objects.create_user("coach", password="pass1234")
        
        self.gym = Gym.objects.create(
            name="Test Gym",
            address="La Paz",
            latitude=-16.5,
            longitude=-68.15,
        )
        self.instructor = Instructor.objects.create(user=self.instructor_user)
        self.fitness_class = FitnessClass.objects.create(
            title="Spinning",
            gym=self.gym,
            instructor=self.instructor,
            starts_at=timezone.now() + timezone.timedelta(days=1),
            ends_at=timezone.now() + timezone.timedelta(days=1, hours=1),
            capacity=1,
        )
    
    def test_user_promoted_event_creates_notification(self):
        """Test that UserPromotedFromWaitlistEvent triggers notification creation."""
        from fitpassgym.gym.shared.event_handlers import NotificationEventHandler
        
        bus = get_event_bus()
        bus.subscribe(
            UserPromotedFromWaitlistEvent,
            NotificationEventHandler.on_user_promoted_from_waitlist,
        )
        
        # Publish the event
        event = UserPromotedFromWaitlistEvent(
            aggregate_id=1,
            user_id=self.user2.id,
            booking_id=1,
            class_id=self.fitness_class.id,
            timestamp=timezone.now(),
        )
        bus.publish(event)
        
        # Verify notification was created
        notification = Notification.objects.filter(
            user=self.user2,
            kind=Notification.Kind.WAITLIST_PROMOTED,
        ).first()
        
        self.assertIsNotNone(notification)
        self.assertIn(self.fitness_class.title, notification.message)
