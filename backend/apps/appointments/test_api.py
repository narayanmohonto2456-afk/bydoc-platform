from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.clinics.models import Clinic
from apps.doctors.models import (
    DoctorClinicAffiliation,
    DoctorProfile,
    DoctorRegistration,
)
from apps.organizations.models import Organization

from .models import Appointment, AppointmentSlot


pytestmark = pytest.mark.django_db

User = get_user_model()


def create_user(username):
    return User.objects.create_user(
        username=username,
        password="test-password",
    )


def create_affiliation(
    organization_slug="api-organization",
    clinic_slug="api-clinic",
    doctor_username="api-doctor",
):
    organization = Organization.objects.create(
        name=f"Organization {organization_slug}",
        slug=organization_slug,
        status=Organization.Status.ACTIVE,
    )

    clinic = Clinic.objects.create(
        organization=organization,
        name=f"Clinic {clinic_slug}",
        slug=clinic_slug,
        status=Clinic.Status.ACTIVE,
        address_line_1="12 Health Road",
        locality="Salt Lake",
        district="Kolkata",
        state="West Bengal",
        postal_code="700091",
        timezone="Asia/Kolkata",
    )

    doctor_user = create_user(doctor_username)

    doctor = DoctorProfile.objects.create(
        user=doctor_user,
        display_name=f"Dr {doctor_username}",
        status=DoctorProfile.Status.ACTIVE,
    )
    DoctorRegistration.objects.create(
        doctor=doctor,
        council_name="Test Council",
        registration_number=doctor_username,
        registered_name=doctor.display_name,
        verification_status=DoctorRegistration.VerificationStatus.VERIFIED,
        verified_at=timezone.now(),
        verified_by=doctor_user,
    )

    affiliation = DoctorClinicAffiliation.objects.create(
        doctor=doctor,
        clinic=clinic,
        status=DoctorClinicAffiliation.Status.ACTIVE,
        joined_at=timezone.now(),
        accepts_online_bookings=True,
        consultation_fee="500.00",
        currency_code="INR",
        appointment_duration_minutes=15,
    )

    return affiliation


def create_future_slot(
    affiliation,
    hours_from_now=24,
    status_value=AppointmentSlot.Status.OPEN,
):
    starts_at = timezone.now() + timedelta(
        hours=hours_from_now
    )

    return AppointmentSlot.objects.create(
        affiliation=affiliation,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=15),
        status=status_value,
    )


def response_items(response):
    if isinstance(response.data, dict):
        return response.data.get("results", [])

    return response.data


def slot_local_date(slot):
    clinic_timezone = ZoneInfo(
        slot.affiliation.clinic.timezone
    )

    return slot.starts_at.astimezone(
        clinic_timezone
    ).date()


def test_public_provider_search_only_shows_verified_bookable_affiliations():
    visible = create_affiliation()
    hidden = create_affiliation(
        organization_slug="hidden-organization",
        clinic_slug="hidden-clinic",
        doctor_username="hidden-doctor",
    )
    DoctorRegistration.objects.filter(doctor=hidden.doctor).update(
        verification_status=DoctorRegistration.VerificationStatus.REVOKED,
        verified_at=None,
        verified_by=None,
    )

    response = APIClient().get(
        reverse("appointments:provider-list"), {"q": "api-doctor", "district": "Kolkata"}
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == str(visible.id)
    assert response.data["results"][0]["clinic_name"] == visible.clinic.name
    assert "registration_number" not in response.data["results"][0]


def test_revoked_registration_hides_slot_and_prevents_direct_hold():
    affiliation = create_affiliation()
    slot = create_future_slot(affiliation)
    DoctorRegistration.objects.filter(doctor=affiliation.doctor).update(
        verification_status=DoctorRegistration.VerificationStatus.REVOKED,
        verified_at=None,
        verified_by=None,
    )
    client = APIClient()
    listing = client.get(
        reverse("appointments:slot-list"),
        {"clinic_id": affiliation.clinic_id, "date": slot_local_date(slot).isoformat()},
    )
    assert listing.status_code == status.HTTP_200_OK
    assert response_items(listing) == []

    client.force_authenticate(user=create_user("revoked-slot-patient"))
    hold = client.post(reverse("appointments:slot-hold", kwargs={"slot_id": slot.id}), {}, format="json")
    assert hold.status_code == status.HTTP_409_CONFLICT
    slot.refresh_from_db()
    assert slot.status == AppointmentSlot.Status.OPEN


def test_public_slot_list_requires_clinic_and_date():
    client = APIClient()

    response = client.get(
        reverse("appointments:slot-list")
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "clinic_id" in response.data
    assert "date" in response.data


def test_public_slot_list_only_returns_open_selected_clinic_slots():
    selected_affiliation = create_affiliation()
    other_affiliation = create_affiliation(
        organization_slug="other-api-organization",
        clinic_slug="other-api-clinic",
        doctor_username="other-api-doctor",
    )

    open_slot = create_future_slot(
        selected_affiliation,
        hours_from_now=24,
    )
    create_future_slot(
        selected_affiliation,
        hours_from_now=25,
        status_value=AppointmentSlot.Status.BLOCKED,
    )
    create_future_slot(
        other_affiliation,
        hours_from_now=24,
    )

    client = APIClient()

    response = client.get(
        reverse("appointments:slot-list"),
        {
            "clinic_id": (
                selected_affiliation.clinic_id
            ),
            "date": slot_local_date(open_slot).isoformat(),
        },
    )

    assert response.status_code == status.HTTP_200_OK

    returned_ids = {
        str(item["id"])
        for item in response_items(response)
    }

    assert returned_ids == {str(open_slot.pk)}


def test_anonymous_user_cannot_hold_slot():
    affiliation = create_affiliation()
    slot = create_future_slot(affiliation)
    client = APIClient()

    response = client.post(
        reverse(
            "appointments:slot-hold",
            kwargs={"slot_id": slot.pk},
        ),
        {},
        format="json",
    )

    assert response.status_code in {
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    }

    slot.refresh_from_db()
    assert slot.status == AppointmentSlot.Status.OPEN


def test_authenticated_user_can_hold_book_list_and_cancel():
    affiliation = create_affiliation()
    slot = create_future_slot(affiliation)
    patient = create_user("api-patient")
    client = APIClient()
    client.force_authenticate(user=patient)

    hold_response = client.post(
        reverse(
            "appointments:slot-hold",
            kwargs={"slot_id": slot.pk},
        ),
        {},
        format="json",
    )

    assert hold_response.status_code == status.HTTP_200_OK

    booking_payload = {
        "hold_token": hold_response.data["hold_token"],
        "booking_request_id": (
            "9c9b2c50-314f-4c37-99eb-64dc20443351"
        ),
    }

    first_booking_response = client.post(
        reverse(
            "appointments:slot-book",
            kwargs={"slot_id": slot.pk},
        ),
        booking_payload,
        format="json",
    )

    repeated_booking_response = client.post(
        reverse(
            "appointments:slot-book",
            kwargs={"slot_id": slot.pk},
        ),
        booking_payload,
        format="json",
    )

    assert (
        first_booking_response.status_code
        == status.HTTP_200_OK
    )
    assert (
        repeated_booking_response.status_code
        == status.HTTP_200_OK
    )
    assert (
        repeated_booking_response.data["id"]
        == first_booking_response.data["id"]
    )
    assert Appointment.objects.count() == 1

    list_response = client.get(
        reverse("appointments:my-appointments")
    )

    assert list_response.status_code == status.HTTP_200_OK
    assert len(response_items(list_response)) == 1

    appointment_id = first_booking_response.data["id"]

    cancel_response = client.post(
        reverse(
            "appointments:appointment-cancel",
            kwargs={"appointment_id": appointment_id},
        ),
        {
            "cancellation_note": "Unable to attend",
        },
        format="json",
    )

    assert cancel_response.status_code == status.HTTP_200_OK
    assert (
        cancel_response.data["status"]
        == Appointment.Status.CANCELLED
    )

    slot.refresh_from_db()
    assert slot.status == AppointmentSlot.Status.OPEN



def test_confirmed_booking_keeps_declared_fee_after_affiliation_edit():
    affiliation = create_affiliation()
    slot = create_future_slot(affiliation)
    client = APIClient()
    client.force_authenticate(user=create_user("fee-snapshot-patient"))

    hold = client.post(
        reverse("appointments:slot-hold", kwargs={"slot_id": slot.pk}), {}, format="json"
    )
    booking = client.post(
        reverse("appointments:slot-book", kwargs={"slot_id": slot.pk}),
        {
            "hold_token": hold.data["hold_token"],
            "booking_request_id": "b4845ff8-9011-4c5f-a09f-c2cad0d83264",
        },
        format="json",
    )
    assert booking.status_code == 200
    assert booking.data["consultation_fee"] == "500.00"

    affiliation.consultation_fee = "700.00"
    affiliation.save(update_fields=["consultation_fee"])
    listed = client.get(reverse("appointments:my-appointments"))
    assert response_items(listed)[0]["consultation_fee"] == "500.00"



def test_unrelated_user_cannot_view_or_cancel_appointment():
    affiliation = create_affiliation()
    slot = create_future_slot(affiliation)
    patient = create_user("private-api-patient")
    unrelated_user = create_user("unrelated-api-user")

    patient_client = APIClient()
    patient_client.force_authenticate(user=patient)

    hold_response = patient_client.post(
        reverse(
            "appointments:slot-hold",
            kwargs={"slot_id": slot.pk},
        ),
        {},
        format="json",
    )

    booking_response = patient_client.post(
        reverse(
            "appointments:slot-book",
            kwargs={"slot_id": slot.pk},
        ),
        {
            "hold_token": hold_response.data["hold_token"],
            "booking_request_id": (
                "69af629b-b105-413a-a4cb-06dc90fc8697"
            ),
        },
        format="json",
    )

    unrelated_client = APIClient()
    unrelated_client.force_authenticate(
        user=unrelated_user
    )

    list_response = unrelated_client.get(
        reverse("appointments:my-appointments")
    )

    assert list_response.status_code == status.HTTP_200_OK
    assert response_items(list_response) == []

    cancel_response = unrelated_client.post(
        reverse(
            "appointments:appointment-cancel",
            kwargs={
                "appointment_id": (
                    booking_response.data["id"]
                )
            },
        ),
        {},
        format="json",
    )

    assert (
        cancel_response.status_code
        == status.HTTP_404_NOT_FOUND
    )

    appointment = Appointment.objects.get(
        pk=booking_response.data["id"]
    )
    assert appointment.status == Appointment.Status.CONFIRMED
