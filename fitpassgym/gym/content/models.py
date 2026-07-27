from django.db import models


class Workout(models.Model):
    title = models.CharField(max_length=150)
    video_url = models.URLField()
    duration_minutes = models.PositiveIntegerField()
    equipment = models.JSONField(default=list, blank=True)
    published = models.BooleanField(default=False)
