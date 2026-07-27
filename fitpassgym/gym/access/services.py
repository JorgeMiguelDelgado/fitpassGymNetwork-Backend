from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from django.utils.module_loading import import_string

from ..commerce.models import Product, Purchase
from .models import CheckIn


def user_has_access(user, gym, at=None):
    at = at or timezone.now()
    purchases = Purchase.objects.filter(
        user=user,
        status=Purchase.Status.PAID,
        starts_at__lte=at,
        expires_at__gte=at,
    ).select_related("product")
    for purchase in purchases:
        product = purchase.product
        grants_access = product.access_scope == Product.AccessScope.NATIONAL or (
            product.access_scope == Product.AccessScope.LOCAL and product.gym_id == gym.id
        )
        if grants_access and (purchase.remaining_credits is None or purchase.remaining_credits > 0):
            return purchase
    return None


@transaction.atomic
def check_in(user, gym):
    purchase = user_has_access(user, gym)
    if not purchase:
        raise PermissionDenied("No valid access product for this gym.")
    gateway = import_string(settings.FITPASS_DOOR_GATEWAY)()
    door_reference = gateway.grant_access(gym_id=gym.id, user_id=user.id)
    if purchase.remaining_credits is not None:
        purchase.remaining_credits -= 1
        purchase.save(update_fields=("remaining_credits",))
    return CheckIn.objects.create(
        user=user,
        gym=gym,
        purchase=purchase,
        door_reference=door_reference,
    )
