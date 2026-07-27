from django.conf import settings
from django.db import models

from ..commerce.models import Purchase
from ..locations.models import Gym


class CheckIn(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="checkins")
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, related_name="checkins")
    purchase = models.ForeignKey(Purchase, on_delete=models.PROTECT, related_name="checkins")
    checked_in_at = models.DateTimeField(auto_now_add=True)
    door_reference = models.CharField(max_length=150, blank=True)
