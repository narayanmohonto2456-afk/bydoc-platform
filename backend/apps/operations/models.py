import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class StaffGrant(models.Model):
    class Role(models.TextChoices):
        PROVIDER = "provider", "Provider reviews"
        SUPPORT = "support", "Support cases"
        FINANCE = "finance", "Payments and refunds"
        SCHEDULE = "schedule", "Appointment exceptions"
        DELIVERY = "delivery", "Notification delivery"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="operations_grants")
    role = models.CharField(max_length=16, choices=Role.choices)
    active = models.BooleanField(default=True)
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="operations_grants_made")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "role"], name="unique_operations_staff_role")]
        indexes = [models.Index(fields=["role", "active"], name="operations_role_active_idx")]

    def __str__(self):
        return f"{self.user}: {self.get_role_display()}"


class OperationsEvent(models.Model):
    """Append-only record of privileged operations; no clinical details or secrets."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="operations_events")
    action = models.CharField(max_length=80)
    subject_type = models.CharField(max_length=40)
    subject_id = models.CharField(max_length=80)
    note = models.CharField(max_length=500, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["subject_type", "subject_id", "created_at"], name="operations_subject_idx"),
            models.Index(fields=["actor", "created_at"], name="operations_actor_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Operations audit events are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Operations audit events cannot be deleted.")


class PaymentInvestigation(models.Model):
    """Human review state; never overrides a Razorpay payment or refund state."""

    intent = models.OneToOneField("payments.PaymentIntent", on_delete=models.PROTECT, related_name="investigation")
    resolved = models.BooleanField(default=False)
    note = models.CharField(max_length=500)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Investigation for {self.intent_id}"


class WebhookFailure(models.Model):
    """Verified Razorpay webhook failures without storing the payload or signature."""

    event_id = models.CharField(max_length=128, primary_key=True)
    event_type = models.CharField(max_length=80, blank=True)
    error_code = models.CharField(max_length=80)
    failed_count = models.PositiveIntegerField(default=1)
    resolved = models.BooleanField(default=False)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
