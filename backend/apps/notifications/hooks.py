"""Persist notification requests; never perform delivery here."""

from django.db import transaction

from apps.appointments.models import Appointment

from .services import (
    enqueue_appointment_cancellation,
    enqueue_appointment_created_notifications,
)


def _get_appointment(appointment_id):
    return (
        Appointment.objects
        .select_related(
            "patient",
            "slot",
            "slot__affiliation",
            "slot__affiliation__doctor",
            "slot__affiliation__clinic",
        )
        .get(pk=appointment_id)
    )


@transaction.atomic
def schedule_created_notifications(appointment_id):
    """Join the booking transaction and let persistence errors propagate.

    The periodic dispatcher delivers committed outbox rows through Celery.
    Call this directly inside the booking transaction, not in on_commit.
    """
    appointment = _get_appointment(appointment_id)
    if appointment.status != Appointment.Status.CONFIRMED:
        return
    return enqueue_appointment_created_notifications(appointment)


@transaction.atomic
def schedule_cancellation_notification(appointment_id):
    """Cancel pending reminders and record the notice in the caller's transaction."""
    appointment = _get_appointment(appointment_id)
    if appointment.status != Appointment.Status.CANCELLED:
        return
    return enqueue_appointment_cancellation(appointment)
