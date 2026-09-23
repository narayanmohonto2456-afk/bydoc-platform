from django.urls import path

from .views import PublicDoctorDetailView, PublicDoctorListView

app_name = "doctors"

urlpatterns = [
    path("", PublicDoctorListView.as_view(), name="list"),
    path("<uuid:doctor_id>/", PublicDoctorDetailView.as_view(), name="detail"),
]
