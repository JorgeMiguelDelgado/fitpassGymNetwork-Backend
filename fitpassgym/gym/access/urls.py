from django.urls import path

from . import api

urlpatterns = [path("gyms/<int:gym_id>/check-ins/", api.gym_checkin, name="check-in")]
