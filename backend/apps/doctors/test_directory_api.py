from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.clinics.models import Clinic
from apps.organizations.models import Organization

from .models import (
    DoctorClinicAffiliation, DoctorProfile, DoctorRegistration, Language, Specialty,
)


pytestmark = pytest.mark.django_db


def make_clinic(slug, *, clinic_status=Clinic.Status.ACTIVE,
                org_status=Organization.Status.ACTIVE, district="Kolkata", wheelchair=False):
    organization = Organization.objects.create(name=slug, slug=slug, status=org_status)
    return Clinic.objects.create(
        organization=organization, name=slug.title(), slug=slug,
        status=clinic_status, address_line_1="Main Road", locality="Salt Lake",
        district=district, state="West Bengal", postal_code="700001",
        wheelchair_accessible=wheelchair,
    )


def make_doctor(slug, clinic, *, verified=True, doctor_status=DoctorProfile.Status.ACTIVE,
                affiliation_status=DoctorClinicAffiliation.Status.ACTIVE,
                valid_until=None, online=True):
    user = get_user_model().objects.create_user(username=slug, password="test-password")
    doctor = DoctorProfile.objects.create(user=user, display_name=f"Dr {slug}", status=doctor_status)
    registrar = get_user_model().objects.create_user(username=f"reviewer-{slug}", password="test-password")
    DoctorRegistration.objects.create(
        doctor=doctor, council_name="Council", registration_number=slug,
        registered_name=doctor.display_name,
        verification_status=(DoctorRegistration.VerificationStatus.VERIFIED if verified
                             else DoctorRegistration.VerificationStatus.PENDING),
        verified_at=timezone.now() if verified else None,
        verified_by=registrar if verified else None,
        valid_until=valid_until,
    )
    DoctorClinicAffiliation.objects.create(
        doctor=doctor, clinic=clinic, status=affiliation_status,
        joined_at=timezone.now() if affiliation_status == DoctorClinicAffiliation.Status.ACTIVE else None,
        accepts_online_bookings=online, consultation_fee="500.00",
    )
    return doctor


def results(response):
    assert response.status_code == 200, response.data
    return response.data["results"]


def test_clinic_directory_only_exposes_active_clinics_and_validates_filters():
    clinic = make_clinic("central", wheelchair=True)
    make_clinic("closed", clinic_status=Clinic.Status.CLOSED)
    make_clinic("suspended", org_status=Organization.Status.SUSPENDED)
    client = APIClient()
    response = client.get(reverse("clinics:list"), {"q": "cent", "wheelchair_accessible": "true"})
    assert [item["id"] for item in results(response)] == [str(clinic.pk)]
    assert client.get(reverse("clinics:detail", kwargs={"clinic_id": clinic.pk})).status_code == 200
    assert client.get(reverse("clinics:list"), {"wheelchair_accessible": "maybe"}).status_code == 400
    assert client.get(reverse("clinics:list"), {"q": "x" * 101}).status_code == 400


def test_closed_clinic_cannot_be_retrieved():
    clinic = make_clinic("inactive", clinic_status=Clinic.Status.SUSPENDED)
    assert APIClient().get(reverse("clinics:detail", kwargs={"clinic_id": clinic.pk})).status_code == 404


def test_doctor_directory_requires_current_verification_and_eligible_clinic():
    active = make_clinic("active")
    closed = make_clinic("closed", clinic_status=Clinic.Status.CLOSED)
    hidden_org = make_clinic("suspended", org_status=Organization.Status.SUSPENDED)
    visible = make_doctor("visible", active)
    unverified = make_doctor("unverified", active, verified=False)
    expired = make_doctor("expired", active, valid_until=timezone.localdate() - timedelta(days=1))
    other = make_doctor("other", closed)
    make_doctor("hidden-org", hidden_org)
    make_doctor("inactive", active, doctor_status=DoctorProfile.Status.INACTIVE)
    make_doctor("ended", active, affiliation_status=DoctorClinicAffiliation.Status.ENDED)

    client = APIClient()
    assert [item["id"] for item in results(client.get(reverse("doctors:list")))] == [str(visible.pk)]
    for doctor in (unverified, expired, other):
        assert client.get(reverse("doctors:detail", kwargs={"doctor_id": doctor.pk})).status_code == 404
    detail = client.get(reverse("doctors:detail", kwargs={"doctor_id": visible.pk}))
    assert detail.status_code == 200
    assert detail.data["clinics"][0]["clinic"]["id"] == str(active.pk)
    assert "user" not in detail.data and "registrations" not in detail.data


def test_doctor_search_filters_refer_to_same_public_affiliation():
    kolkata = make_clinic("kolkata", district="Kolkata")
    delhi = make_clinic("delhi", district="Delhi")
    doctor = make_doctor("dual-clinic", kolkata, online=False)
    DoctorClinicAffiliation.objects.create(
        doctor=doctor, clinic=delhi, status=DoctorClinicAffiliation.Status.ACTIVE,
        joined_at=timezone.now(), accepts_online_bookings=True,
    )
    client = APIClient()
    url = reverse("doctors:list")
    assert results(client.get(url, {"district": "Kolkata", "online_booking": "true"})) == []
    assert len(results(client.get(url, {"district": "Kolkata", "online_booking": "false"}))) == 1
    assert results(client.get(url, {"clinic_id": kolkata.pk, "online_booking": "true"})) == []
    assert client.get(url, {"clinic_id": "not-a-uuid"}).status_code == 400


def test_specialty_and_language_search_does_not_duplicate_doctors():
    clinic = make_clinic("specialty-clinic")
    doctor = make_doctor("specialist", clinic)
    specialty = Specialty.objects.create(name="Cardiology", slug="cardiology")
    language = Language.objects.create(code="bn", name="Bengali")
    doctor.primary_specialty = specialty
    doctor.save(update_fields=["primary_specialty"])
    doctor.specialties.add(specialty)
    doctor.languages.add(language)
    response = APIClient().get(reverse("doctors:list"), {
        "specialty": "cardiology", "language": "BN", "page_size": 1,
    })
    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == str(doctor.pk)


def test_doctor_detail_only_contains_eligible_clinics():
    active = make_clinic("eligible")
    closed = make_clinic("ineligible", clinic_status=Clinic.Status.CLOSED)
    doctor = make_doctor("split", active)
    DoctorClinicAffiliation.objects.create(
        doctor=doctor, clinic=closed, status=DoctorClinicAffiliation.Status.ACTIVE,
        joined_at=timezone.now(), accepts_online_bookings=True,
    )
    client = APIClient()
    response = client.get(reverse("doctors:detail", kwargs={"doctor_id": doctor.pk}))
    assert response.status_code == 200
    assert [item["clinic"]["id"] for item in response.data["clinics"]] == [str(active.pk)]
    assert results(client.get(reverse("doctors:list"), {"clinic_id": closed.pk})) == []
