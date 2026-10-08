from django.urls import path

from .views import (
    BookSlotView,
    CancelAppointmentView,
    HoldSlotView,
    MyAppointmentListView,
    PublicSlotListView,
    PublicProviderListView,
)


app_name = "appointments"


urlpatterns = [
    path("providers/", PublicProviderListView.as_view(), name="provider-list"),
    path(
        "slots/",
        PublicSlotListView.as_view(),
        name="slot-list",
    ),
    path(
        "slots/<uuid:slot_id>/hold/",
        HoldSlotView.as_view(),
        name="slot-hold",
    ),
    path(
        "slots/<uuid:slot_id>/book/",
        BookSlotView.as_view(),
        name="slot-book",
    ),
    path(
        "mine/",
        MyAppointmentListView.as_view(),
        name="my-appointments",
    ),
    path(
        "<uuid:appointment_id>/cancel/",
        CancelAppointmentView.as_view(),
        name="appointment-cancel",
    ),
]
