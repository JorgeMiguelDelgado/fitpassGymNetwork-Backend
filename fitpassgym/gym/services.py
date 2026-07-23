from datetime import timedelta
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.module_loading import import_string

from .models import Booking, CheckIn, FitnessClass, Notification, Promotion, Purchase


def find_nearby_gyms(queryset, latitude, longitude, radius_km=25):
    """Database-agnostic Haversine search, suitable until a spatial DB is introduced."""
    def distance(gym):
        lat1, lon1, lat2, lon2 = map(radians, (float(latitude), float(longitude), float(gym.latitude), float(gym.longitude)))
        return 6371 * 2 * asin(sqrt(sin((lat2-lat1)/2)**2 + cos(lat1)*cos(lat2)*sin((lon2-lon1)/2)**2))

    results = [(gym, distance(gym)) for gym in queryset.filter(active=True)]
    return sorted(((gym, km) for gym, km in results if km <= float(radius_km)), key=lambda item: item[1])


def user_has_access(user, gym, at=None):
    at = at or timezone.now()
    purchases = Purchase.objects.filter(user=user, status=Purchase.Status.PAID, starts_at__lte=at, expires_at__gte=at).select_related("product")
    for purchase in purchases:
        product = purchase.product
        if product.access_scope == product.AccessScope.NATIONAL or (product.access_scope == product.AccessScope.LOCAL and product.gym_id == gym.id):
            if purchase.remaining_credits is None or purchase.remaining_credits > 0:
                return purchase
    return None


@transaction.atomic
def book_class(user, class_id):
    fitness_class = FitnessClass.objects.select_for_update().get(pk=class_id)
    if fitness_class.status != FitnessClass.Status.SCHEDULED or fitness_class.starts_at <= timezone.now():
        raise ValidationError("This class cannot be booked.")
    existing = Booking.objects.filter(user=user, fitness_class=fitness_class).first()
    if existing and existing.status != Booking.Status.CANCELLED:
        return existing, False
    confirmed = Booking.objects.filter(fitness_class=fitness_class, status__in=[Booking.Status.CONFIRMED, Booking.Status.ATTENDED]).count()
    status, position = Booking.Status.CONFIRMED, None
    if confirmed >= fitness_class.capacity:
        status = Booking.Status.WAITLISTED
        position = (Booking.objects.filter(fitness_class=fitness_class, status=Booking.Status.WAITLISTED).aggregate(Max("waitlist_position"))["waitlist_position__max"] or 0) + 1
    if existing:
        existing.status, existing.waitlist_position = status, position
        existing.save(update_fields=("status", "waitlist_position", "updated_at"))
        return existing, True
    return Booking.objects.create(user=user, fitness_class=fitness_class, status=status, waitlist_position=position), True


@transaction.atomic
def cancel_booking(user, booking_id):
    booking = Booking.objects.select_for_update().select_related("fitness_class").get(pk=booking_id, user=user)
    if booking.status not in (Booking.Status.CONFIRMED, Booking.Status.WAITLISTED):
        raise ValidationError("This booking cannot be cancelled.")
    was_confirmed = booking.status == Booking.Status.CONFIRMED
    booking.status, booking.waitlist_position = Booking.Status.CANCELLED, None
    booking.save(update_fields=("status", "waitlist_position", "updated_at"))
    if was_confirmed:
        promoted = Booking.objects.select_for_update().filter(fitness_class=booking.fitness_class, status=Booking.Status.WAITLISTED).order_by("waitlist_position", "created_at").first()
        if promoted:
            promoted.status, promoted.waitlist_position = Booking.Status.CONFIRMED, None
            promoted.save(update_fields=("status", "waitlist_position", "updated_at"))
            Notification.objects.create(user=promoted.user, kind=Notification.Kind.WAITLIST_PROMOTED, message=f"Your place in {booking.fitness_class.title} is confirmed.", data={"class_id": booking.fitness_class_id})
    # Compact positions after cancellations.
    for position, queued in enumerate(Booking.objects.filter(fitness_class=booking.fitness_class, status=Booking.Status.WAITLISTED).order_by("waitlist_position", "created_at"), 1):
        if queued.waitlist_position != position:
            queued.waitlist_position = position
            queued.save(update_fields=("waitlist_position",))
    return booking


@transaction.atomic
def record_attendance(instructor_user, booking_id, attended):
    booking = Booking.objects.select_for_update().select_related("fitness_class__instructor").get(pk=booking_id)
    if booking.fitness_class.instructor.user_id != instructor_user.id and not instructor_user.is_staff:
        raise PermissionDenied("Only the assigned instructor can manage attendance.")
    if booking.status != Booking.Status.CONFIRMED:
        raise ValidationError("Only confirmed bookings can receive attendance.")
    booking.status = Booking.Status.ATTENDED if attended else Booking.Status.NO_SHOW
    booking.save(update_fields=("status", "updated_at"))
    return booking


@transaction.atomic
def purchase_product(user, product, payment_token, promotion_code=None):
    now = timezone.now()
    promotion = None
    # Callers may pass a freshly-created model whose DecimalField value has not
    # yet been reloaded from the database and is therefore still a string.
    amount = Decimal(product.price)
    if promotion_code:
        promotion = Promotion.objects.filter(code__iexact=promotion_code, active=True, starts_at__lte=now, ends_at__gte=now).first()
        if not promotion or (promotion.gym_id and promotion.gym_id != product.gym_id):
            raise ValidationError("Promotion is invalid for this product.")
        amount = (amount * (Decimal(100) - promotion.percent_off) / Decimal(100)).quantize(Decimal("0.01"))
    purchase = Purchase.objects.create(user=user, product=product, promotion=promotion, amount=amount, currency=product.currency, remaining_credits=product.session_credits)
    gateway = import_string(settings.FITPASS_PAYMENT_GATEWAY)()
    result = gateway.charge(amount=amount, currency=product.currency, payment_token=payment_token, idempotency_key=str(purchase.pk))
    purchase.status = Purchase.Status.PAID if result.successful else Purchase.Status.FAILED
    purchase.provider_reference = result.reference
    if result.successful:
        purchase.starts_at, purchase.expires_at = now, now + timedelta(days=product.duration_days)
    purchase.save()
    return purchase


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
    return CheckIn.objects.create(user=user, gym=gym, purchase=purchase, door_reference=door_reference)
