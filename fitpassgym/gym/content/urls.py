from django.urls import path

from . import api

urlpatterns = [path("workouts/", api.workout_list, name="workouts")]
