from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .models import Booking, FitnessClass, Gym, Instructor, Notification, Product, Promotion
from .services import book_class, cancel_booking, check_in, purchase_product


class FitPassServicesTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.user1 = users.objects.create_user("member1", password="x")
        self.user2 = users.objects.create_user("member2", password="x")
        instructor_user = users.objects.create_user("coach", password="x")
        self.gym = Gym.objects.create(name="Central", address="La Paz", latitude=-16.5, longitude=-68.15)
        self.instructor = Instructor.objects.create(user=instructor_user)
        self.fitness_class = FitnessClass.objects.create(title="Spinning", gym=self.gym, instructor=self.instructor, starts_at=timezone.now() + timedelta(days=1), ends_at=timezone.now() + timedelta(days=1, hours=1), capacity=1)

    def test_full_class_creates_waitlist_and_cancel_promotes_first(self):
        first, _ = book_class(self.user1, self.fitness_class.pk)
        waiting, _ = book_class(self.user2, self.fitness_class.pk)
        self.assertEqual(first.status, Booking.Status.CONFIRMED)
        self.assertEqual(waiting.status, Booking.Status.WAITLISTED)
        cancel_booking(self.user1, first.pk)
        waiting.refresh_from_db()
        self.assertEqual(waiting.status, Booking.Status.CONFIRMED)
        self.assertTrue(Notification.objects.filter(user=self.user2, kind=Notification.Kind.WAITLIST_PROMOTED).exists())

    def test_national_purchase_supports_checkin_and_promotion(self):
        product = Product.objects.create(name="National day", kind=Product.Kind.DAY_PASS, access_scope=Product.AccessScope.NATIONAL, price="100.00", duration_days=1, session_credits=1)
        now = timezone.now()
        Promotion.objects.create(code="NATIONAL20", percent_off=20, starts_at=now - timedelta(hours=1), ends_at=now + timedelta(days=1))
        purchase = purchase_product(self.user1, product, "valid-token", "NATIONAL20")
        self.assertEqual(str(purchase.amount), "80.00")
        entry = check_in(self.user1, self.gym)
        self.assertEqual(entry.purchase, purchase)
        purchase.refresh_from_db()
        self.assertEqual(purchase.remaining_credits, 0)
