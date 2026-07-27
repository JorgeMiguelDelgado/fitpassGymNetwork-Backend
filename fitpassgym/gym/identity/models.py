import secrets

from django.conf import settings
from django.db import models


class ApiToken(models.Model):
    key = models.CharField(max_length=64, unique=True, default=secrets.token_hex, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_token")
    created_at = models.DateTimeField(auto_now_add=True)
