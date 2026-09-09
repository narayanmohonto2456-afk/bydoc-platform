from uuid import uuid4

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework.test import APIClient

from .models import Appointment, AppointmentSlot
from .test_api import create_affiliation, create_future_slot, create_user, response_items


pytestmark = pytest.mark.django_db


def book_via_api(client, slot):
    held = client.post(
        reverse("appointments:slot-hold", kwargs={"slot_id": slot.pk}),
        {}, format="json",
    )
    assert held.status_code == 200, held.data
    payload = {
        "hold_token": held.data["hold_token"],
        "booking_request_id": str(uuid4()),
    }
    booked = client.post(
        reverse("appointments:slot-book", kwargs={"slot_id": slot.pk}),
        payload, format="json",
    )
    assert booked.status_code == 200, booked.data
    return booked.data["id"], payload


def test_cancelled_slot_can_be_rebooked_with_history_and_safe_retries():
    slot = create_future_slot(create_affiliation())
    first_user = create_user("rebooking-first")
    second_user = create_user("rebooking-second")
    first_client = APIClient()
    second_client = APIClient()
    first_client.force_authenticate(user=first_user)
    second_client.force_authenticate(user=second_user)

    first_id, first_payload = book_via_api(first_client, slot)
    cancel_url = reverse(
        "appointments:appointment-cancel", kwargs={"appointment_id": first_id}
    )
    cancelled = first_client.post(
        cancel_url, {"cancellation_note": "Unable to attend"}, format="json"
    )
    assert cancelled.status_code == 200, cancelled.data
    first = Appointment.objects.get(pk=first_id)
    original_cancelled_at = first.cancelled_at
    slot.refresh_from_db()
    assert slot.status == AppointmentSlot.Status.OPEN

    second_id, second_payload = book_via_api(second_client, slot)
    assert str(second_id) != str(first_id)
    book_url = reverse("appointments:slot-book", kwargs={"slot_id": slot.pk})

    second_retry = second_client.post(book_url, second_payload, format="json")
    assert second_retry.status_code == 200, second_retry.data
    assert str(second_retry.data["id"]) == str(second_id)

    # An old booking retry must return its cancelled history record.
    first_retry = first_client.post(book_url, first_payload, format="json")
    assert first_retry.status_code == 200, first_retry.data
    assert str(first_retry.data["id"]) == str(first_id)
    assert first_retry.data["status"] == Appointment.Status.CANCELLED

    # Retrying the old cancellation must not reopen the new booking's slot.
    cancel_retry = first_client.post(cancel_url, {}, format="json")
    assert cancel_retry.status_code == 200, cancel_retry.data
    slot.refresh_from_db()
    first.refresh_from_db()
    second = Appointment.objects.get(pk=second_id)
    assert slot.status == AppointmentSlot.Status.BOOKED
    assert first.status == Appointment.Status.CANCELLED
    assert first.cancelled_at == original_cancelled_at
    assert first.cancelled_by_id == first_user.pk
    assert first.cancellation_note == "Unable to attend"
    assert second.status == Appointment.Status.CONFIRMED
    assert second.patient_id == second_user.pk
    assert slot.appointments.count() == 2
    assert slot.appointments.exclude(status=Appointment.Status.CANCELLED).count() == 1

    for client, expected_id in ((first_client, first_id), (second_client, second_id)):
        history = client.get(reverse("appointments:my-appointments"))
        assert history.status_code == 200, history.data
        assert {str(item["id"]) for item in response_items(history)} == {str(expected_id)}


@pytest.mark.parametrize("existing_status", [
    Appointment.Status.CONFIRMED,
    Appointment.Status.CHECKED_IN,
    Appointment.Status.COMPLETED,
    Appointment.Status.NO_SHOW,
])
def test_database_rejects_two_non_cancelled_bookings(existing_status):
    slot = create_future_slot(create_affiliation())
    user = create_user("constraint-rebooking-user")
    Appointment.objects.create(
        slot=slot, patient=user, booked_by=user, status=existing_status
    )
    with pytest.raises(IntegrityError) as error:
        with transaction.atomic():
            Appointment.objects.create(
                slot=slot, patient=user, booked_by=user,
                status=Appointment.Status.CONFIRMED,
            )
    assert error.value.__cause__.diag.constraint_name == "unique_non_cancelled_slot_appt"
