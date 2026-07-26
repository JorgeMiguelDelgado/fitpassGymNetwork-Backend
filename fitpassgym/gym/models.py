from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
import secrets


class Gym(models.Model):
    name = models.CharField(max_length=150)
    country_code = models.CharField(max_length=2, default="BO")
    address = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    timezone = models.CharField(max_length=64, default="America/La_Paz")
    equipment = models.JSONField(default=list, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Room(models.Model):
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, related_name="rooms")
    name = models.CharField(max_length=100)
    capacity = models.PositiveIntegerField()
    equipment = models.JSONField(default=list, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("gym", "name"), name="unique_room_per_gym")]


class Instructor(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    gyms = models.ManyToManyField(Gym, related_name="instructors", blank=True)
    specialties = models.JSONField(default=list, blank=True)


class ApiToken(models.Model):
    key = models.CharField(max_length=64, unique=True, default=secrets.token_hex, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_token")
    created_at = models.DateTimeField(auto_now_add=True)


class Product(models.Model):
    class Kind(models.TextChoices):
        MEMBERSHIP = "membership", "Membership"
        DAY_PASS = "day_pass", "Day pass"
        TRAINING = "training", "Training package"

    class AccessScope(models.TextChoices):
        NATIONAL = "national", "National"
        LOCAL = "local", "Local"
        VIRTUAL = "virtual", "Virtual"

    name = models.CharField(max_length=150)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    access_scope = models.CharField(max_length=20, choices=AccessScope.choices)
    gym = models.ForeignKey(Gym, null=True, blank=True, on_delete=models.CASCADE, related_name="products")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="BOB")
    duration_days = models.PositiveIntegerField(default=1)
    session_credits = models.PositiveIntegerField(null=True, blank=True)
    active = models.BooleanField(default=True)

    def clean(self):
        if self.access_scope == self.AccessScope.LOCAL and not self.gym_id:
            raise ValidationError({"gym": "A local product requires a gym."})


class Promotion(models.Model):
    code = models.CharField(max_length=40, unique=True)
    gym = models.ForeignKey(Gym, null=True, blank=True, on_delete=models.CASCADE, related_name="promotions")
    percent_off = models.PositiveSmallIntegerField()
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    active = models.BooleanField(default=True)

    def clean(self):
        if not 1 <= self.percent_off <= 100:
            raise ValidationError({"percent_off": "Must be between 1 and 100."})
        if self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "Must be after starts_at."})


class Purchase(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="purchases")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    promotion = models.ForeignKey(Promotion, null=True, blank=True, on_delete=models.SET_NULL)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    provider_reference = models.CharField(max_length=150, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    remaining_credits = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class FitnessClass(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    title = models.CharField(max_length=150)
    gym = models.ForeignKey(Gym, null=True, blank=True, on_delete=models.CASCADE, related_name="classes")
    room = models.ForeignKey(Room, null=True, blank=True, on_delete=models.PROTECT, related_name="classes")
    instructor = models.ForeignKey(Instructor, on_delete=models.PROTECT, related_name="classes")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    capacity = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    is_virtual = models.BooleanField(default=False)
    stream_url = models.URLField(blank=True)
    recording_url = models.URLField(blank=True)
    version = models.PositiveIntegerField(default=1)

    def clean(self):
        if self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "Must be after starts_at."})
        if not self.is_virtual and not self.gym_id:
            raise ValidationError({"gym": "An in-person class requires a gym."})


class Booking(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed"
        WAITLISTED = "waitlisted", "Waitlisted"
        CANCELLED = "cancelled", "Cancelled"
        ATTENDED = "attended", "Attended"
        NO_SHOW = "no_show", "No show"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookings")
    fitness_class = models.ForeignKey(FitnessClass, on_delete=models.CASCADE, related_name="bookings")
    status = models.CharField(max_length=20, choices=Status.choices)
    waitlist_position = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("user", "fitness_class"), name="unique_user_class_booking")]


class CheckIn(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="checkins")
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, related_name="checkins")
    purchase = models.ForeignKey(Purchase, on_delete=models.PROTECT, related_name="checkins")
    checked_in_at = models.DateTimeField(auto_now_add=True)
    door_reference = models.CharField(max_length=150, blank=True)


class Workout(models.Model):
    title = models.CharField(max_length=150)
    video_url = models.URLField()
    duration_minutes = models.PositiveIntegerField()
    equipment = models.JSONField(default=list, blank=True)
    published = models.BooleanField(default=False)


class Notification(models.Model):
    class Kind(models.TextChoices):
        CLASS_CHANGED = "class_changed", "Class changed"
        CLASS_CANCELLED = "class_cancelled", "Class cancelled"
        REMINDER = "reminder", "Reminder"
        WAITLIST_PROMOTED = "waitlist_promoted", "Waitlist promoted"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=30, choices=Kind.choices)
    message = models.CharField(max_length=300)
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
