from django.urls import path

from . import api

urlpatterns = [path("gyms/nearby/", api.nearby_gyms, name="nearby-gyms")]
