import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from .models import Booking, FitnessClass, Gym, Product, Workout
from .services import book_class, cancel_booking, check_in, find_nearby_gyms, purchase_product, record_attendance


@require_GET
def api_root(request):
    return JsonResponse({
        "name": "FitPass Gym API",
        "status": "running",
        "endpoints": {
            "admin": "/admin/",
            "nearby_gyms": "/api/gyms/nearby/?lat=-16.5&lon=-68.15&radius_km=10",
            "classes": "/api/classes/",
            "products": "/api/products/",
            "workouts": "/api/workouts/",
        },
    })


def _body(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError as exc:
        raise ValidationError("Invalid JSON body.") from exc


def _error_response(exc):
    if isinstance(exc, PermissionDenied):
        return JsonResponse({"error": str(exc)}, status=403)
    messages = exc.messages if isinstance(exc, ValidationError) else [str(exc)]
    return JsonResponse({"error": messages}, status=400)


@require_GET
def nearby_gyms(request):
    try:
        latitude = float(request.GET["lat"])
        longitude = float(request.GET["lon"])
        radius = min(float(request.GET.get("radius_km", 25)), 200)
    except (KeyError, TypeError, ValueError):
        return JsonResponse({"error": "lat, lon and a numeric radius_km are required."}, status=400)
    results = find_nearby_gyms(Gym.objects.all(), latitude, longitude, radius)
    return JsonResponse({"results": [{"id": gym.id, "name": gym.name, "address": gym.address, "country_code": gym.country_code, "distance_km": round(km, 2), "equipment": gym.equipment} for gym, km in results]})


@require_GET
def class_list(request):
    classes = FitnessClass.objects.filter(status=FitnessClass.Status.SCHEDULED).select_related("gym", "instructor__user")
    if request.GET.get("gym_id"):
        classes = classes.filter(gym_id=request.GET["gym_id"])
    return JsonResponse({"results": [{"id": item.id, "title": item.title, "gym": item.gym.name if item.gym else None, "starts_at": item.starts_at.isoformat(), "ends_at": item.ends_at.isoformat(), "capacity": item.capacity, "is_virtual": item.is_virtual, "instructor": item.instructor.user.get_full_name() or item.instructor.user.username} for item in classes.order_by("starts_at")]})


@login_required
@require_POST
def create_booking(request, class_id):
    try:
        booking, created = book_class(request.user, class_id)
        return JsonResponse({"id": booking.id, "status": booking.status, "waitlist_position": booking.waitlist_position}, status=201 if created else 200)
    except (ValidationError, FitnessClass.DoesNotExist) as exc:
        return _error_response(exc)


@login_required
@require_POST
def cancel_booking_view(request, booking_id):
    try:
        booking = cancel_booking(request.user, booking_id)
        return JsonResponse({"id": booking.id, "status": booking.status})
    except (ValidationError, Booking.DoesNotExist) as exc:
        return _error_response(exc)


@login_required
@require_POST
def attendance(request, booking_id):
    try:
        booking = record_attendance(request.user, booking_id, bool(_body(request).get("attended")))
        return JsonResponse({"id": booking.id, "status": booking.status})
    except (ValidationError, PermissionDenied, Booking.DoesNotExist) as exc:
        return _error_response(exc)


@login_required
@require_POST
def gym_checkin(request, gym_id):
    try:
        entry = check_in(request.user, get_object_or_404(Gym, pk=gym_id, active=True))
        return JsonResponse({"id": entry.id, "checked_in_at": entry.checked_in_at.isoformat(), "door_reference": entry.door_reference}, status=201)
    except (ValidationError, PermissionDenied) as exc:
        return _error_response(exc)


@require_GET
def product_list(request):
    products = Product.objects.filter(active=True)
    return JsonResponse({"results": [{"id": item.id, "name": item.name, "kind": item.kind, "access_scope": item.access_scope, "gym_id": item.gym_id, "price": str(item.price), "currency": item.currency} for item in products]})


@login_required
@require_POST
def buy_product(request, product_id):
    try:
        data = _body(request)
        purchase = purchase_product(request.user, get_object_or_404(Product, pk=product_id, active=True), data.get("payment_token", ""), data.get("promotion_code"))
        return JsonResponse({"id": purchase.id, "status": purchase.status, "amount": str(purchase.amount), "currency": purchase.currency, "expires_at": purchase.expires_at.isoformat() if purchase.expires_at else None}, status=201)
    except ValidationError as exc:
        return _error_response(exc)


@login_required
@require_GET
def workout_list(request):
    workouts = Workout.objects.filter(published=True)
    return JsonResponse({"results": [{"id": item.id, "title": item.title, "video_url": item.video_url, "duration_minutes": item.duration_minutes, "equipment": item.equipment} for item in workouts]})
