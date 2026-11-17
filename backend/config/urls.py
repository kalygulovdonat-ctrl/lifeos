from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

api_v1 = [
    path("", include("common.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.tasks.urls")),
    path("", include("apps.schedule.urls")),
    path("", include("apps.habits.urls")),
    path("", include("apps.goals.urls")),
    path("", include("apps.journal.urls")),
    path("", include("apps.time_tracking.urls")),
    path("", include("apps.analytics.urls")),
    path("", include("apps.reviews.urls")),
    path("", include("apps.wellness.urls")),
    path("", include("apps.notifications.urls")),
    path("", include("apps.ai_assistant.urls")),
    path("", include("apps.dashboard.urls")),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
]
if settings.DEBUG:
    api_v1.append(path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"))

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("api/v1/", include(api_v1)),
]

handler404 = "common.views.json_404"
handler500 = "common.views.json_500"
