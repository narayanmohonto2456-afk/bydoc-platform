from django.urls import path

from .views import PublicClinicDetailView, PublicClinicListView

app_name = "clinics"

urlpatterns = [
    path("", PublicClinicListView.as_view(), name="list"),
    path("<uuid:clinic_id>/", PublicClinicDetailView.as_view(), name="detail"),
]
