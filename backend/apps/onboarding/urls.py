from django.urls import path

from .views import ClinicApplicationView, DoctorApplicationView

app_name = "onboarding"

urlpatterns = [
    path("doctor/", DoctorApplicationView.as_view(), name="doctor"),
    path("clinic/", ClinicApplicationView.as_view(), name="clinic"),
]
