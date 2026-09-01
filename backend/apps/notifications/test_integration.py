from uuid import uuid4

import pytest

from apps.appointments.models import Appointment
from apps.appointments.services import (
    book_held_slot,
    cancel_appointment,
)

from .models import NotificationOutbox
from .test_services import create_confirmed_appointment


pytestmark = pytest.mark.django_db


def test_booking_commit_creates_confirmation_and_reminder(
    django_capture_on_commit_callbacks,
):
    with django_capture_on_commit_callbacks(
        execute=True
    ) as callbacks:
        appointment = create_confirmed_appointment(
            patient_username="booking-hook-patient"
        )

    assert len(callbacks) == 1

    notifications = (
        NotificationOutbox.objects
        .filter(appointment=appointment)
        .order_by("category")
    )

    assert notifications.count() == 2

    categories = set(
        notifications.values_list(
            "category",
            flat=True,
        )
    )

    assert categories == {
        NotificationOutbox.Category.APPOINTMENT_CONFIRMED,
        NotificationOutbox.Category.APPOINTMENT_REMINDER,
    }


def test_idempotent_booking_retry_does_not_duplicate_notifications(
    django_capture_on_commit_callbacks,
):
    with django_capture_on_commit_callbacks(
        execute=True
    ):
        appointment = create_confirmed_appointment(
            patient_username="retry-hook-patient"
        )

    assert (
        NotificationOutbox.objects
        .filter(appointment=appointment)
        .count()
        == 2
    )

    with django_capture_on_commit_callbacks(
        execute=True
    ) as callbacks:
        repeated_appointment = book_held_slot(
            slot_id=appointment.slot_id,
            hold_token=uuid4(),
            patient=appointment.patient,
            booked_by=appointment.booked_by,
            booking_request_id=(
                appointment.booking_request_id
            ),
        )

    assert len(callbacks) == 1
    assert repeated_appointment.pk == appointment.pk

    assert (
        NotificationOutbox.objects
        .filter(appointment=appointment)
        .count()
        == 2
    )


def test_cancellation_commit_cancels_reminder_and_creates_notice(
    django_capture_on_commit_callbacks,
):
    with django_capture_on_commit_callbacks(
        execute=True
    ):
        appointment = create_confirmed_appointment(
            patient_username="cancellation-hook-patient"
        )

    with django_capture_on_commit_callbacks(
        execute=True
    ) as callbacks:
        cancelled_appointment = cancel_appointment(
            appointment_id=appointment.pk,
            cancelled_by=appointment.patient,
            cancellation_note="Unable to attend",
        )

    assert len(callbacks) == 1
    assert (
        cancelled_appointment.status
        == Appointment.Status.CANCELLED
    )

    reminder = NotificationOutbox.objects.get(
        appointment=appointment,
        category=(
            NotificationOutbox.Category.APPOINTMENT_REMINDER
        ),
    )

    cancellation = NotificationOutbox.objects.get(
        appointment=appointment,
        category=(
            NotificationOutbox.Category.APPOINTMENT_CANCELLED
        ),
    )

    assert (
        reminder.status
        == NotificationOutbox.Status.CANCELLED
    )
    assert (
        cancellation.status
        == NotificationOutbox.Status.PENDING
    )


def test_notification_failure_does_not_undo_booking(
    django_capture_on_commit_callbacks,
    monkeypatch,
):
    def raise_scheduling_error(_appointment):
        raise RuntimeError("Simulated notification failure")

    monkeypatch.setattr(
        "apps.notifications.hooks."
        "enqueue_appointment_created_notifications",
        raise_scheduling_error,
    )

    with django_capture_on_commit_callbacks(
        execute=True
    ):
        appointment = create_confirmed_appointment(
            patient_username="failed-hook-patient"
        )

    assert Appointment.objects.filter(
        pk=appointment.pk,
        status=Appointment.Status.CONFIRMED,
    ).exists()

    assert not NotificationOutbox.objects.filter(
        appointment=appointment
    ).exists()