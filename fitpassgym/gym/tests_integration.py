"""Integration tests for critical Session II endpoints."""

from datetime import timedelta
from json import loads

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Booking, FitnessClass, Gym, Instructor, Product, Promotion
from .services import purchase_product


User = get_user_model()


class BookingEndpointsTests(TestCase):
    """Test reservation and waitlist endpoints."""

    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user("member1", password="pass1234")
        self.user2 = User.objects.create_user("member2", password="pass1234")
        
        instructor_user = User.objects.create_user("coach", password="pass1234")
        self.gym = Gym.objects.create(
            name="Central Gym",
            address="La Paz",
            latitude=-16.5,
            longitude=-68.15,
        )
        self.instructor = Instructor.objects.create(user=instructor_user)
        self.fitness_class = FitnessClass.objects.create(
            title="Spinning",
            gym=self.gym,
            instructor=self.instructor,
            starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1, hours=1),
            capacity=1,
        )

    def test_get_class_list_returns_scheduled_classes(self):
        """GET /api/classes/ should return scheduled classes."""
        response = self.client.get(reverse("gym:classes"))
        self.assertEqual(response.status_code, 200)
        data = loads(response.content)
        self.assertIn("results", data)
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["title"], "Spinning")

    def test_get_class_list_filters_by_gym(self):
        """GET /api/classes/?gym_id=X should filter by gym."""
        other_gym = Gym.objects.create(
            name="Other Gym",
            address="Cochabamba",
            latitude=-17.4,
            longitude=-66.2,
        )
        other_class = FitnessClass.objects.create(
            title="Yoga",
            gym=other_gym,
            instructor=self.instructor,
            starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1, hours=1),
            capacity=10,
        )
        
        response = self.client.get(reverse("gym:classes") + f"?gym_id={self.gym.id}")
        data = loads(response.content)
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["id"], self.fitness_class.id)

    def test_post_booking_creates_confirmed_when_space_available(self):
        """POST /api/classes/{id}/bookings/ should create confirmed booking when space exists."""
        self.client.login(username="member1", password="pass1234")
        response = self.client.post(
            reverse("gym:book", args=[self.fitness_class.id])
        )
        self.assertEqual(response.status_code, 201)
        data = loads(response.content)
        self.assertEqual(data["status"], Booking.Status.CONFIRMED)
        self.assertIsNone(data["waitlist_position"])

    def test_post_booking_creates_waitlisted_when_full(self):
        """POST /api/classes/{id}/bookings/ should create waitlisted booking when full."""
        Booking.objects.create(
            user=self.user1,
            fitness_class=self.fitness_class,
            status=Booking.Status.CONFIRMED,
        )
        self.client.login(username="member2", password="pass1234")
        response = self.client.post(
            reverse("gym:book", args=[self.fitness_class.id])
        )
        self.assertEqual(response.status_code, 201)
        data = loads(response.content)
        self.assertEqual(data["status"], Booking.Status.WAITLISTED)
        self.assertEqual(data["waitlist_position"], 1)

    def test_post_booking_requires_authentication(self):
        """POST /api/classes/{id}/bookings/ should require login."""
        response = self.client.post(
            reverse("gym:book", args=[self.fitness_class.id])
        )
        self.assertEqual(response.status_code, 401)

    def test_post_cancel_booking_promotes_waitlist(self):
        """POST /api/bookings/{id}/cancel/ should promote next user from waitlist."""
        booking1 = Booking.objects.create(
            user=self.user1,
            fitness_class=self.fitness_class,
            status=Booking.Status.CONFIRMED,
        )
        booking2 = Booking.objects.create(
            user=self.user2,
            fitness_class=self.fitness_class,
            status=Booking.Status.WAITLISTED,
            waitlist_position=1,
        )
        
        self.client.login(username="member1", password="pass1234")
        response = self.client.post(
            reverse("gym:cancel-booking", args=[booking1.id])
        )
        self.assertEqual(response.status_code, 200)
        
        booking2.refresh_from_db()
        self.assertEqual(booking2.status, Booking.Status.CONFIRMED)
        self.assertIsNone(booking2.waitlist_position)

    def test_get_booking_list_returns_user_bookings(self):
        """GET /api/bookings/ should return current user's bookings."""
        Booking.objects.create(
            user=self.user1,
            fitness_class=self.fitness_class,
            status=Booking.Status.CONFIRMED,
        )
        
        self.client.login(username="member1", password="pass1234")
        response = self.client.get(reverse("gym:bookings"))
        self.assertEqual(response.status_code, 200)
        data = loads(response.content)
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["title"], "Spinning")

    def test_get_booking_list_requires_authentication(self):
        """GET /api/bookings/ should require login."""
        response = self.client.get(reverse("gym:bookings"))
        self.assertEqual(response.status_code, 401)

    def test_post_attendance_only_instructor_can_mark(self):
        """POST /api/bookings/{id}/attendance/ should only allow instructors."""
        booking = Booking.objects.create(
            user=self.user1,
            fitness_class=self.fitness_class,
            status=Booking.Status.CONFIRMED,
        )
        
        # Non-instructor should fail
        self.client.login(username="member1", password="pass1234")
        response = self.client.post(
            reverse("gym:attendance", args=[booking.id]),
            data='{"attended": true}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        
        # Instructor should succeed
        self.client.logout()
        self.client.login(username="coach", password="pass1234")
        response = self.client.post(
            reverse("gym:attendance", args=[booking.id]),
            data='{"attended": true}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = loads(response.content)
        self.assertEqual(data["status"], Booking.Status.ATTENDED)


class PurchaseEndpointsTests(TestCase):
    """Test product and purchase endpoints."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("buyer", password="pass1234")
        self.gym = Gym.objects.create(
            name="Central Gym",
            address="La Paz",
            latitude=-16.5,
            longitude=-68.15,
        )
        self.product = Product.objects.create(
            name="National Day Pass",
            kind=Product.Kind.DAY_PASS,
            access_scope=Product.AccessScope.NATIONAL,
            price="100.00",
            duration_days=1,
            session_credits=1,
        )

    def test_get_products_returns_active_products(self):
        """GET /api/products/ should return active products."""
        response = self.client.get(reverse("gym:products"))
        self.assertEqual(response.status_code, 200)
        data = loads(response.content)
        self.assertIn("results", data)
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["name"], "National Day Pass")

    def test_post_purchase_with_promotion_applies_discount(self):
        """POST /api/products/{id}/purchases/ should apply valid promotion."""
        now = timezone.now()
        Promotion.objects.create(
            code="INTRO20",
            percent_off=20,
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(days=1),
        )
        
        self.client.login(username="buyer", password="pass1234")
        response = self.client.post(
            reverse("gym:purchase", args=[self.product.id]),
            data='{"payment_token": "token_123", "promotion_code": "INTRO20"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = loads(response.content)
        self.assertEqual(data["amount"], "80.00")

    def test_post_purchase_requires_authentication(self):
        """POST /api/products/{id}/purchases/ should require login."""
        response = self.client.post(
            reverse("gym:purchase", args=[self.product.id]),
            data='{"payment_token": "token_123"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)


class NearbyGymsEndpointTests(TestCase):
    """Test nearby gyms location search endpoint."""

    def setUp(self):
        self.client = Client()
        self.gym1 = Gym.objects.create(
            name="Central",
            address="La Paz Center",
            latitude=-16.5,
            longitude=-68.15,
        )
        self.gym2 = Gym.objects.create(
            name="North",
            address="La Paz North",
            latitude=-16.48,
            longitude=-68.15,
        )

    def test_nearby_gyms_returns_results_sorted_by_distance(self):
        """GET /api/gyms/nearby/?lat=X&lon=Y should return sorted by distance."""
        response = self.client.get(
            reverse("gym:nearby-gyms") + "?lat=-16.5&lon=-68.15&radius_km=10"
        )
        self.assertEqual(response.status_code, 200)
        data = loads(response.content)
        self.assertEqual(len(data["results"]), 2)
        # Central should be first (0 distance), then North
        self.assertEqual(data["results"][0]["name"], "Central")
        self.assertEqual(data["results"][1]["name"], "North")
        self.assertLess(data["results"][0]["distance_km"], data["results"][1]["distance_km"])
