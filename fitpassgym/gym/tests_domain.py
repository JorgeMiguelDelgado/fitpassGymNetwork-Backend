"""Tests for domain layer (business logic without persistence or HTTP).

These tests validate pure domain invariants and value objects.
"""

from decimal import Decimal
from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from fitpassgym.gym.shared.domain import (
    Money,
    Coordinates,
    Position,
    Capacity,
    InvariantViolation,
)
from fitpassgym.gym.scheduling.domain import (
    FitnessClassAggregate,
    BookingAggregate,
    BookingStatus,
    ClassStatus,
    SchedulingService,
)
from fitpassgym.gym.commerce.domain import (
    ProductAggregate,
    PromotionAggregate,
    PurchaseAggregate,
    ProductKind,
    AccessScope,
    CommerceService,
)
from fitpassgym.gym.access.domain import (
    CheckInAggregate,
    AccessService,
)


class MoneyValueObjectTests(SimpleTestCase):
    """Test Money value object invariants."""
    
    def test_money_creation_with_valid_amount(self):
        money = Money(Decimal("100.00"), "USD")
        self.assertEqual(money.amount, Decimal("100.00"))
        self.assertEqual(money.currency, "USD")
    
    def test_money_rejects_negative_amount(self):
        with self.assertRaises(InvariantViolation):
            Money(Decimal("-50.00"), "USD")
    
    def test_money_rejects_invalid_currency_code(self):
        with self.assertRaises(InvariantViolation):
            Money(Decimal("100.00"), "INVALID")
    
    def test_money_addition_same_currency(self):
        m1 = Money(Decimal("100.00"), "USD")
        m2 = Money(Decimal("50.00"), "USD")
        result = m1.add(m2)
        self.assertEqual(result.amount, Decimal("150.00"))
    
    def test_money_addition_different_currency_fails(self):
        m1 = Money(Decimal("100.00"), "USD")
        m2 = Money(Decimal("50.00"), "EUR")
        with self.assertRaises(InvariantViolation):
            m1.add(m2)
    
    def test_money_subtraction(self):
        m1 = Money(Decimal("100.00"), "USD")
        m2 = Money(Decimal("30.00"), "USD")
        result = m1.subtract(m2)
        self.assertEqual(result.amount, Decimal("70.00"))
    
    def test_money_subtraction_would_go_negative_fails(self):
        m1 = Money(Decimal("50.00"), "USD")
        m2 = Money(Decimal("100.00"), "USD")
        with self.assertRaises(InvariantViolation):
            m1.subtract(m2)
    
    def test_money_multiplication(self):
        money = Money(Decimal("100.00"), "USD")
        result = money.multiply(Decimal("1.5"))
        self.assertEqual(result.amount, Decimal("150.00"))
    
    def test_money_apply_percent_discount(self):
        money = Money(Decimal("100.00"), "USD")
        result = money.apply_percent_discount(20)
        self.assertEqual(result.amount, Decimal("80.00"))
    
    def test_money_discount_invalid_percent(self):
        money = Money(Decimal("100.00"), "USD")
        with self.assertRaises(InvariantViolation):
            money.apply_percent_discount(150)


class CoordinatesValueObjectTests(SimpleTestCase):
    """Test Coordinates value object."""
    
    def test_valid_coordinates(self):
        coords = Coordinates(latitude=-16.5, longitude=-68.15)
        self.assertEqual(coords.latitude, -16.5)
        self.assertEqual(coords.longitude, -68.15)
    
    def test_invalid_latitude(self):
        with self.assertRaises(InvariantViolation):
            Coordinates(latitude=95.0, longitude=-68.15)
    
    def test_invalid_longitude(self):
        with self.assertRaises(InvariantViolation):
            Coordinates(latitude=-16.5, longitude=200.0)


class PositionValueObjectTests(SimpleTestCase):
    """Test Position value object (waitlist positions)."""
    
    def test_valid_position(self):
        pos = Position(position=1)
        self.assertEqual(pos.position, 1)
    
    def test_position_zero_invalid(self):
        with self.assertRaises(InvariantViolation):
            Position(position=0)
    
    def test_position_next(self):
        pos = Position(position=1)
        next_pos = pos.next_position()
        self.assertEqual(next_pos.position, 2)
    
    def test_position_previous(self):
        pos = Position(position=2)
        prev_pos = pos.previous_position()
        self.assertEqual(prev_pos.position, 1)
    
    def test_position_previous_from_first_fails(self):
        pos = Position(position=1)
        with self.assertRaises(InvariantViolation):
            pos.previous_position()


class CapacityValueObjectTests(SimpleTestCase):
    """Test Capacity value object."""
    
    def test_valid_capacity(self):
        cap = Capacity(total=20, occupied=5)
        self.assertEqual(cap.available, 15)
        self.assertFalse(cap.is_full())
    
    def test_capacity_full(self):
        cap = Capacity(total=10, occupied=10)
        self.assertTrue(cap.is_full())
        self.assertEqual(cap.available, 0)
    
    def test_reserve_spot_when_available(self):
        cap = Capacity(total=10, occupied=5)
        new_cap = cap.reserve_spot()
        self.assertEqual(new_cap.occupied, 6)
    
    def test_reserve_spot_when_full_fails(self):
        cap = Capacity(total=10, occupied=10)
        with self.assertRaises(InvariantViolation):
            cap.reserve_spot()
    
    def test_release_spot(self):
        cap = Capacity(total=10, occupied=5)
        new_cap = cap.release_spot()
        self.assertEqual(new_cap.occupied, 4)
    
    def test_release_spot_when_empty_fails(self):
        cap = Capacity(total=10, occupied=0)
        with self.assertRaises(InvariantViolation):
            cap.release_spot()


class FitnessClassAggregateTests(SimpleTestCase):
    """Test FitnessClassAggregate business rules."""
    
    def setUp(self):
        self.now = timezone.now()
        self.class_aggregate = FitnessClassAggregate(
            class_id=1,
            title="Spinning",
            gym_id=1,
            instructor_id=1,
            starts_at=self.now + timedelta(days=1),
            ends_at=self.now + timedelta(days=1, hours=1),
            capacity=10,
        )
    
    def test_class_start_must_be_before_end(self):
        with self.assertRaises(InvariantViolation):
            FitnessClassAggregate(
                class_id=1,
                title="Spinning",
                gym_id=1,
                instructor_id=1,
                starts_at=self.now + timedelta(days=2),
                ends_at=self.now + timedelta(days=1),
                capacity=10,
            )
    
    def test_class_capacity_must_be_positive(self):
        with self.assertRaises(InvariantViolation):
            FitnessClassAggregate(
                class_id=1,
                title="Spinning",
                gym_id=1,
                instructor_id=1,
                starts_at=self.now + timedelta(days=1),
                ends_at=self.now + timedelta(days=1, hours=1),
                capacity=0,
            )
    
    def test_class_can_accept_booking_in_future(self):
        self.assertTrue(self.class_aggregate.can_accept_booking())
    
    def test_class_cannot_accept_booking_in_past(self):
        past_class = FitnessClassAggregate(
            class_id=1,
            title="Spinning",
            gym_id=1,
            instructor_id=1,
            starts_at=self.now - timedelta(days=1),
            ends_at=self.now - timedelta(days=1, hours=-1),
            capacity=10,
        )
        self.assertFalse(past_class.can_accept_booking())
    
    def test_class_space_available_initially(self):
        self.assertTrue(self.class_aggregate.has_space_available())
    
    def test_class_space_when_full(self):
        full_class = FitnessClassAggregate(
            class_id=1,
            title="Spinning",
            gym_id=1,
            instructor_id=1,
            starts_at=self.now + timedelta(days=1),
            ends_at=self.now + timedelta(days=1, hours=1),
            capacity=1,
        )
        booking = BookingAggregate(1, 1, 1, BookingStatus.CONFIRMED)
        full_class.bookings.append(booking)
        self.assertFalse(full_class.has_space_available())


class BookingAggregateTests(SimpleTestCase):
    """Test BookingAggregate business rules."""
    
    def test_confirmed_booking_must_not_have_position(self):
        with self.assertRaises(InvariantViolation):
            BookingAggregate(
                booking_id=1,
                user_id=1,
                class_id=1,
                status=BookingStatus.CONFIRMED,
                position=1,  # Should fail
            )
    
    def test_waitlisted_booking_must_have_position(self):
        with self.assertRaises(InvariantViolation):
            BookingAggregate(
                booking_id=1,
                user_id=1,
                class_id=1,
                status=BookingStatus.WAITLISTED,
                position=None,  # Should fail
            )
    
    def test_promote_from_waitlist(self):
        booking = BookingAggregate(
            booking_id=1,
            user_id=1,
            class_id=1,
            status=BookingStatus.WAITLISTED,
            position=1,
        )
        booking.promote_from_waitlist()
        self.assertEqual(booking.status, BookingStatus.CONFIRMED)
        self.assertIsNone(booking.position)
    
    def test_mark_attended_only_if_confirmed(self):
        booking = BookingAggregate(
            booking_id=1,
            user_id=1,
            class_id=1,
            status=BookingStatus.CONFIRMED,
        )
        booking.mark_attended()
        self.assertEqual(booking.status, BookingStatus.ATTENDED)
    
    def test_cannot_mark_attended_if_not_confirmed(self):
        booking = BookingAggregate(
            booking_id=1,
            user_id=1,
            class_id=1,
            status=BookingStatus.WAITLISTED,
            position=1,
        )
        with self.assertRaises(InvariantViolation):
            booking.mark_attended()
    
    def test_cancel_confirmed_booking_returns_true(self):
        booking = BookingAggregate(
            booking_id=1,
            user_id=1,
            class_id=1,
            status=BookingStatus.CONFIRMED,
        )
        was_confirmed = booking.cancel()
        self.assertTrue(was_confirmed)
        self.assertEqual(booking.status, BookingStatus.CANCELLED)
    
    def test_cancel_waitlisted_booking_returns_false(self):
        booking = BookingAggregate(
            booking_id=1,
            user_id=1,
            class_id=1,
            status=BookingStatus.WAITLISTED,
            position=1,
        )
        was_confirmed = booking.cancel()
        self.assertFalse(was_confirmed)


class MoneyPromotionTests(SimpleTestCase):
    """Test promotion discount calculation with Money value object."""
    
    def setUp(self):
        self.now = timezone.now()
        self.promotion = PromotionAggregate(
            promotion_id=1,
            code="INTRO20",
            percent_off=20,
            starts_at=self.now - timedelta(hours=1),
            ends_at=self.now + timedelta(days=1),
        )
    
    def test_promotion_is_active_during_period(self):
        self.assertTrue(self.promotion.is_active())
    
    def test_promotion_apply_discount(self):
        price = Money(Decimal("100.00"), "USD")
        discounted = self.promotion.apply_discount(price)
        self.assertEqual(discounted.amount, Decimal("80.00"))
    
    def test_promotion_inactive_rejects_discount(self):
        inactive_promo = PromotionAggregate(
            promotion_id=1,
            code="OLD",
            percent_off=20,
            starts_at=self.now - timedelta(days=2),
            ends_at=self.now - timedelta(days=1),
        )
        price = Money(Decimal("100.00"), "USD")
        with self.assertRaises(InvariantViolation):
            inactive_promo.apply_discount(price)


class PurchaseAggregateTests(SimpleTestCase):
    """Test PurchaseAggregate business rules."""
    
    def setUp(self):
        self.now = timezone.now()
        self.product = ProductAggregate(
            product_id=1,
            name="Day Pass",
            kind=ProductKind.DAY_PASS,
            access_scope=AccessScope.NATIONAL,
            price=Money(Decimal("50.00"), "USD"),
            duration_days=1,
            session_credits=5,
        )
    
    def test_purchase_is_valid_within_duration(self):
        purchase = PurchaseAggregate(
            purchase_id=1,
            user_id=1,
            product=self.product,
            amount=Money(Decimal("50.00"), "USD"),
            valid_until=self.now + timedelta(days=1),
            remaining_credits=5,
        )
        self.assertTrue(purchase.is_valid())
    
    def test_purchase_is_expired_after_duration(self):
        purchase = PurchaseAggregate(
            purchase_id=1,
            user_id=1,
            product=self.product,
            amount=Money(Decimal("50.00"), "USD"),
            valid_until=self.now - timedelta(days=1),
            remaining_credits=5,
        )
        self.assertFalse(purchase.is_valid())
    
    def test_consume_credit(self):
        purchase = PurchaseAggregate(
            purchase_id=1,
            user_id=1,
            product=self.product,
            amount=Money(Decimal("50.00"), "USD"),
            valid_until=self.now + timedelta(days=1),
            remaining_credits=5,
        )
        purchase.consume_credit()
        self.assertEqual(purchase.remaining_credits, 4)
    
    def test_consume_credit_when_none_remaining_fails(self):
        purchase = PurchaseAggregate(
            purchase_id=1,
            user_id=1,
            product=self.product,
            amount=Money(Decimal("50.00"), "USD"),
            valid_until=self.now + timedelta(days=1),
            remaining_credits=0,
        )
        with self.assertRaises(InvariantViolation):
            purchase.consume_credit()
    
    def test_consume_credit_when_expired_fails(self):
        purchase = PurchaseAggregate(
            purchase_id=1,
            user_id=1,
            product=self.product,
            amount=Money(Decimal("50.00"), "USD"),
            valid_until=self.now - timedelta(days=1),
            remaining_credits=5,
        )
        with self.assertRaises(InvariantViolation):
            purchase.consume_credit()


class AccessServiceTests(SimpleTestCase):
    """Test access control domain service."""
    
    def setUp(self):
        self.now = timezone.now()
        self.product = ProductAggregate(
            product_id=1,
            name="National Day Pass",
            kind=ProductKind.DAY_PASS,
            access_scope=AccessScope.NATIONAL,
            price=Money(Decimal("50.00"), "USD"),
            duration_days=1,
        )
        self.purchase = PurchaseAggregate(
            purchase_id=1,
            user_id=1,
            product=self.product,
            amount=Money(Decimal("50.00"), "USD"),
            valid_until=self.now + timedelta(days=1),
        )
    
    def test_validate_access_succeeds_with_valid_purchase(self):
        result = AccessService.validate_access(1, 1, self.purchase)
        self.assertTrue(result)
    
    def test_validate_access_fails_with_expired_purchase(self):
        expired_purchase = PurchaseAggregate(
            purchase_id=1,
            user_id=1,
            product=self.product,
            amount=Money(Decimal("50.00"), "USD"),
            valid_until=self.now - timedelta(days=1),
        )
        with self.assertRaises(InvariantViolation):
            AccessService.validate_access(1, 1, expired_purchase)
