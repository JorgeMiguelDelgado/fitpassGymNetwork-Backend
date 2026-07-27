"""Compatibility facade for module application services."""

from .access.services import check_in, user_has_access
from .commerce.services import purchase_product
from .locations.services import find_nearby_gyms
from .scheduling.services import book_class, cancel_booking, record_attendance

__all__ = [
    "book_class", "cancel_booking", "check_in", "find_nearby_gyms",
    "purchase_product", "record_attendance", "user_has_access",
]
