from datetime import timedelta
from uuid import uuid4

import pytest
from django.db import transaction
from django.utils import timezone

from apps.appointments.models import Appointment, AppointmentSlot
from apps.appointments.services import book_held_slot, cancel_appointment

from .models import NotificationDeliveryAttempt, NotificationOutbox
from .tasks import deliver_notification, dispatch_due_notifications
from .test_services import create_confirmed_appointment


pytestmark = pytest.mark.django_db


def notices(appointment):
    return NotificationOutbox.objects.filter(appointment=appointment)


def test_booking_persists_outbox_before_outer_commit_without_broker(
    monkeypatch, django_capture_on_commit_callbacks,
):
    def broker_unavailable(*args, **kwargs):
        raise RuntimeError("Broker must not be contacted during booking")

    monkeypatch.setattr("celery.app.task.Task.apply_async", broker_unavailable)
    with django_capture_on_commit_callbacks(execute=True):
        with transaction.atomic():
            appointment = create_confirmed_appointment()
            assert set(notices(appointment).values_list("category", flat=True)) == {
                NotificationOutbox.Category.APPOINTMENT_CONFIRMED,
                NotificationOutbox.Category.APPOINTMENT_REMINDER,
            }
            assert not notices(appointment).exclude(
                status=NotificationOutbox.Status.PENDING,
            ).exists()
    assert notices(appointment).count() == 2
    assert not NotificationDeliveryAttempt.objects.exists()


def test_booking_outer_rollback_removes_appointment_and_outbox():
    with pytest.raises(RuntimeError, match="Abort outer transaction"):
        with transaction.atomic():
            appointment = create_confirmed_appointment()
            assert notices(appointment).count() == 2
            raise RuntimeError("Abort outer transaction")
    assert not Appointment.objects.filter(pk=appointment.pk).exists()
    assert not notices(appointment).exists()


def test_partial_outbox_failure_rolls_back_booking_and_preserves_hold(monkeypatch):
    def fail_after_confirmation(appointment, **kwargs):
        assert notices(appointment).filter(
            category=NotificationOutbox.Category.APPOINTMENT_CONFIRMED,
        ).exists()
        raise RuntimeError("Simulated outbox write failure")

    with monkeypatch.context() as patch:
        patch.setattr(
            "apps.notifications.services.enqueue_appointment_reminder",
            fail_after_confirmation,
        )
        with pytest.raises(RuntimeError, match="Simulated outbox write failure"):
            create_confirmed_appointment()

    assert not Appointment.objects.exists()
    assert not NotificationOutbox.objects.exists()
    slot = AppointmentSlot.objects.get()
    assert slot.status == AppointmentSlot.Status.HELD
    assert slot.hold_token is not None
    assert slot.held_by_id is not None
    assert slot.hold_expires_at > timezone.now()

    appointment = book_held_slot(
        slot_id=slot.pk, hold_token=slot.hold_token,
        patient=slot.held_by, booked_by=slot.held_by,
        booking_request_id=uuid4(),
    )
    assert notices(appointment).count() == 2


def test_idempotent_booking_retry_preserves_outbox_even_after_start_time():
    appointment = create_confirmed_appointment()
    ids = set(notices(appointment).values_list("pk", flat=True))
    starts_at = timezone.now() - timedelta(hours=1)
    AppointmentSlot.objects.filter(pk=appointment.slot_id).update(
        starts_at=starts_at, ends_at=starts_at + timedelta(minutes=15),
    )
    repeated = book_held_slot(
        slot_id=appointment.slot_id, hold_token=uuid4(),
        patient=appointment.patient, booked_by=appointment.booked_by,
        booking_request_id=appointment.booking_request_id,
    )
    assert repeated.pk == appointment.pk
    assert set(notices(appointment).values_list("pk", flat=True)) == ids


def test_cancellation_and_retry_persist_notice_and_cancel_reminder():
    appointment = create_confirmed_appointment()
    with transaction.atomic():
        cancelled = cancel_appointment(
            appointment_id=appointment.pk, cancelled_by=appointment.patient,
            cancellation_note="Unable to attend",
        )
        reminder = notices(appointment).get(
            category=NotificationOutbox.Category.APPOINTMENT_REMINDER,
        )
        notice = notices(appointment).get(
            category=NotificationOutbox.Category.APPOINTMENT_CANCELLED,
        )
        assert reminder.status == NotificationOutbox.Status.CANCELLED
        assert notice.status == NotificationOutbox.Status.PENDING
        assert cancelled.status == Appointment.Status.CANCELLED

    cancel_appointment(
        appointment_id=appointment.pk, cancelled_by=appointment.patient,
    )
    assert notices(appointment).count() == 3
    assert notices(appointment).get(
        category=NotificationOutbox.Category.APPOINTMENT_CANCELLED,
    ).pk == notice.pk


def test_cancellation_outer_rollback_restores_booking_and_reminder():
    appointment = create_confirmed_appointment()
    with pytest.raises(RuntimeError, match="Abort cancellation"):
        with transaction.atomic():
            cancel_appointment(
                appointment_id=appointment.pk, cancelled_by=appointment.patient,
            )
            assert notices(appointment).filter(
                category=NotificationOutbox.Category.APPOINTMENT_CANCELLED,
            ).exists()
            raise RuntimeError("Abort cancellation")
    assert_cancellation_rolled_back(appointment)


def assert_cancellation_rolled_back(appointment):
    appointment.refresh_from_db()
    slot = AppointmentSlot.objects.get(pk=appointment.slot_id)
    assert appointment.status == Appointment.Status.CONFIRMED
    assert appointment.cancelled_at is None
    assert appointment.cancelled_by_id is None
    assert appointment.cancellation_note == ""
    assert slot.status == AppointmentSlot.Status.BOOKED
    assert notices(appointment).count() == 2
    assert notices(appointment).get(
        category=NotificationOutbox.Category.APPOINTMENT_REMINDER,
    ).status == NotificationOutbox.Status.PENDING


def test_cancellation_outbox_failure_restores_booking_and_reminder(monkeypatch):
    appointment = create_confirmed_appointment()

    def fail_notice(**kwargs):
        assert notices(appointment).get(
            category=NotificationOutbox.Category.APPOINTMENT_REMINDER,
        ).status == NotificationOutbox.Status.CANCELLED
        raise RuntimeError("Cancellation outbox unavailable")

    monkeypatch.setattr("apps.notifications.services.enqueue_notification", fail_notice)
    with pytest.raises(RuntimeError, match="Cancellation outbox unavailable"):
        cancel_appointment(
            appointment_id=appointment.pk, cancelled_by=appointment.patient,
        )
    assert_cancellation_rolled_back(appointment)


@pytest.mark.django_db(transaction=True)
def test_committed_outbox_survives_dispatch_failure_and_can_be_retried(monkeypatch):
    appointment = create_confirmed_appointment()
    confirmation = notices(appointment).get(
        category=NotificationOutbox.Category.APPOINTMENT_CONFIRMED,
    )
    def broker_unavailable(*args, **kwargs):
        raise RuntimeError("Broker unavailable")

    with monkeypatch.context() as patch:
        patch.setattr(deliver_notification, "delay", broker_unavailable)
        with pytest.raises(RuntimeError, match="Broker unavailable"):
            dispatch_due_notifications.run()

    appointment.refresh_from_db()
    confirmation.refresh_from_db()
    assert appointment.status == Appointment.Status.CONFIRMED
    assert confirmation.status == NotificationOutbox.Status.PENDING
    queued = []
    monkeypatch.setattr(deliver_notification, "delay", queued.append)
    assert dispatch_due_notifications.run() == {"queued": 1}
    assert queued == [str(confirmation.pk)]
