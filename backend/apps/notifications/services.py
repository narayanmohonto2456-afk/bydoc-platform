from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.appointments.models import Appointment

from .models import NotificationOutbox


DEFAULT_REMINDER_LEAD_TIME = timedelta(hours=24)


class NotificationSchedulingError(Exception):
    """Raised when a notification cannot be scheduled safely."""


def _deduplication_key(
    appointment,
    category,
    channel,
):
    return (
        f"appointment:{appointment.pk}:"
        f"{category}:{channel}"
    )


def _appointment_payload(appointment):
    """
    Return minimal non-clinical template data.

    Diagnosis, symptoms, prescriptions and medical records must
    never be added to this payload.
    """
    slot = appointment.slot
    affiliation = slot.affiliation

    return {
        "booking_reference": str(
            appointment.booking_reference
        ),
        "appointment_starts_at": (
            slot.starts_at.isoformat()
        ),
        "appointment_ends_at": (
            slot.ends_at.isoformat()
        ),
        "doctor_name": (
            affiliation.doctor.display_name
        ),
        "clinic_name": affiliation.clinic.name,
    }


def enqueue_notification(
    *,
    appointment,
    category,
    template_key,
    scheduled_for,
    channel=NotificationOutbox.Channel.IN_APP,
    locale="en",
):
    """
    Create an outbox item idempotently.

    Repeating the same operation returns the existing notification
    instead of creating a duplicate.
    """
    if appointment.patient_id is None:
        raise NotificationSchedulingError(
            "The appointment does not have a patient."
        )

    deduplication_key = _deduplication_key(
        appointment,
        category,
        channel,
    )

    notification, _created = (
        NotificationOutbox.objects.get_or_create(
            deduplication_key=deduplication_key,
            defaults={
                "recipient": appointment.patient,
                "appointment": appointment,
                "channel": channel,
                "category": category,
                "template_key": template_key,
                "locale": locale,
                "payload": _appointment_payload(
                    appointment
                ),
                "scheduled_for": scheduled_for,
            },
        )
    )

    return notification


def enqueue_appointment_confirmation(
    appointment,
    *,
    channel=NotificationOutbox.Channel.IN_APP,
    locale="en",
):
    if appointment.status != Appointment.Status.CONFIRMED:
        raise NotificationSchedulingError(
            "Only confirmed appointments can receive "
            "confirmation notifications."
        )

    return enqueue_notification(
        appointment=appointment,
        category=(
            NotificationOutbox.Category.APPOINTMENT_CONFIRMED
        ),
        template_key="appointment.confirmed",
        scheduled_for=timezone.now(),
        channel=channel,
        locale=locale,
    )


def enqueue_appointment_reminder(
    appointment,
    *,
    channel=NotificationOutbox.Channel.IN_APP,
    locale="en",
    lead_time=DEFAULT_REMINDER_LEAD_TIME,
):
    if appointment.status != Appointment.Status.CONFIRMED:
        raise NotificationSchedulingError(
            "Only confirmed appointments can receive reminders."
        )

    if lead_time <= timedelta(0):
        raise NotificationSchedulingError(
            "Reminder lead time must be greater than zero."
        )

    now = timezone.now()

    if appointment.slot.starts_at <= now:
        raise NotificationSchedulingError(
            "Reminders cannot be scheduled for "
            "past appointments."
        )

    scheduled_for = max(
        now,
        appointment.slot.starts_at - lead_time,
    )

    return enqueue_notification(
        appointment=appointment,
        category=(
            NotificationOutbox.Category.APPOINTMENT_REMINDER
        ),
        template_key="appointment.reminder",
        scheduled_for=scheduled_for,
        channel=channel,
        locale=locale,
    )


@transaction.atomic
def enqueue_appointment_created_notifications(
    appointment,
    *,
    channel=NotificationOutbox.Channel.IN_APP,
    locale="en",
):
    """
    Schedule confirmation and reminder outbox items atomically.
    """
    confirmation = enqueue_appointment_confirmation(
        appointment,
        channel=channel,
        locale=locale,
    )

    reminder = enqueue_appointment_reminder(
        appointment,
        channel=channel,
        locale=locale,
    )

    return confirmation, reminder


@transaction.atomic
def enqueue_appointment_cancellation(
    appointment,
    *,
    channel=NotificationOutbox.Channel.IN_APP,
    locale="en",
):
    if appointment.status != Appointment.Status.CANCELLED:
        raise NotificationSchedulingError(
            "Only cancelled appointments can receive "
            "cancellation notifications."
        )

    (
        NotificationOutbox.objects
        .filter(
            appointment=appointment,
            category=(
                NotificationOutbox.Category.APPOINTMENT_REMINDER
            ),
            status__in=[
                NotificationOutbox.Status.PENDING,
                NotificationOutbox.Status.FAILED,
            ],
        )
        .update(
            status=NotificationOutbox.Status.CANCELLED,
            next_attempt_at=None,
        )
    )

    return enqueue_notification(
        appointment=appointment,
        category=(
            NotificationOutbox.Category.APPOINTMENT_CANCELLED
        ),
        template_key="appointment.cancelled",
        scheduled_for=timezone.now(),
        channel=channel,
        locale=locale,
    )



