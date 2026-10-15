import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator
from django.db import models
from django.db.models import Q

from apps.appointments.models import Appointment
from apps.clinics.models import Clinic
from apps.organizations.models import Organization


def generate_case_reference():
    """
    Generate a non-sequential public support reference.

    The random component prevents users from easily guessing references
    belonging to other users.
    """
    return f"SUP-{uuid.uuid4().hex[:12].upper()}"


class SupportCaseQuerySet(models.QuerySet):
    def visible_to(self, user):
        if not user or not user.is_authenticated:
            return self.none()

        from apps.operations.models import StaffGrant
        from apps.operations.permissions import has_role

        if has_role(user, StaffGrant.Role.SUPPORT):
            return self

        return self.filter(requester=user)

    def active(self):
        return self.exclude(
            status=SupportCase.Status.CLOSED,
        )


class SupportCase(models.Model):
    """
    A non-clinical support request or complaint.

    Descriptions and resolution summaries must not contain diagnosis,
    prescriptions, medical records or other unnecessary clinical data.
    """

    class Category(models.TextChoices):
        APPOINTMENT = (
            "appointment",
            "Appointment or scheduling",
        )
        CLINIC = (
            "clinic",
            "Clinic experience",
        )
        DOCTOR_DIRECTORY = (
            "doctor_directory",
            "Doctor directory information",
        )
        ACCOUNT_ACCESS = (
            "account_access",
            "Account access",
        )
        NOTIFICATION = (
            "notification",
            "Notification or reminder",
        )
        FEE_OR_PAYMENT = (
            "fee_or_payment",
            "Fee or payment question",
        )
        ACCESSIBILITY = (
            "accessibility",
            "Accessibility",
        )
        PRIVACY = (
            "privacy",
            "Privacy concern",
        )
        OTHER = (
            "other",
            "Other",
        )

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        WAITING_FOR_USER = (
            "waiting_for_user",
            "Waiting for user",
        )
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    reference = models.CharField(
        max_length=20,
        unique=True,
        default=generate_case_reference,
        editable=False,
    )

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="support_cases",
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_support_cases",
        blank=True,
        null=True,
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="support_cases",
        blank=True,
        null=True,
    )

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="support_cases",
        blank=True,
        null=True,
    )

    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.PROTECT,
        related_name="support_cases",
        blank=True,
        null=True,
    )

    category = models.CharField(
        max_length=40,
        choices=Category.choices,
    )

    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.OPEN,
    )

    subject = models.CharField(
        max_length=160,
    )

    description = models.TextField(
        validators=[MaxLengthValidator(3000)],
        help_text=(
            "Describe the operational issue without including "
            "diagnosis, prescriptions or medical-record details."
        ),
    )

    resolution_summary = models.TextField(
        blank=True,
        validators=[MaxLengthValidator(3000)],
    )

    resolved_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    closed_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    objects = SupportCaseQuerySet.as_manager()

    class Meta:
        db_table = "support_case"
        ordering = ["-created_at"]

        constraints = [
            models.CheckConstraint(
                condition=Q(
                    category__in=[
                        "appointment",
                        "clinic",
                        "doctor_directory",
                        "account_access",
                        "notification",
                        "fee_or_payment",
                        "accessibility",
                        "privacy",
                        "other",
                    ]
                ),
                name="support_case_category_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    priority__in=[
                        "low",
                        "normal",
                        "high",
                    ]
                ),
                name="support_case_priority_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "open",
                        "in_progress",
                        "waiting_for_user",
                        "resolved",
                        "closed",
                    ]
                ),
                name="support_case_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status__in=[
                            "resolved",
                            "closed",
                        ],
                        resolved_at__isnull=False,
                    )
                    |
                    Q(
                        status__in=[
                            "open",
                            "in_progress",
                            "waiting_for_user",
                        ],
                        resolved_at__isnull=True,
                    )
                ),
                name="support_case_resolved_state",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status="closed",
                        closed_at__isnull=False,
                    )
                    |
                    (
                        ~Q(status="closed")
                        & Q(closed_at__isnull=True)
                    )
                ),
                name="support_case_closed_state",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "status",
                    "priority",
                    "created_at",
                ],
                name="support_status_priority_idx",
            ),
            models.Index(
                fields=[
                    "requester",
                    "created_at",
                ],
                name="support_requester_idx",
            ),
            models.Index(
                fields=[
                    "assigned_to",
                    "status",
                    "updated_at",
                ],
                name="support_assignee_idx",
            ),
            models.Index(
                fields=[
                    "organization",
                    "status",
                ],
                name="support_organization_idx",
            ),
            models.Index(
                fields=[
                    "clinic",
                    "status",
                ],
                name="support_clinic_idx",
            ),
        ]

    def __str__(self):
        return f"{self.reference}: {self.subject}"


class SupportCaseEvent(models.Model):
    """
    Immutable audit-history entry for a support case.

    Existing events must never be edited or deleted. Corrections should
    be recorded as new events.
    """

    class EventType(models.TextChoices):
        CREATED = "created", "Created"
        ASSIGNED = "assigned", "Assigned"
        STATUS_CHANGED = (
            "status_changed",
            "Status changed",
        )
        COMMENTED = "commented", "Commented"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"
        REOPENED = "reopened", "Reopened"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    case = models.ForeignKey(
        SupportCase,
        on_delete=models.PROTECT,
        related_name="events",
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="support_case_events",
        blank=True,
        null=True,
        help_text=(
            "Null only when an automated system action created "
            "the event."
        ),
    )

    event_type = models.CharField(
        max_length=30,
        choices=EventType.choices,
    )

    previous_status = models.CharField(
        max_length=30,
        choices=SupportCase.Status.choices,
        blank=True,
    )

    new_status = models.CharField(
        max_length=30,
        choices=SupportCase.Status.choices,
        blank=True,
    )

    message = models.TextField(
        blank=True,
        validators=[MaxLengthValidator(3000)],
        help_text=(
            "Operational note only. Do not include unnecessary "
            "medical or clinical information."
        ),
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Minimal structured audit data. Do not store secrets "
            "or clinical information."
        ),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "support_case_event"
        ordering = ["created_at", "id"]

        constraints = [
            models.CheckConstraint(
                condition=Q(
                    event_type__in=[
                        "created",
                        "assigned",
                        "status_changed",
                        "commented",
                        "resolved",
                        "closed",
                        "reopened",
                    ]
                ),
                name="support_event_type_valid",
            ),
            models.CheckConstraint(
                condition=(
                    (
                        Q(event_type="status_changed")
                        & ~Q(previous_status="")
                        & ~Q(new_status="")
                    )
                    |
                    ~Q(event_type="status_changed")
                ),
                name="support_event_status_fields",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "case",
                    "created_at",
                ],
                name="support_event_case_idx",
            ),
            models.Index(
                fields=[
                    "event_type",
                    "created_at",
                ],
                name="support_event_type_idx",
            ),
            models.Index(
                fields=[
                    "actor",
                    "created_at",
                ],
                name="support_event_actor_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(
                "Support case audit events are immutable."
            )

        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Support case audit events cannot be deleted."
        )

    def __str__(self):
        return (
            f"{self.case.reference}: "
            f"{self.get_event_type_display()}"
        )
