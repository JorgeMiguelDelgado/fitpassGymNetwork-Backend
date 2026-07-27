from django.conf import settings
from django.db import models


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
