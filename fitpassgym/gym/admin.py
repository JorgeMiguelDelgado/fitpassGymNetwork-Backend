from django.contrib import admin

from .models import ApiToken, Booking, CheckIn, FitnessClass, Gym, Instructor, Notification, Product, Promotion, Purchase, Room, Workout

admin.site.register((ApiToken, Gym, Room, Instructor, Product, Promotion, Purchase, FitnessClass, Booking, CheckIn, Workout, Notification))
