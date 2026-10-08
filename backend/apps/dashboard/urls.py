from django.urls import path

from .views import (
    AdminDashboardView,
    ClinicDashboardView,
    DoctorDashboardView,
    PatientDashboardView,
    RolesView,
)

app_name = "dashboard"

urlpatterns = [
    path("roles/", RolesView.as_view(), name="roles"),
    path("patient/", PatientDashboardView.as_view(), name="patient"),
    path("doctor/", DoctorDashboardView.as_view(), name="doctor"),
    path("clinic/", ClinicDashboardView.as_view(), name="clinic"),
    path("admin/", AdminDashboardView.as_view(), name="admin"),
]
