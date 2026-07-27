from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from ..shared.http import api_login_required, error_response, parse_body
from .models import Booking, FitnessClass
from .services import book_class, cancel_booking, record_attendance


@require_GET
def class_list(request):
    classes = FitnessClass.objects.filter(status=FitnessClass.Status.SCHEDULED).select_related(
        "gym", "instructor__user",
    )
    if request.GET.get("gym_id"):
        classes = classes.filter(gym_id=request.GET["gym_id"])
    return JsonResponse({"results": [{
        "id": item.id, "title": item.title,
        "gym": item.gym.name if item.gym else None,
        "starts_at": item.starts_at.isoformat(), "ends_at": item.ends_at.isoformat(),
        "capacity": item.capacity, "is_virtual": item.is_virtual,
        "instructor": item.instructor.user.get_full_name() or item.instructor.user.username,
    } for item in classes.order_by("starts_at")]})


@api_login_required
@require_POST
def create_booking(request, class_id):
    try:
        booking, created = book_class(request.user, class_id)
        return JsonResponse({
            "id": booking.id, "status": booking.status,
            "waitlist_position": booking.waitlist_position,
        }, status=201 if created else 200)
    except (ValidationError, FitnessClass.DoesNotExist) as exc:
        return error_response(exc)


@api_login_required
@require_POST
def cancel_booking_view(request, booking_id):
    try:
        booking = cancel_booking(request.user, booking_id)
        return JsonResponse({"id": booking.id, "status": booking.status})
    except (ValidationError, Booking.DoesNotExist) as exc:
        return error_response(exc)


@api_login_required
@require_POST
def attendance(request, booking_id):
    try:
        booking = record_attendance(request.user, booking_id, bool(parse_body(request).get("attended")))
        return JsonResponse({"id": booking.id, "status": booking.status})
    except (ValidationError, PermissionDenied, Booking.DoesNotExist) as exc:
        return error_response(exc)


@api_login_required
@require_GET
def booking_list(request):
    bookings = Booking.objects.filter(user=request.user).select_related(
        "fitness_class__gym",
    ).order_by("-created_at")
    return JsonResponse({"results": [{
        "id": item.id, "class_id": item.fitness_class_id,
        "title": item.fitness_class.title,
        "gym": item.fitness_class.gym.name if item.fitness_class.gym else None,
        "starts_at": item.fitness_class.starts_at.isoformat(),
        "status": item.status, "waitlist_position": item.waitlist_position,
    } for item in bookings]})
