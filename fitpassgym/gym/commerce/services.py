from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.module_loading import import_string

from .models import Promotion, Purchase


@transaction.atomic
def purchase_product(user, product, payment_token, promotion_code=None):
    now = timezone.now()
    promotion = None
    amount = Decimal(product.price)
    if promotion_code:
        promotion = Promotion.objects.filter(
            code__iexact=promotion_code,
            active=True,
            starts_at__lte=now,
            ends_at__gte=now,
        ).first()
        if not promotion or (promotion.gym_id and promotion.gym_id != product.gym_id):
            raise ValidationError("Promotion is invalid for this product.")
        discount = Decimal(100) - promotion.percent_off
        amount = (amount * discount / Decimal(100)).quantize(Decimal("0.01"))

    purchase = Purchase.objects.create(
        user=user,
        product=product,
        promotion=promotion,
        amount=amount,
        currency=product.currency,
        remaining_credits=product.session_credits,
    )
    gateway = import_string(settings.FITPASS_PAYMENT_GATEWAY)()
    result = gateway.charge(
        amount=amount,
        currency=product.currency,
        payment_token=payment_token,
        idempotency_key=str(purchase.pk),
    )
    purchase.status = Purchase.Status.PAID if result.successful else Purchase.Status.FAILED
    purchase.provider_reference = result.reference
    if result.successful:
        purchase.starts_at = now
        purchase.expires_at = now + timedelta(days=product.duration_days)
    purchase.save()
    return purchase
