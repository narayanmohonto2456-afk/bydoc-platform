import uuid
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.db.models import Q

from apps.clinics.models import Clinic
from apps.doctors.models import DoctorClinicAffiliation
from apps.organizations.models import (
    Organization,
    OrganizationMembership,
)

from .models import (
    Appointment,
    AppointmentSlot,
    AvailabilityRule,
    ScheduleException,
)
from django.utils.translation import gettext as _

def _persist_created_notifications(
    appointment_id,
):
    from apps.notifications.hooks import (
        schedule_created_notifications,
    )

    schedule_created_notifications(appointment_id)


def _persist_cancellation_notification(
    appointment_id,
):
    from apps.notifications.hooks import (
        schedule_cancellation_notification,
    )

    schedule_cancellation_notification(appointment_id)


class AppointmentBookingError(Exception):
    """Base exception for safe appointment-booking failures."""


class SlotUnavailableError(AppointmentBookingError):
    """The requested slot cannot currently be held or booked."""


class InvalidSlotHoldError(AppointmentBookingError):
    """The supplied slot hold is missing, invalid or expired."""


def _validate_authenticated_user(user, label):
    if not getattr(user, "is_authenticated", False):
        messages = {
            "user": _("An authenticated user is required."),
            "patient": _("An authenticated patient is required."),
            "booking user": _(
                "An authenticated booking user is required."
            ),
            "cancelling user": _(
                "An authenticated cancelling user is required."
            ),
        }

        raise AppointmentBookingError(
            messages.get(
                label,
                _("An authenticated user is required."),
            )
        )


def _validate_slot_eligibility(slot):
    affiliation = slot.affiliation
    clinic = affiliation.clinic
    organization = clinic.organization

    if (
        affiliation.status
        != DoctorClinicAffiliation.Status.ACTIVE
    ):
        raise SlotUnavailableError(
            _("The doctor is not active at this clinic.")
        )

    if not affiliation.accepts_online_bookings:
        raise SlotUnavailableError(
            _("Online booking is not enabled for this doctor.")
        )

    if clinic.status != Clinic.Status.ACTIVE:
        raise SlotUnavailableError(
            _("The clinic is not currently active.")
        )

    if organization.status != Organization.Status.ACTIVE:
        raise SlotUnavailableError(
            _("The organization is not currently active.")
        )

    if slot.starts_at <= timezone.now():
        raise SlotUnavailableError(
            _("Past appointment slots cannot be booked.")
        )


@transaction.atomic
def hold_slot(slot_id, held_by):
    """
    Lock and temporarily hold a slot.

    PostgreSQL SELECT FOR UPDATE ensures two requests cannot
    successfully hold the same slot simultaneously.
    """
    _validate_authenticated_user(held_by, "user")

    slot = (
        AppointmentSlot.objects
        .select_for_update()
        .select_related(
            "affiliation",
            "affiliation__clinic",
            "affiliation__clinic__organization",
        )
        .get(pk=slot_id)
    )

    _validate_slot_eligibility(slot)

    now = timezone.now()

    if slot.status in {
        AppointmentSlot.Status.BOOKED,
        AppointmentSlot.Status.BLOCKED,
    }:
        raise SlotUnavailableError(
            _("This appointment slot is unavailable.")
        )

    if (
        slot.status == AppointmentSlot.Status.HELD
        and slot.hold_expires_at
        and slot.hold_expires_at > now
        and slot.held_by_id != held_by.pk
    ):
        raise SlotUnavailableError(
            _("This slot is temporarily held by another user.")
        )

    hold_minutes = getattr(
        settings,
        "APPOINTMENT_HOLD_MINUTES",
        5,
    )

    slot.status = AppointmentSlot.Status.HELD
    slot.held_by = held_by
    slot.hold_token = uuid.uuid4()
    slot.hold_expires_at = now + timedelta(
        minutes=hold_minutes
    )
    slot.save(
        update_fields=[
            "status",
            "held_by",
            "hold_token",
            "hold_expires_at",
            "updated_at",
        ]
    )

    return slot


@transaction.atomic
def book_held_slot(
    slot_id,
    hold_token,
    patient,
    booked_by,
    booking_request_id=None,
):
    """
    Convert a valid temporary slot hold into one appointment.

    PostgreSQL locks the slot row until the transaction finishes.
    The booking_request_id makes repeated confirmation requests
    idempotent.

    Notification outbox records are scheduled only after the
    booking transaction commits successfully.
    """
    _validate_authenticated_user(patient, "patient")
    _validate_authenticated_user(
        booked_by,
        "booking user",
    )

    if booking_request_id is None:
        booking_request_id = uuid.uuid4()
    elif not isinstance(booking_request_id, uuid.UUID):
        try:
            booking_request_id = uuid.UUID(
                str(booking_request_id)
            )
        except (
            TypeError,
            ValueError,
            AttributeError,
        ) as error:
            raise AppointmentBookingError(
                _("The booking request identifier is invalid.")
            ) from error

    slot = (
        AppointmentSlot.objects
        .select_for_update()
        .select_related(
            "affiliation",
            "affiliation__clinic",
            "affiliation__clinic__organization",
        )
        .get(pk=slot_id)
    )

    # Check idempotency after locking the slot. A repeated request
    # waits for the first transaction and then receives the same
    # appointment instead of creating a duplicate.
    existing_appointment = (
        Appointment.objects
        .filter(
            booking_request_id=booking_request_id,
        )
        .first()
    )

    if existing_appointment is not None:
        same_booking_request = (
            existing_appointment.slot_id == slot.pk
            and existing_appointment.patient_id
            == patient.pk
            and existing_appointment.booked_by_id
            == booked_by.pk
        )

        if same_booking_request:
            # This booking and its outbox rows were committed together.
            # Return history without rescheduling reminders for a past booking.
            return existing_appointment

        raise AppointmentBookingError(
            _(
                "This booking request identifier "
                "has already been used."
            )
        )

    _validate_slot_eligibility(slot)

    now = timezone.now()

    if slot.status != AppointmentSlot.Status.HELD:
        raise InvalidSlotHoldError(
            _("This slot does not have an active hold.")
        )

    if slot.held_by_id != booked_by.pk:
        raise InvalidSlotHoldError(
            _("This slot is held by another user.")
        )

    if slot.hold_token != hold_token:
        raise InvalidSlotHoldError(
            _("The slot hold token is invalid.")
        )

    if (
        slot.hold_expires_at is None
        or slot.hold_expires_at <= now
    ):
        raise InvalidSlotHoldError(
            _("The slot hold has expired.")
        )

    appointment = Appointment.objects.create(
        slot=slot,
        patient=patient,
        booked_by=booked_by,
        booking_request_id=booking_request_id,
        status=Appointment.Status.CONFIRMED,
    )

    slot.status = AppointmentSlot.Status.BOOKED
    slot.held_by = None
    slot.hold_token = None
    slot.hold_expires_at = None
    slot.save(
        update_fields=[
            "status",
            "held_by",
            "hold_token",
            "hold_expires_at",
            "updated_at",
        ]
    )

    _persist_created_notifications(
        appointment.pk
    )

    return appointment




def release_expired_holds():
    """
    Release expired holds in one atomic database update.

    This can later be called periodically by Celery.
    """
    now = timezone.now()

    return AppointmentSlot.objects.filter(
        status=AppointmentSlot.Status.HELD,
        hold_expires_at__lte=now,
    ).update(
        status=AppointmentSlot.Status.OPEN,
        held_by=None,
        hold_token=None,
        hold_expires_at=None,
        updated_at=now,
    )

class ScheduleGenerationError(Exception):
    """A schedule cannot safely generate appointment slots."""

@transaction.atomic
def generate_slots_for_date(affiliation, target_date):
    """
    Generate slots for one doctor-clinic affiliation and local date.

    Existing slots are preserved. The database uniqueness constraint
    prevents duplicate slots when generation runs more than once.
    """
    if (
        affiliation.status
        != DoctorClinicAffiliation.Status.ACTIVE
    ):
        raise ScheduleGenerationError(
            _("Slots cannot be generated for an inactive affiliation.")
        )

    if not affiliation.accepts_online_bookings:
        raise ScheduleGenerationError(
            _("Online booking is not enabled for this affiliation.")
        )

    clinic = affiliation.clinic

    if clinic.status != Clinic.Status.ACTIVE:
        raise ScheduleGenerationError(
            _("Slots cannot be generated for an inactive clinic.")
        )

    if clinic.organization.status != Organization.Status.ACTIVE:
        raise ScheduleGenerationError(
            _("Slots cannot be generated for an inactive organization.")
        )

    try:
        clinic_timezone = ZoneInfo(clinic.timezone)
    except ZoneInfoNotFoundError as error:
        raise ScheduleGenerationError(
            _("The clinic timezone is invalid.")
        ) from error

    exceptions = list(
        ScheduleException.objects.filter(
            affiliation=affiliation,
            exception_date=target_date,
        )
    )

    if any(
        item.exception_type == ScheduleException.Type.CLOSED
        for item in exceptions
    ):
        return AppointmentSlot.objects.none()

    custom_windows = [
        (item.start_time, item.end_time)
        for item in exceptions
        if (
            item.exception_type
            == ScheduleException.Type.CUSTOM_HOURS
        )
    ]

    if custom_windows:
        availability_windows = custom_windows
    else:
        rules = AvailabilityRule.objects.filter(
            affiliation=affiliation,
            weekday=target_date.weekday(),
            valid_from__lte=target_date,
            is_active=True,
        ).filter(
            Q(valid_until__isnull=True)
            | Q(valid_until__gte=target_date)
        )

        availability_windows = [
            (rule.start_time, rule.end_time)
            for rule in rules
        ]

    unavailable_windows = [
        (item.start_time, item.end_time)
        for item in exceptions
        if (
            item.exception_type
            == ScheduleException.Type.UNAVAILABLE
        )
    ]

    duration = timedelta(
        minutes=affiliation.appointment_duration_minutes
    )
    now = timezone.now()
    candidate_slots = {}

    for window_start, window_end in availability_windows:
        starts_at = datetime.combine(
            target_date,
            window_start,
            tzinfo=clinic_timezone,
        )
        window_ends_at = datetime.combine(
            target_date,
            window_end,
            tzinfo=clinic_timezone,
        )

        while starts_at + duration <= window_ends_at:
            ends_at = starts_at + duration

            overlaps_unavailable_period = any(
                starts_at
                < datetime.combine(
                    target_date,
                    unavailable_end,
                    tzinfo=clinic_timezone,
                )
                and ends_at
                > datetime.combine(
                    target_date,
                    unavailable_start,
                    tzinfo=clinic_timezone,
                )
                for unavailable_start, unavailable_end
                in unavailable_windows
            )

            if (
                starts_at > now
                and not overlaps_unavailable_period
            ):
                candidate_slots[starts_at] = AppointmentSlot(
                    affiliation=affiliation,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    status=AppointmentSlot.Status.OPEN,
                )

            starts_at = ends_at

    AppointmentSlot.objects.bulk_create(
        candidate_slots.values(),
        ignore_conflicts=True,
    )

    local_day_start = datetime.combine(
        target_date,
        time.min,
        tzinfo=clinic_timezone,
    )
    local_next_day = local_day_start + timedelta(days=1)

    return AppointmentSlot.objects.filter(
        affiliation=affiliation,
        starts_at__gte=local_day_start,
        starts_at__lt=local_next_day,
    ).order_by("starts_at")


class AppointmentAuthorizationError(AppointmentBookingError):
    """The user cannot perform this appointment operation."""


class InvalidAppointmentStateError(AppointmentBookingError):
    """The appointment cannot transition from its current state."""


@transaction.atomic
def cancel_appointment(
    appointment_id,
    cancelled_by,
    cancellation_note="",
):
    """
    Cancel a confirmed appointment with row-level locking.

    Repeated cancellation requests are idempotent. Cancellation outbox
    rows and pending-reminder updates share this transaction.
    """
    _validate_authenticated_user(
        cancelled_by,
        "cancelling user",
    )

    appointment = (
        Appointment.objects
        .select_for_update()
        .select_related(
            "slot",
            "slot__affiliation",
            "slot__affiliation__clinic",
            "slot__affiliation__clinic__organization",
            "patient",
            "booked_by",
        )
        .get(pk=appointment_id)
    )

    organization = (
        appointment
        .slot
        .affiliation
        .clinic
        .organization
    )

    is_patient_or_booking_user = cancelled_by.pk in {
        appointment.patient_id,
        appointment.booked_by_id,
    }

    is_active_clinic_staff = (
        OrganizationMembership.objects.filter(
            organization=organization,
            user=cancelled_by,
            status=OrganizationMembership.Status.ACTIVE,
        ).exists()
    )

    if not (
        is_patient_or_booking_user
        or is_active_clinic_staff
    ):
        raise AppointmentAuthorizationError(
            _("You cannot cancel this appointment.")
        )

    if appointment.status == Appointment.Status.CANCELLED:
        # Retrying cancellation is safe. Deduplication prevents
        # duplicate cancellation notifications.
        _persist_cancellation_notification(
            appointment.pk
        )

        return appointment

    if appointment.status != Appointment.Status.CONFIRMED:
        raise InvalidAppointmentStateError(
            _("Only confirmed appointments can be cancelled.")
        )

    cancellation_note = cancellation_note.strip()

    if len(cancellation_note) > 250:
        raise AppointmentBookingError(
            _(
                "The cancellation note cannot exceed "
                "250 characters."
            )
        )

    slot = (
        AppointmentSlot.objects
        .select_for_update()
        .select_related(
            "affiliation",
            "affiliation__clinic",
            "affiliation__clinic__organization",
        )
        .get(pk=appointment.slot_id)
    )

    now = timezone.now()

    appointment.status = Appointment.Status.CANCELLED
    appointment.cancelled_at = now
    appointment.cancelled_by = cancelled_by
    appointment.cancellation_note = cancellation_note
    appointment.save(
        update_fields=[
            "status",
            "cancelled_at",
            "cancelled_by",
            "cancellation_note",
            "updated_at",
        ]
    )

    affiliation = slot.affiliation
    clinic = affiliation.clinic

    can_reopen_slot = (
        slot.starts_at > now
        and affiliation.status
        == DoctorClinicAffiliation.Status.ACTIVE
        and affiliation.accepts_online_bookings
        and clinic.status == Clinic.Status.ACTIVE
        and clinic.organization.status
        == Organization.Status.ACTIVE
    )

    slot.status = (
        AppointmentSlot.Status.OPEN
        if can_reopen_slot
        else AppointmentSlot.Status.BLOCKED
    )
    slot.held_by = None
    slot.hold_token = None
    slot.hold_expires_at = None
    slot.save(
        update_fields=[
            "status",
            "held_by",
            "hold_token",
            "hold_expires_at",
            "updated_at",
        ]
    )

    _persist_cancellation_notification(
        appointment.pk
    )

    return appointment
