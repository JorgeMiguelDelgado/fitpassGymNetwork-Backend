from django.urls import path

from . import views

app_name = "gym"
urlpatterns = [
    path("gyms/nearby/", views.nearby_gyms, name="nearby-gyms"),
    path("gyms/<int:gym_id>/check-ins/", views.gym_checkin, name="check-in"),
    path("classes/", views.class_list, name="classes"),
    path("classes/<int:class_id>/bookings/", views.create_booking, name="book"),
    path("bookings/<int:booking_id>/cancel/", views.cancel_booking_view, name="cancel-booking"),
    path("bookings/<int:booking_id>/attendance/", views.attendance, name="attendance"),
    path("products/", views.product_list, name="products"),
    path("products/<int:product_id>/purchases/", views.buy_product, name="purchase"),
    path("workouts/", views.workout_list, name="workouts"),
]
