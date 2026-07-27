from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import Gym
from .services import find_nearby_gyms


@require_GET
def nearby_gyms(request):
    try:
        latitude = float(request.GET["lat"])
        longitude = float(request.GET["lon"])
        radius = min(float(request.GET.get("radius_km", 25)), 200)
    except (KeyError, TypeError, ValueError):
        return JsonResponse({"error": "lat, lon and a numeric radius_km are required."}, status=400)
    results = find_nearby_gyms(Gym.objects.all(), latitude, longitude, radius)
    return JsonResponse({"results": [{
        "id": gym.id,
        "name": gym.name,
        "address": gym.address,
        "country_code": gym.country_code,
        "distance_km": round(km, 2),
        "equipment": gym.equipment,
    } for gym, km in results]})
