"""Compatibility facade for the public model API.

Models are owned by business modules. Re-exporting them here keeps Django
migrations and existing integrations compatible with the original monolith.
"""

from .access.models import CheckIn
from .commerce.models import Product, Promotion, Purchase
from .content.models import Workout
from .identity.models import ApiToken
from .locations.models import Gym, Instructor, Room
from .notifications.models import Notification
from .scheduling.models import Booking, FitnessClass

__all__ = [
    "ApiToken", "Booking", "CheckIn", "FitnessClass", "Gym", "Instructor",
    "Notification", "Product", "Promotion", "Purchase", "Room", "Workout",
]
