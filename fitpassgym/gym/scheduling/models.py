from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from ..locations.models import Gym, Instructor, Room


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
