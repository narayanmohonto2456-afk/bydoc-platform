import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.doctors.models import DoctorClinicAffiliation


class AvailabilityRule(models.Model):
    """Recurring weekly availability for a doctor at a clinic."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    affiliation = models.ForeignKey(
        DoctorClinicAffiliation,
        on_delete=models.PROTECT,
        related_name="availability_rules",
    )
    weekday = models.PositiveSmallIntegerField(
        help_text="Monday is 0 and Sunday is 6.",
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    valid_from = models.DateField()
    valid_until = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "appointments_availability_rule"
        ordering = ["affiliation", "weekday", "start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["affiliation", "weekday", "start_time", "valid_from"],
                name="unique_availability_rule",
            ),
            models.CheckConstraint(
                condition=Q(weekday__gte=0, weekday__lte=6),
                name="availability_weekday_valid",
            ),
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")),
                name="availability_time_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(valid_until__isnull=True)
                    | Q(valid_until__gte=F("valid_from"))
                ),
                name="availability_dates_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["affiliation", "weekday", "is_active"],
                name="availability_lookup_idx",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.affiliation} - weekday {self.weekday}: "
            f"{self.start_time}-{self.end_time}"
        )


class ScheduleException(models.Model):
    """A closure, unavailable period, or custom-hours override."""

    class Type(models.TextChoices):
        CLOSED = "closed", "Closed for the day"
        UNAVAILABLE = "unavailable", "Unavailable period"
        CUSTOM_HOURS = "custom_hours", "Custom hours"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    affiliation = models.ForeignKey(
        DoctorClinicAffiliation,
        on_delete=models.PROTECT,
        related_name="schedule_exceptions",
    )
    exception_date = models.DateField()
    exception_type = models.CharField(max_length=20, choices=Type.choices)
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    public_note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "appointments_schedule_exception"
        ordering = ["exception_date", "start_time"]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    exception_type__in=["closed", "unavailable", "custom_hours"]
                ),
                name="schedule_exception_type_valid",
            ),
            models.CheckConstraint(
                condition=(
                    (
                        Q(exception_type="closed")
                        & Q(start_time__isnull=True)
                        & Q(end_time__isnull=True)
                    )
                    | (
                        Q(exception_type__in=["unavailable", "custom_hours"])
                        & Q(start_time__isnull=False)
                        & Q(end_time__isnull=False)
                        & Q(end_time__gt=F("start_time"))
                    )
                ),
                name="schedule_exception_time_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["affiliation", "exception_date"],
                name="schedule_exception_idx",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.affiliation} - {self.exception_date} "
            f"({self.exception_type})"
        )


class AppointmentSlotQuerySet(models.QuerySet):
    def available(self):
        return self.filter(
            Q(affiliation__doctor__registrations__valid_until__isnull=True)
            | Q(affiliation__doctor__registrations__valid_until__gte=timezone.localdate()),
            status=AppointmentSlot.Status.OPEN,
            affiliation__status=DoctorClinicAffiliation.Status.ACTIVE,
            affiliation__accepts_online_bookings=True,
            affiliation__doctor__status="active",
            affiliation__doctor__registrations__verification_status="verified",
        ).distinct()


class AppointmentSlot(models.Model):
    """A concrete, uniquely bookable time interval."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        HELD = "held", "Temporarily held"
        BOOKED = "booked", "Booked"
        BLOCKED = "blocked", "Blocked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    affiliation = models.ForeignKey(
        DoctorClinicAffiliation,
        on_delete=models.PROTECT,
        related_name="appointment_slots",
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    held_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="appointment_slots_held",
        blank=True,
        null=True,
    )
    hold_token = models.UUIDField(unique=True, blank=True, null=True)
    hold_expires_at = models.DateTimeField(blank=True, null=True)
    schedule_blocked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AppointmentSlotQuerySet.as_manager()

    class Meta:
        db_table = "appointments_slot"
        ordering = ["starts_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["affiliation", "starts_at"],
                name="unique_affiliation_slot",
            ),
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")),
                name="appointment_slot_time_valid",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["open", "held", "booked", "blocked"]),
                name="appointment_slot_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    (
                        Q(status="held")
                        & Q(held_by__isnull=False)
                        & Q(hold_token__isnull=False)
                        & Q(hold_expires_at__isnull=False)
                    )
                    | (
                        ~Q(status="held")
                        & Q(held_by__isnull=True)
                        & Q(hold_token__isnull=True)
                        & Q(hold_expires_at__isnull=True)
                    )
                ),
                name="appointment_hold_state_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["affiliation", "status", "starts_at"],
                name="appointment_slot_lookup_idx",
            ),
            models.Index(
                fields=["status", "hold_expires_at"],
                name="appointment_hold_expiry_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.affiliation} - {self.starts_at}"


class Appointment(models.Model):
    """An auditable booking for exactly one appointment slot."""

    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed"
        CHECKED_IN = "checked_in", "Checked in"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        NO_SHOW = "no_show", "No show"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking_reference = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    booking_request_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        help_text="Idempotency key supplied for a booking request.",
    )
    slot = models.ForeignKey(
        AppointmentSlot,
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    consultation_fee = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )
    currency_code = models.CharField(max_length=3, blank=True, default="")
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="patient_appointments",
    )
    booked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="appointments_booked",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CONFIRMED,
    )
    cancelled_at = models.DateTimeField(blank=True, null=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="appointments_cancelled",
        blank=True,
        null=True,
    )
    cancellation_note = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "appointments_appointment"
        ordering = ["-slot__starts_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["slot"],
                condition=~Q(status="cancelled"),
                name="unique_non_cancelled_slot_appt",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "confirmed", "checked_in", "completed", "cancelled", "no_show"
                    ]
                ),
                name="appointment_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    (Q(status="cancelled") & Q(cancelled_at__isnull=False))
                    | (
                        ~Q(status="cancelled")
                        & Q(cancelled_at__isnull=True)
                        & Q(cancelled_by__isnull=True)
                        & Q(cancellation_note="")
                    )
                ),
                name="appointment_cancel_state_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["patient", "status"],
                name="patient_appointment_idx",
            ),
            models.Index(
                fields=["status", "created_at"],
                name="appointment_status_idx",
            ),
        ]

    def __str__(self) -> str:
        return str(self.booking_reference)
