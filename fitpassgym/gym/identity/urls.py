from django.urls import path

from . import api

urlpatterns = [path("auth/login/", api.api_login, name="api-login")]
