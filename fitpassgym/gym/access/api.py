from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from ..locations.models import Gym
from ..shared.http import api_login_required, error_response
from .services import check_in


@api_login_required
@require_POST
def gym_checkin(request, gym_id):
    try:
        entry = check_in(request.user, get_object_or_404(Gym, pk=gym_id, active=True))
        return JsonResponse({
            "id": entry.id,
            "checked_in_at": entry.checked_in_at.isoformat(),
            "door_reference": entry.door_reference,
        }, status=201)
    except (ValidationError, PermissionDenied) as exc:
        return error_response(exc)
