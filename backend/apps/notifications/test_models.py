from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import (
    NotificationDeliveryAttempt,
    NotificationOutbox,
)


pytestmark = pytest.mark.django_db

User = get_user_model()


def create_user(username="notification-user"):
    return User.objects.create_user(
        username=username,
        password="test-password",
    )


def create_notification(
    recipient,
    deduplication_key,
    **overrides,
):
    values = {
        "recipient": recipient,
        "deduplication_key": deduplication_key,
        "channel": NotificationOutbox.Channel.EMAIL,
        "category": (
            NotificationOutbox.Category.APPOINTMENT_CONFIRMED
        ),
        "template_key": "appointment.confirmed",
        "payload": {
            "appointment_reference": "APT-TEST",
        },
        "scheduled_for": timezone.now(),
    }
    values.update(overrides)

    return NotificationOutbox.objects.create(**values)


def test_deduplication_key_must_be_unique():
    recipient = create_user()

    create_notification(
        recipient,
        "appointment:test:confirmed:email",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create_notification(
                recipient,
                "appointment:test:confirmed:email",
            )


def test_due_returns_only_deliverable_notifications():
    recipient = create_user()
    now = timezone.now()

    pending = create_notification(
        recipient,
        "due-pending",
        scheduled_for=now - timedelta(minutes=1),
    )

    failed = create_notification(
        recipient,
        "due-failed",
        status=NotificationOutbox.Status.FAILED,
        scheduled_for=now - timedelta(minutes=10),
        next_attempt_at=now - timedelta(minutes=1),
        attempt_count=1,
    )

    create_notification(
        recipient,
        "future-schedule",
        scheduled_for=now + timedelta(hours=1),
    )

    create_notification(
        recipient,
        "future-retry",
        status=NotificationOutbox.Status.FAILED,
        scheduled_for=now - timedelta(minutes=10),
        next_attempt_at=now + timedelta(hours=1),
        attempt_count=1,
    )

    create_notification(
        recipient,
        "attempts-exhausted",
        status=NotificationOutbox.Status.FAILED,
        scheduled_for=now - timedelta(minutes=10),
        attempt_count=5,
        max_attempts=5,
    )

    create_notification(
        recipient,
        "already-sent",
        status=NotificationOutbox.Status.SENT,
        scheduled_for=now - timedelta(minutes=10),
        sent_at=now,
    )

    returned_ids = set(
        NotificationOutbox.objects
        .due(at=now)
        .values_list("id", flat=True)
    )

    assert returned_ids == {
        pending.id,
        failed.id,
    }


def test_delivery_attempt_number_is_unique_per_notification():
    recipient = create_user()
    notification = create_notification(
        recipient,
        "unique-attempt-number",
    )

    NotificationDeliveryAttempt.objects.create(
        notification=notification,
        attempt_number=1,
        adapter_name="test-email-adapter",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            NotificationDeliveryAttempt.objects.create(
                notification=notification,
                attempt_number=1,
                adapter_name="test-email-adapter",
            )


def test_attempt_count_cannot_exceed_max_attempts():
    recipient = create_user()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create_notification(
                recipient,
                "invalid-attempt-count",
                attempt_count=4,
                max_attempts=3,
            )


def test_processing_notification_requires_lock_timestamp():
    recipient = create_user()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create_notification(
                recipient,
                "processing-without-lock",
                status=NotificationOutbox.Status.PROCESSING,
                locked_at=None,
            )


def test_sent_notification_requires_sent_timestamp():
    recipient = create_user()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create_notification(
                recipient,
                "sent-without-timestamp",
                status=NotificationOutbox.Status.SENT,
                sent_at=None,
            )


def test_non_sent_notification_cannot_have_sent_timestamp():
    recipient = create_user()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create_notification(
                recipient,
                "pending-with-sent-timestamp",
                status=NotificationOutbox.Status.PENDING,
                sent_at=timezone.now(),
            )


def test_completed_delivery_attempt_requires_timestamp():
    recipient = create_user()
    notification = create_notification(
        recipient,
        "completed-attempt-timestamp",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            NotificationDeliveryAttempt.objects.create(
                notification=notification,
                attempt_number=1,
                adapter_name="test-email-adapter",
                status=(
                    NotificationDeliveryAttempt.Status.SUCCEEDED
                ),
                completed_at=None,
            )


def test_valid_successful_delivery_attempt_is_saved():
    recipient = create_user()
    notification = create_notification(
        recipient,
        "successful-attempt",
    )
    completed_at = timezone.now()

    attempt = NotificationDeliveryAttempt.objects.create(
        notification=notification,
        attempt_number=1,
        adapter_name="test-email-adapter",
        status=NotificationDeliveryAttempt.Status.SUCCEEDED,
        external_reference="test-reference-123",
        completed_at=completed_at,
    )

    assert attempt.pk is not None
    assert (
        attempt.status
        == NotificationDeliveryAttempt.Status.SUCCEEDED
    )
    assert attempt.completed_at == completed_at