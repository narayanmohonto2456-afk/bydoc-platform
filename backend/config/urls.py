from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "health/",
        include("apps.core.urls"),
    ),
    path(
    "api/v1/appointments/",
    include("apps.appointments.urls"),
),
    path(
    "api/v1/notifications/",
    include("apps.notifications.urls"),
),
    path(
    "api/v1/support/",
    include("apps.support.urls"),
),
    path(
    "api/v1/preferences/",
    include("apps.preferences.urls"),
),
]