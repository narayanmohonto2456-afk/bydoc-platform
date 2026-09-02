from django.urls import path

from .views import (
    InboxListView,
    MarkAllNotificationsReadView,
    MarkNotificationReadView,
    UnreadCountView,
)


app_name = "notifications"


urlpatterns = [
    path(
        "inbox/",
        InboxListView.as_view(),
        name="inbox-list",
    ),
    path(
        "inbox/unread-count/",
        UnreadCountView.as_view(),
        name="unread-count",
    ),
    path(
        "inbox/mark-all-read/",
        MarkAllNotificationsReadView.as_view(),
        name="mark-all-read",
    ),
    path(
        "inbox/<uuid:notification_id>/read/",
        MarkNotificationReadView.as_view(),
        name="mark-read",
    ),
]