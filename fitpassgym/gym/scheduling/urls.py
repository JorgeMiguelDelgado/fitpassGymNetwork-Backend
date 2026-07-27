from django.urls import path

from . import api

urlpatterns = [
    path("classes/", api.class_list, name="classes"),
    path("classes/<int:class_id>/bookings/", api.create_booking, name="book"),
    path("bookings/<int:booking_id>/cancel/", api.cancel_booking_view, name="cancel-booking"),
    path("bookings/", api.booking_list, name="bookings"),
    path("bookings/<int:booking_id>/attendance/", api.attendance, name="attendance"),
]
