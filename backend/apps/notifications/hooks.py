import logging

from apps.appointments.models import Appointment

from .services import (
    enqueue_appointment_cancellation,
    enqueue_appointment_created_notifications,
)


logger = logging.getLogger(__name__)


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


def schedule_created_notifications(appointment_id):
    """
    Schedule confirmation and reminder after booking commits.

    Exceptions are logged because notification failure must never
    make a successfully committed booking appear unsuccessful.
    """
    try:
        appointment = _get_appointment(appointment_id)

        if appointment.status != Appointment.Status.CONFIRMED:
            return

        enqueue_appointment_created_notifications(
            appointment
        )
    except Exception:
        logger.exception(
            "Unable to schedule notifications for appointment %s.",
            appointment_id,
        )


def schedule_cancellation_notification(appointment_id):
    """
    Schedule cancellation notification after cancellation commits.
    """
    try:
        appointment = _get_appointment(appointment_id)

        if appointment.status != Appointment.Status.CANCELLED:
            return

        enqueue_appointment_cancellation(appointment)
    except Exception:
        logger.exception(
            "Unable to schedule cancellation notification "
            "for appointment %s.",
            appointment_id,
        )