from django.contrib import admin

from .models import Booking, CheckIn, FitnessClass, Gym, Instructor, Notification, Product, Promotion, Purchase, Room, Workout

admin.site.register((Gym, Room, Instructor, Product, Promotion, Purchase, FitnessClass, Booking, CheckIn, Workout, Notification))
