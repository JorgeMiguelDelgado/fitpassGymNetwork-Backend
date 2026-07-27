from django.conf import settings
from django.db import models


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
