from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from ..shared.http import error_response, parse_body
from .models import ApiToken


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


@csrf_exempt
@require_POST
def api_login(request):
    try:
        data = parse_body(request)
    except ValidationError as exc:
        return error_response(exc)
    user = authenticate(request, username=data.get("username", ""), password=data.get("password", ""))
    if not user:
        return JsonResponse({"error": "Invalid username or password."}, status=401)
    token, _ = ApiToken.objects.get_or_create(user=user)
    return JsonResponse({
        "token": token.key,
        "user": {"id": user.id, "username": user.username, "name": user.get_full_name()},
    })
