import json
from functools import wraps

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ..identity.models import ApiToken


def parse_body(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError as exc:
        raise ValidationError("Invalid JSON body.") from exc


def error_response(exc):
    if isinstance(exc, PermissionDenied):
        return JsonResponse({"error": str(exc)}, status=403)
    messages = exc.messages if isinstance(exc, ValidationError) else [str(exc)]
    return JsonResponse({"error": messages}, status=400)


def api_login_required(view):
    """Accept a Django session or an Authorization: Token header."""
    @csrf_exempt
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            authorization = request.headers.get("Authorization", "")
            if authorization.startswith("Token "):
                token = ApiToken.objects.select_related("user").filter(key=authorization[6:]).first()
                if token:
                    request.user = token.user
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required."}, status=401)
        return view(request, *args, **kwargs)
    return wrapped
