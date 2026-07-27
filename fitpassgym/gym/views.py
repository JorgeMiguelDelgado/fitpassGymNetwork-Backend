"""Compatibility facade for HTTP views owned by business modules."""

from .access.api import gym_checkin
from .commerce.api import buy_product, product_list
from .content.api import workout_list
from .identity.api import api_login, api_root
from .locations.api import nearby_gyms
from .scheduling.api import attendance, booking_list, cancel_booking_view, class_list, create_booking

__all__ = [
    "api_login", "api_root", "attendance", "booking_list", "buy_product",
    "cancel_booking_view", "class_list", "create_booking", "gym_checkin",
    "nearby_gyms", "product_list", "workout_list",
]
