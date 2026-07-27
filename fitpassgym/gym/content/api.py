from django.http import JsonResponse
from django.views.decorators.http import require_GET

from ..shared.http import api_login_required
from .models import Workout


@api_login_required
@require_GET
def workout_list(request):
    workouts = Workout.objects.filter(published=True)
    return JsonResponse({"results": [{
        "id": item.id, "title": item.title, "video_url": item.video_url,
        "duration_minutes": item.duration_minutes, "equipment": item.equipment,
    } for item in workouts]})
