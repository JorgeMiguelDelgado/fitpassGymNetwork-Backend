from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from ..locations.models import Gym


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
