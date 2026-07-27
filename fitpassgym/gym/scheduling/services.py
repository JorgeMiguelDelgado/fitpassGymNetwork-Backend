from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from ..notifications.models import Notification
from .models import Booking, FitnessClass


@transaction.atomic
def book_class(user, class_id):
    fitness_class = FitnessClass.objects.select_for_update().get(pk=class_id)
    if fitness_class.status != FitnessClass.Status.SCHEDULED or fitness_class.starts_at <= timezone.now():
        raise ValidationError("This class cannot be booked.")
    existing = Booking.objects.filter(user=user, fitness_class=fitness_class).first()
    if existing and existing.status != Booking.Status.CANCELLED:
        return existing, False
    confirmed = Booking.objects.filter(
        fitness_class=fitness_class,
        status__in=[Booking.Status.CONFIRMED, Booking.Status.ATTENDED],
    ).count()
    status, position = Booking.Status.CONFIRMED, None
    if confirmed >= fitness_class.capacity:
        status = Booking.Status.WAITLISTED
        maximum = Booking.objects.filter(
            fitness_class=fitness_class,
            status=Booking.Status.WAITLISTED,
        ).aggregate(Max("waitlist_position"))["waitlist_position__max"] or 0
        position = maximum + 1
    if existing:
        existing.status, existing.waitlist_position = status, position
        existing.save(update_fields=("status", "waitlist_position", "updated_at"))
        return existing, True
    return Booking.objects.create(
        user=user,
        fitness_class=fitness_class,
        status=status,
        waitlist_position=position,
    ), True


@transaction.atomic
def cancel_booking(user, booking_id):
    booking = Booking.objects.select_for_update().select_related("fitness_class").get(
        pk=booking_id,
        user=user,
    )
    if booking.status not in (Booking.Status.CONFIRMED, Booking.Status.WAITLISTED):
        raise ValidationError("This booking cannot be cancelled.")
    was_confirmed = booking.status == Booking.Status.CONFIRMED
    booking.status, booking.waitlist_position = Booking.Status.CANCELLED, None
    booking.save(update_fields=("status", "waitlist_position", "updated_at"))
    if was_confirmed:
        promoted = Booking.objects.select_for_update().filter(
            fitness_class=booking.fitness_class,
            status=Booking.Status.WAITLISTED,
        ).order_by("waitlist_position", "created_at").first()
        if promoted:
            promoted.status, promoted.waitlist_position = Booking.Status.CONFIRMED, None
            promoted.save(update_fields=("status", "waitlist_position", "updated_at"))
            Notification.objects.create(
                user=promoted.user,
                kind=Notification.Kind.WAITLIST_PROMOTED,
                message=f"Your place in {booking.fitness_class.title} is confirmed.",
                data={"class_id": booking.fitness_class_id},
            )
    queued_bookings = Booking.objects.filter(
        fitness_class=booking.fitness_class,
        status=Booking.Status.WAITLISTED,
    ).order_by("waitlist_position", "created_at")
    for position, queued in enumerate(queued_bookings, 1):
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
