import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from apps.appointments.models import Appointment


class NotificationOutboxQuerySet(models.QuerySet):
    def due(self, at=None):
        from django.utils import timezone

        at = at or timezone.now()

        return self.filter(
            status__in=[
                NotificationOutbox.Status.PENDING,
                NotificationOutbox.Status.FAILED,
            ],
            scheduled_for__lte=at,
            attempt_count__lt=F("max_attempts"),
        ).filter(
            Q(next_attempt_at__isnull=True)
            | Q(next_attempt_at__lte=at)
        )


class NotificationOutbox(models.Model):
    """
    Provider-neutral request for asynchronous delivery.

    The payload must contain only minimal template variables and
    must not contain diagnosis or clinical information.
    """

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"
        PUSH = "push", "Push notification"
        IN_APP = "in_app", "In-app notification"

    class Category(models.TextChoices):
        APPOINTMENT_CONFIRMED = (
            "appointment_confirmed",
            "Appointment confirmed",
        )
        APPOINTMENT_REMINDER = (
            "appointment_reminder",
            "Appointment reminder",
        )
        APPOINTMENT_CANCELLED = (
            "appointment_cancelled",
            "Appointment cancelled",
        )

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    deduplication_key = models.CharField(
        max_length=200,
        unique=True,
        help_text=(
            "Stable idempotency key for this notification."
        ),
    )

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="notification_outbox_items",
    )

    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.PROTECT,
        related_name="notifications",
        blank=True,
        null=True,
    )

    channel = models.CharField(
        max_length=20,
        choices=Channel.choices,
    )

    category = models.CharField(
        max_length=40,
        choices=Category.choices,
    )

    template_key = models.CharField(
        max_length=120,
    )

    locale = models.CharField(
        max_length=10,
        default="en",
    )

    payload = models.JSONField(
        default=dict,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    scheduled_for = models.DateTimeField()

    attempt_count = models.PositiveSmallIntegerField(
        default=0,
    )

    max_attempts = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1)],
    )

    next_attempt_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    locked_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    sent_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    last_error_code = models.CharField(
        max_length=100,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    objects = NotificationOutboxQuerySet.as_manager()

    class Meta:
        db_table = "notifications_outbox"
        ordering = ["scheduled_for", "created_at"]

        constraints = [
            models.CheckConstraint(
                condition=Q(
                    channel__in=[
                        "email",
                        "sms",
                        "push",
                        "in_app",
                    ]
                ),
                name="notification_channel_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    category__in=[
                        "appointment_confirmed",
                        "appointment_reminder",
                        "appointment_cancelled",
                    ]
                ),
                name="notification_category_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "pending",
                        "processing",
                        "sent",
                        "failed",
                        "cancelled",
                    ]
                ),
                name="notification_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(max_attempts__gte=1),
                name="notification_max_attempts_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    attempt_count__lte=F("max_attempts")
                ),
                name="notification_attempts_valid",
            ),
            models.CheckConstraint(
                condition=(
                    (
                        Q(status="processing")
                        & Q(locked_at__isnull=False)
                    )
                    | ~Q(status="processing")
                ),
                name="notification_processing_lock",
            ),
            models.CheckConstraint(
                condition=(
                    (
                        Q(status="sent")
                        & Q(sent_at__isnull=False)
                    )
                    |
                    (
                        ~Q(status="sent")
                        & Q(sent_at__isnull=True)
                    )
                ),
                name="notification_sent_state",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "status",
                    "scheduled_for",
                    "next_attempt_at",
                ],
                name="notification_due_idx",
            ),
            models.Index(
                fields=["recipient", "created_at"],
                name="notification_recipient_idx",
            ),
            models.Index(
                fields=["appointment", "category"],
                name="notification_appt_idx",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.category} via {self.channel} "
            f"for {self.recipient}"
        )


class NotificationDeliveryAttempt(models.Model):
    class Status(models.TextChoices):
        STARTED = "started", "Started"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    notification = models.ForeignKey(
        NotificationOutbox,
        on_delete=models.PROTECT,
        related_name="delivery_attempts",
    )

    attempt_number = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.STARTED,
    )

    adapter_name = models.CharField(
        max_length=100,
        help_text=(
            "Internal delivery adapter identifier, "
            "not a hard-coded vendor dependency."
        ),
    )

    external_reference = models.CharField(
        max_length=200,
        blank=True,
    )

    error_code = models.CharField(
        max_length=100,
        blank=True,
    )

    started_at = models.DateTimeField(
        auto_now_add=True,
    )

    completed_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "notifications_delivery_attempt"
        ordering = [
            "notification",
            "attempt_number",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "notification",
                    "attempt_number",
                ],
                name="unique_notification_attempt",
            ),
            models.CheckConstraint(
                condition=Q(attempt_number__gte=1),
                name="delivery_attempt_number_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "started",
                        "succeeded",
                        "failed",
                    ]
                ),
                name="delivery_attempt_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    (
                        Q(status="started")
                        & Q(completed_at__isnull=True)
                    )
                    |
                    (
                        Q(
                            status__in=[
                                "succeeded",
                                "failed",
                            ]
                        )
                        & Q(completed_at__isnull=False)
                    )
                ),
                name="delivery_attempt_state_valid",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.notification_id} "
            f"attempt {self.attempt_number}"
        )

class InAppNotificationQuerySet(models.QuerySet):
    def for_recipient(self, recipient):
        return self.filter(
            outbox__recipient=recipient,
            outbox__channel=(
                NotificationOutbox.Channel.IN_APP
            ),
            outbox__status=NotificationOutbox.Status.SENT,
        )

    def unread(self):
        return self.filter(read_at__isnull=True)


class InAppNotification(models.Model):
    """
    Patient-visible inbox record for a delivered in-app
    notification.

    Delivery state remains in NotificationOutbox. This model only
    tracks inbox creation and whether the recipient has read it.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    outbox = models.OneToOneField(
        NotificationOutbox,
        on_delete=models.PROTECT,
        related_name="in_app_notification",
    )

    read_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    objects = InAppNotificationQuerySet.as_manager()

    class Meta:
        db_table = "notifications_in_app"
        ordering = ["-created_at"]

        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(read_at__isnull=True)
                    | Q(read_at__gte=F("created_at"))
                ),
                name="in_app_read_after_creation",
            ),
        ]

        indexes = [
            models.Index(
                fields=["read_at", "created_at"],
                name="in_app_notification_read_idx",
            ),
        ]

    def __str__(self) -> str:
        state = (
            "read"
            if self.read_at is not None
            else "unread"
        )

        return (
            f"In-app notification {self.pk} "
            f"({state})"
        )