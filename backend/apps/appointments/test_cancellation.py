"""Cancellation policy at the API boundary, including atomic side effects."""

from datetime import timedelta
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.notifications.models import NotificationOutbox
from apps.organizations.models import OrganizationMembership
from apps.payments.models import PaymentIntent

from .models import Appointment, AppointmentSlot
from .services import book_held_slot, hold_slot
from .test_api import create_affiliation, create_future_slot, create_user


pytestmark = pytest.mark.django_db


@pytest.fixture
def booking():
    slot = create_future_slot(create_affiliation())
    patient = create_user("cancel-api-patient")
    held = hold_slot(slot.pk, patient)
    appointment = book_held_slot(
        slot_id=slot.pk, hold_token=held.hold_token, patient=patient, booked_by=patient,
    )
    client = APIClient()
    client.force_authenticate(user=patient)
    return client, appointment, slot, patient


@pytest.fixture
def paid_booking(booking):
    _, appointment, _, _ = booking
    payment = PaymentIntent.objects.create(
        appointment=appointment, amount_paise=50000, currency="INR",
        linked_account_id="acc_cancel_test", razorpay_order_id="order_cancel_test",
        razorpay_payment_id="pay_cancel_test", status=PaymentIntent.Status.CAPTURED,
    )
    return (*booking, payment)


def cancel_url(appointment):
    return reverse("appointments:appointment-cancel", kwargs={"appointment_id": appointment.pk})


def notices(appointment):
    return list(NotificationOutbox.objects.filter(appointment=appointment).order_by("pk").values())


@pytest.mark.parametrize("microseconds_before_start,expected_status", [(1, 200), (0, 409), (-1, 409)])
def test_patient_cancellation_cutoff_is_strict_and_preserves_payment_when_rejected(
    paid_booking, monkeypatch, microseconds_before_start, expected_status,
):
    client, appointment, slot, patient, payment = paid_booking
    before_notices = notices(appointment)
    now = slot.starts_at - timedelta(microseconds=microseconds_before_start)
    monkeypatch.setattr("apps.appointments.services.timezone.now", lambda: now)

    response = client.post(cancel_url(appointment), {"cancellation_note": "  Unable to attend  "}, format="json")

    assert response.status_code == expected_status, response.data
    appointment.refresh_from_db()
    slot.refresh_from_db()
    payment.refresh_from_db()
    assert payment.amount_paise == 50000
    if expected_status == 200:
        assert appointment.status == Appointment.Status.CANCELLED
        assert appointment.cancelled_at == now
        assert appointment.cancelled_by_id == patient.pk
        assert appointment.cancellation_note == "Unable to attend"
        assert slot.status == AppointmentSlot.Status.OPEN
        assert payment.status == PaymentIntent.Status.REFUND_DUE
    else:
        assert appointment.status == Appointment.Status.CONFIRMED
        assert appointment.cancelled_at is None
        assert appointment.cancelled_by_id is None
        assert appointment.cancellation_note == ""
        assert slot.status == AppointmentSlot.Status.BOOKED
        assert payment.status == PaymentIntent.Status.CAPTURED
        assert notices(appointment) == before_notices


@pytest.mark.parametrize("state", [Appointment.Status.CHECKED_IN, Appointment.Status.COMPLETED, Appointment.Status.NO_SHOW])
def test_non_confirmed_visit_cannot_be_cancelled_or_refunded(paid_booking, state):
    client, appointment, slot, _, payment = paid_booking
    appointment.status = state
    appointment.save(update_fields=["status"])
    before_notices = notices(appointment)

    response = client.post(cancel_url(appointment), {}, format="json")

    assert response.status_code == 409
    appointment.refresh_from_db()
    slot.refresh_from_db()
    payment.refresh_from_db()
    assert appointment.status == state
    assert appointment.cancelled_at is None
    assert slot.status == AppointmentSlot.Status.BOOKED
    assert payment.status == PaymentIntent.Status.CAPTURED
    assert notices(appointment) == before_notices


def test_cancel_retry_after_start_preserves_original_result_and_refund(paid_booking, monkeypatch):
    client, appointment, slot, _, payment = paid_booking
    first = client.post(cancel_url(appointment), {"cancellation_note": "Original reason"}, format="json")
    assert first.status_code == 200
    before_notices = notices(appointment)
    late = slot.starts_at + timedelta(minutes=1)
    monkeypatch.setattr("apps.appointments.services.timezone.now", lambda: late)

    repeated = client.post(cancel_url(appointment), {"cancellation_note": "Retry reason"}, format="json")

    assert repeated.status_code == 200
    assert repeated.data == first.data
    payment.refresh_from_db()
    assert payment.status == PaymentIntent.Status.REFUND_DUE
    assert PaymentIntent.objects.filter(appointment=appointment).count() == 1
    assert notices(appointment) == before_notices


@pytest.mark.parametrize("actor", ["anonymous", "another-patient", "inactive-staff"])
def test_unauthorized_cancellation_leaves_booking_payment_and_notices_unchanged(paid_booking, actor):
    _, appointment, slot, _, payment = paid_booking
    client = APIClient()
    if actor != "anonymous":
        user = create_user("unauthorized-canceller")
        client.force_authenticate(user=user)
        if actor == "inactive-staff":
            OrganizationMembership.objects.create(
                user=user, organization=slot.affiliation.clinic.organization,
                role=OrganizationMembership.Role.MANAGER, status=OrganizationMembership.Status.SUSPENDED,
            )
    before_notices = notices(appointment)

    response = client.post(cancel_url(appointment), {}, format="json")

    assert response.status_code == (401 if actor == "anonymous" else 404)
    appointment.refresh_from_db()
    slot.refresh_from_db()
    payment.refresh_from_db()
    assert appointment.status == Appointment.Status.CONFIRMED
    assert appointment.cancelled_at is None
    assert slot.status == AppointmentSlot.Status.BOOKED
    assert payment.status == PaymentIntent.Status.CAPTURED
    assert notices(appointment) == before_notices


def test_unknown_appointment_cancellation_returns_not_found(booking):
    client, _, _, _ = booking
    url = reverse("appointments:appointment-cancel", kwargs={"appointment_id": uuid4()})
    assert client.post(url, {}, format="json").status_code == 404


def test_authorized_clinic_manager_can_cancel_after_patient_cutoff(booking, monkeypatch):
    client, appointment, slot, _ = booking
    manager = create_user("cancellation-manager")
    OrganizationMembership.objects.create(
        user=manager, organization=slot.affiliation.clinic.organization,
        role=OrganizationMembership.Role.MANAGER, status=OrganizationMembership.Status.ACTIVE,
        joined_at=timezone.now(),
    )
    client.force_authenticate(user=manager)
    late = slot.starts_at + timedelta(minutes=1)
    monkeypatch.setattr("apps.appointments.services.timezone.now", lambda: late)

    response = client.post(cancel_url(appointment), {"cancellation_note": "Clinic cancellation"}, format="json")

    assert response.status_code == 200
    appointment.refresh_from_db()
    slot.refresh_from_db()
    assert appointment.cancelled_by_id == manager.pk
    assert slot.status == AppointmentSlot.Status.BLOCKED


def test_refund_state_failure_rolls_back_cancellation_and_notifications(paid_booking, monkeypatch):
    client, appointment, slot, _, payment = paid_booking
    before_notices = notices(appointment)

    def refund_unavailable(_appointment):
        raise RuntimeError("Refund state could not be persisted")

    monkeypatch.setattr("apps.payments.services.mark_cancelled_for_refund", refund_unavailable)
    with pytest.raises(RuntimeError, match="Refund state could not be persisted"):
        client.post(cancel_url(appointment), {}, format="json")

    appointment.refresh_from_db()
    slot.refresh_from_db()
    payment.refresh_from_db()
    assert appointment.status == Appointment.Status.CONFIRMED
    assert appointment.cancelled_at is None
    assert slot.status == AppointmentSlot.Status.BOOKED
    assert payment.status == PaymentIntent.Status.CAPTURED
    assert notices(appointment) == before_notices
