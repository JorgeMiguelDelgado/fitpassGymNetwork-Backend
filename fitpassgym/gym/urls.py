from django.urls import include, path

app_name = "gym"

urlpatterns = [
    path("", include("fitpassgym.gym.identity.urls")),
    path("", include("fitpassgym.gym.locations.urls")),
    path("", include("fitpassgym.gym.scheduling.urls")),
    path("", include("fitpassgym.gym.commerce.urls")),
    path("", include("fitpassgym.gym.access.urls")),
    path("", include("fitpassgym.gym.content.urls")),
]
