"""Tests for domain layer aggregates and value objects."""

from decimal import Decimal
from datetime import datetime

from django.test import SimpleTestCase
from django.utils import timezone

from fitpassgym.gym.shared.domain import (
    Money,
    Coordinates,
    Position,
    Capacity,
    InvariantViolation,
    AggregateRoot,
    DomainEvent,
)
from fitpassgym.gym.scheduling.domain import (
    BookingAggregate,
    FitnessClassAggregate,
    SchedulingService,
    BookingCreatedEvent,
)
from fitpassgym.gym.commerce.domain import (
    ProductAggregate,
    PromotionAggregate,
    PurchaseAggregate,
    CommerceService,
)
from fitpassgym.gym.access.domain import AccessService, CheckInAggregate


class MoneyValueObjectTests(SimpleTestCase):
    """Test Money value object invariants and operations."""
    
    def test_money_creation_valid(self):
        """Test creating money with valid amount."""
        money = Money(Decimal("100.00"), "USD")
        self.assertEqual(money.amount, Decimal("100.00"))
        self.assertEqual(money.currency, "USD")
    
    def test_money_negative_amount_raises_error(self):
        """Test that negative amount raises InvariantViolation."""
        with self.assertRaises(InvariantViolation):
            Money(Decimal("-10.00"), "USD")
    
    def test_money_add_same_currency(self):
        """Test adding money with same currency."""
        m1 = Money(Decimal("100.00"), "USD")
        m2 = Money(Decimal("50.00"), "USD")
        result = m1.add(m2)
        self.assertEqual(result.amount, Decimal("150.00"))
        self.assertEqual(result.currency, "USD")
    
    def test_money_add_different_currency_raises_error(self):
        """Test adding money with different currency raises error."""
        m1 = Money(Decimal("100.00"), "USD")
        m2 = Money(Decimal("50.00"), "EUR")
        with self.assertRaises(InvariantViolation):
            m1.add(m2)
    
    def test_money_subtract_same_currency(self):
        """Test subtracting money with same currency."""
        m1 = Money(Decimal("100.00"), "USD")
        m2 = Money(Decimal("30.00"), "USD")
        result = m1.subtract(m2)
        self.assertEqual(result.amount, Decimal("70.00"))
    
    def test_money_subtract_results_negative_raises_error(self):
        """Test that subtraction resulting in negative raises error."""
        m1 = Money(Decimal("50.00"), "USD")
        m2 = Money(Decimal("100.00"), "USD")
        with self.assertRaises(InvariantViolation):
            m1.subtract(m2)
    
    def test_money_multiply(self):
        """Test multiplying money by factor."""
        m = Money(Decimal("100.00"), "USD")
        result = m.multiply(Decimal("1.5"))
        self.assertEqual(result.amount, Decimal("150.00"))
    
    def test_money_multiply_negative_factor_raises_error(self):
        """Test that negative multiplication factor raises error."""
        m = Money(Decimal("100.00"), "USD")
        with self.assertRaises(InvariantViolation):
            m.multiply(Decimal("-2"))
    
    def test_money_equality(self):
        """Test money equality comparison."""
        m1 = Money(Decimal("100.00"), "USD")
        m2 = Money(Decimal("100.00"), "USD")
        m3 = Money(Decimal("50.00"), "USD")
        self.assertEqual(m1, m2)
        self.assertNotEqual(m1, m3)
    
    def test_money_comparison_different_currency_raises_error(self):
        """Test comparing money with different currency raises error."""
        m1 = Money(Decimal("100.00"), "USD")
        m2 = Money(Decimal("100.00"), "EUR")
        with self.assertRaises(InvariantViolation):
            m1 < m2


class CapacityValueObjectTests(SimpleTestCase):
    """Test Capacity value object invariants."""
    
    def test_capacity_creation_valid(self):
        """Test creating capacity with valid values."""
        cap = Capacity(total=10, occupied=5)
        self.assertEqual(cap.total, 10)
        self.assertEqual(cap.occupied, 5)
        self.assertEqual(cap.available, 5)
    
    def test_capacity_occupied_exceeds_total_raises_error(self):
        """Test that occupied > total raises error."""
        with self.assertRaises(InvariantViolation):
            Capacity(total=10, occupied=15)
    
    def test_capacity_total_zero_raises_error(self):
        """Test that total < 1 raises error."""
        with self.assertRaises(InvariantViolation):
            Capacity(total=0, occupied=0)
    
    def test_capacity_occupied_negative_raises_error(self):
        """Test that negative occupied raises error."""
        with self.assertRaises(InvariantViolation):
            Capacity(total=10, occupied=-1)
    
    def test_capacity_reserve_spot(self):
        """Test reserving a spot."""
        cap = Capacity(total=10, occupied=5)
        new_cap = cap.reserve_spot()
        self.assertEqual(new_cap.occupied, 6)
        self.assertEqual(new_cap.available, 4)
    
    def test_capacity_reserve_spot_when_full_raises_error(self):
        """Test reserving spot when full raises error."""
        cap = Capacity(total=10, occupied=10)
        with self.assertRaises(InvariantViolation):
            cap.reserve_spot()
    
    def test_capacity_release_spot(self):
        """Test releasing a spot."""
        cap = Capacity(total=10, occupied=5)
        new_cap = cap.release_spot()
        self.assertEqual(new_cap.occupied, 4)
        self.assertEqual(new_cap.available, 6)
    
    def test_capacity_release_spot_when_empty_raises_error(self):
        """Test releasing spot when empty raises error."""
        cap = Capacity(total=10, occupied=0)
        with self.assertRaises(InvariantViolation):
            cap.release_spot()


class BookingAggregateTests(SimpleTestCase):
    """Test BookingAggregate state machine and transitions."""
    
    def test_booking_creation_confirmed(self):
        """Test creating a confirmed booking."""
        booking = BookingAggregate(
            booking_id=1,
            user_id=10,
            class_id=20,
            status=BookingAggregate.CONFIRMED,
        )
        self.assertEqual(booking.status, BookingAggregate.CONFIRMED)
        self.assertIsNone(booking.waitlist_position)
    
    def test_booking_creation_waitlisted(self):
        """Test creating a waitlisted booking."""
        booking = BookingAggregate(
            booking_id=1,
            user_id=10,
            class_id=20,
            status=BookingAggregate.WAITLISTED,
            waitlist_position=2,
        )
        self.assertEqual(booking.status, BookingAggregate.WAITLISTED)
        self.assertEqual(booking.waitlist_position, 2)
    
    def test_promote_from_waitlist(self):
        """Test promoting a booking from waitlist to confirmed."""
        booking = BookingAggregate(
            booking_id=1,
            user_id=10,
            class_id=20,
            status=BookingAggregate.WAITLISTED,
            waitlist_position=1,
        )
        booking.promote_from_waitlist()
        
        self.assertEqual(booking.status, BookingAggregate.CONFIRMED)
        self.assertIsNone(booking.waitlist_position)
        self.assertEqual(len(booking.get_uncommitted_events()), 1)
    
    def test_promote_from_confirmed_raises_error(self):
        """Test promoting from confirmed status raises error."""
        booking = BookingAggregate(
            booking_id=1,
            user_id=10,
            class_id=20,
            status=BookingAggregate.CONFIRMED,
        )
        with self.assertRaises(InvariantViolation):
            booking.promote_from_waitlist()
    
    def test_mark_attended(self):
        """Test marking booking as attended."""
        booking = BookingAggregate(
            booking_id=1,
            user_id=10,
            class_id=20,
            status=BookingAggregate.CONFIRMED,
        )
        booking.mark_attended()
        self.assertEqual(booking.status, BookingAggregate.ATTENDED)
    
    def test_cancel_booking(self):
        """Test cancelling a booking."""
        booking = BookingAggregate(
            booking_id=1,
            user_id=10,
            class_id=20,
            status=BookingAggregate.CONFIRMED,
        )
        booking.cancel()
        
        self.assertEqual(booking.status, BookingAggregate.CANCELLED)
        self.assertEqual(len(booking.get_uncommitted_events()), 1)


class FitnessClassAggregateTests(SimpleTestCase):
    """Test FitnessClassAggregate capacity management."""
    
    def test_fitness_class_with_available_slots(self):
        """Test fitness class with available slots."""
        capacity = Capacity(total=10, occupied=5)
        fitness_class = FitnessClassAggregate(
            class_id=1,
            title="Spinning",
            capacity=capacity,
        )
        self.assertTrue(fitness_class.has_available_slots())
    
    def test_fitness_class_full(self):
        """Test fitness class with no available slots."""
        capacity = Capacity(total=10, occupied=10)
        fitness_class = FitnessClassAggregate(
            class_id=1,
            title="Spinning",
            capacity=capacity,
        )
        self.assertFalse(fitness_class.has_available_slots())
    
    def test_reserve_spot(self):
        """Test reserving a spot in fitness class."""
        capacity = Capacity(total=10, occupied=5)
        fitness_class = FitnessClassAggregate(
            class_id=1,
            title="Spinning",
            capacity=capacity,
        )
        fitness_class.reserve_spot()
        self.assertEqual(fitness_class.capacity.occupied, 6)


class SchedulingServiceTests(SimpleTestCase):
    """Test SchedulingService business logic."""
    
    def test_book_class_with_available_spots(self):
        """Test booking class with available spots."""
        capacity = Capacity(total=10, occupied=5)
        fitness_class = FitnessClassAggregate(
            class_id=20,
            title="Spinning",
            capacity=capacity,
        )
        
        booking = SchedulingService.book_class(
            user_id=10,
            class_id=20,
            class_aggregate=fitness_class,
        )
        
        self.assertEqual(booking.status, BookingAggregate.CONFIRMED)
        self.assertEqual(fitness_class.capacity.occupied, 6)
    
    def test_book_class_when_full(self):
        """Test booking class when full creates waitlisted booking."""
        capacity = Capacity(total=10, occupied=10)
        fitness_class = FitnessClassAggregate(
            class_id=20,
            title="Spinning",
            capacity=capacity,
        )
        
        booking = SchedulingService.book_class(
            user_id=10,
            class_id=20,
            class_aggregate=fitness_class,
        )
        
        self.assertEqual(booking.status, BookingAggregate.WAITLISTED)
        self.assertEqual(fitness_class.capacity.occupied, 10)


class ProductAggregateTests(SimpleTestCase):
    """Test ProductAggregate."""
    
    def test_product_creation(self):
        """Test creating a product."""
        price = Money(Decimal("50.00"), "USD")
        product = ProductAggregate(
            product_id=1,
            name="Monthly Pass",
            price=price,
            valid_days=30,
        )
        self.assertEqual(product.name, "Monthly Pass")
        self.assertEqual(product.price.amount, Decimal("50.00"))
        self.assertEqual(product.valid_days, 30)


class PromotionAggregateTests(SimpleTestCase):
    """Test PromotionAggregate."""
    
    def test_promotion_creation_valid(self):
        """Test creating a promotion with valid discount."""
        promotion = PromotionAggregate(
            promotion_id=1,
            code="SAVE20",
            discount_percentage=Decimal("20"),
        )
        self.assertEqual(promotion.discount_percentage, Decimal("20"))
    
    def test_promotion_discount_out_of_range_raises_error(self):
        """Test that discount > 100 raises error."""
        with self.assertRaises(InvariantViolation):
            PromotionAggregate(
                promotion_id=1,
                code="INVALID",
                discount_percentage=Decimal("150"),
            )
    
    def test_calculate_discount(self):
        """Test calculating discount amount."""
        promotion = PromotionAggregate(
            promotion_id=1,
            code="SAVE20",
            discount_percentage=Decimal("20"),
        )
        price = Money(Decimal("100.00"), "USD")
        discount = promotion.calculate_discount(price)
        self.assertEqual(discount.amount, Decimal("20.00"))


class CommerceServiceTests(SimpleTestCase):
    """Test CommerceService business logic."""
    
    def test_apply_promotion(self):
        """Test applying promotion to a price."""
        price = Money(Decimal("100.00"), "USD")
        promotion = PromotionAggregate(
            promotion_id=1,
            code="SAVE20",
            discount_percentage=Decimal("20"),
        )
        
        discounted = CommerceService.apply_promotion(price, promotion)
        self.assertEqual(discounted.amount, Decimal("80.00"))
    
    def test_create_purchase_without_promotion(self):
        """Test creating a purchase without promotion."""
        price = Money(Decimal("50.00"), "USD")
        product = ProductAggregate(
            product_id=1,
            name="Monthly Pass",
            price=price,
            valid_days=30,
        )
        
        purchase = CommerceService.create_purchase(
            user_id=10,
            product=product,
        )
        
        self.assertEqual(purchase.total_paid.amount, Decimal("50.00"))
        self.assertTrue(purchase.is_valid())
    
    def test_create_purchase_with_promotion(self):
        """Test creating a purchase with promotion."""
        price = Money(Decimal("100.00"), "USD")
        product = ProductAggregate(
            product_id=1,
            name="Yearly Pass",
            price=price,
            valid_days=365,
        )
        promotion = PromotionAggregate(
            promotion_id=1,
            code="SAVE10",
            discount_percentage=Decimal("10"),
        )
        
        purchase = CommerceService.create_purchase(
            user_id=10,
            product=product,
            promotion=promotion,
        )
        
        self.assertEqual(purchase.total_paid.amount, Decimal("90.00"))


class AccessServiceTests(SimpleTestCase):
    """Test AccessService business logic."""
    
    def test_validate_access_with_valid_purchase(self):
        """Test validating access when user has valid purchase."""
        result = AccessService.validate_access(
            user_id=10,
            gym_id=5,
            has_valid_purchase=True,
        )
        self.assertTrue(result)
    
    def test_validate_access_without_purchase(self):
        """Test validating access when user has no valid purchase."""
        result = AccessService.validate_access(
            user_id=10,
            gym_id=5,
            has_valid_purchase=False,
        )
        self.assertFalse(result)
    
    def test_record_check_in(self):
        """Test recording a check-in."""
        checkin = AccessService.record_check_in(
            user_id=10,
            gym_id=5,
        )
        
        self.assertIsNotNone(checkin.checked_in_at)
        self.assertIsNone(checkin.checked_out_at)
        self.assertEqual(len(checkin.get_uncommitted_events()), 1)
