from datetime import timedelta

import pytest
from django.utils import timezone

from .adapters import TemporaryDeliveryError
from .models import (
    NotificationDeliveryAttempt,
    NotificationOutbox,
)
from .tasks import (
    deliver_notification,
    dispatch_due_notifications,
    recover_stale_notifications,
)
from .test_models import (
    create_notification,
    create_user,
)


pytestmark = pytest.mark.django_db


def test_in_app_notification_is_delivered_successfully():
    recipient = create_user("task-success-user")

    notification = create_notification(
        recipient,
        "task-success",
        channel=NotificationOutbox.Channel.IN_APP,
        scheduled_for=timezone.now(),
    )

    result = deliver_notification.run(
        str(notification.pk)
    )

    notification.refresh_from_db()

    attempt = (
        NotificationDeliveryAttempt.objects
        .get(notification=notification)
    )

    assert result["status"] == "sent"
    assert (
        notification.status
        == NotificationOutbox.Status.SENT
    )
    assert notification.sent_at is not None
    assert notification.locked_at is None
    assert notification.attempt_count == 1

    assert (
        attempt.status
        == NotificationDeliveryAttempt.Status.SUCCEEDED
    )
    assert attempt.adapter_name == "in_app"
    assert attempt.completed_at is not None
    assert attempt.external_reference == (
        f"in-app:{notification.pk}"
    )


def test_sent_notification_cannot_be_delivered_twice():
    recipient = create_user("task-duplicate-user")

    notification = create_notification(
        recipient,
        "task-duplicate",
        channel=NotificationOutbox.Channel.IN_APP,
        scheduled_for=timezone.now(),
    )

    first_result = deliver_notification.run(
        str(notification.pk)
    )
    second_result = deliver_notification.run(
        str(notification.pk)
    )

    notification.refresh_from_db()

    assert first_result["status"] == "sent"
    assert (
        second_result["status"]
        == "not_due_or_unavailable"
    )
    assert notification.attempt_count == 1

    assert (
        NotificationDeliveryAttempt.objects
        .filter(notification=notification)
        .count()
        == 1
    )


def test_future_notification_is_not_claimed():
    recipient = create_user("task-future-user")

    notification = create_notification(
        recipient,
        "task-future",
        channel=NotificationOutbox.Channel.IN_APP,
        scheduled_for=(
            timezone.now() + timedelta(hours=1)
        ),
    )

    result = deliver_notification.run(
        str(notification.pk)
    )

    notification.refresh_from_db()

    assert (
        result["status"]
        == "not_due_or_unavailable"
    )
    assert (
        notification.status
        == NotificationOutbox.Status.PENDING
    )
    assert notification.attempt_count == 0

    assert not (
        NotificationDeliveryAttempt.objects
        .filter(notification=notification)
        .exists()
    )


def test_unconfigured_channel_fails_permanently():
    recipient = create_user("task-permanent-user")

    notification = create_notification(
        recipient,
        "task-permanent",
        channel=NotificationOutbox.Channel.EMAIL,
        scheduled_for=timezone.now(),
    )

    result = deliver_notification.run(
        str(notification.pk)
    )

    notification.refresh_from_db()

    attempt = (
        NotificationDeliveryAttempt.objects
        .get(notification=notification)
    )

    assert result["status"] == "permanently_failed"
    assert (
        result["error_code"]
        == "delivery_not_configured"
    )

    assert (
        notification.status
        == NotificationOutbox.Status.FAILED
    )
    assert (
        notification.attempt_count
        == notification.max_attempts
    )
    assert notification.next_attempt_at is None
    assert notification.locked_at is None
    assert (
        notification.last_error_code
        == "delivery_not_configured"
    )

    assert (
        attempt.status
        == NotificationDeliveryAttempt.Status.FAILED
    )
    assert (
        attempt.error_code
        == "delivery_not_configured"
    )
    assert attempt.completed_at is not None


def test_temporary_failure_schedules_retry(
    monkeypatch,
):
    recipient = create_user("task-retry-user")

    notification = create_notification(
        recipient,
        "task-retry",
        channel=NotificationOutbox.Channel.IN_APP,
        scheduled_for=timezone.now(),
    )

    class FailingAdapter:
        name = "temporary-test-adapter"

        def deliver(self, _notification):
            raise TemporaryDeliveryError(
                "Temporary test failure"
            )

    monkeypatch.setattr(
        "apps.notifications.tasks."
        "get_delivery_adapter",
        lambda _channel: FailingAdapter(),
    )

    scheduled_retries = []

    def capture_retry(*, args, countdown):
        scheduled_retries.append(
            {
                "args": args,
                "countdown": countdown,
            }
        )

    monkeypatch.setattr(
        deliver_notification,
        "apply_async",
        capture_retry,
    )

    before = timezone.now()

    result = deliver_notification.run(
        str(notification.pk)
    )

    after = timezone.now()

    notification.refresh_from_db()

    attempt = (
        NotificationDeliveryAttempt.objects
        .get(notification=notification)
    )

    assert result["status"] == "retry_scheduled"
    assert (
        result["error_code"]
        == "temporary_delivery_error"
    )

    assert (
        notification.status
        == NotificationOutbox.Status.FAILED
    )
    assert notification.attempt_count == 1
    assert notification.locked_at is None

    assert notification.next_attempt_at is not None
    assert (
        before + timedelta(seconds=60)
        <= notification.next_attempt_at
        <= after + timedelta(seconds=60)
    )

    assert (
        attempt.status
        == NotificationDeliveryAttempt.Status.FAILED
    )
    assert (
        attempt.adapter_name
        == "temporary-test-adapter"
    )
    assert (
        attempt.error_code
        == "temporary_delivery_error"
    )

    assert scheduled_retries == [
        {
            "args": [str(notification.pk)],
            "countdown": 60,
        }
    ]


def test_dispatcher_queues_only_due_notifications(
    monkeypatch,
):
    recipient = create_user("task-dispatch-user")
    now = timezone.now()

    due_notification = create_notification(
        recipient,
        "dispatcher-due",
        channel=NotificationOutbox.Channel.IN_APP,
        scheduled_for=now - timedelta(minutes=1),
    )

    create_notification(
        recipient,
        "dispatcher-future",
        channel=NotificationOutbox.Channel.IN_APP,
        scheduled_for=now + timedelta(hours=1),
    )

    queued_ids = []

    monkeypatch.setattr(
        deliver_notification,
        "delay",
        lambda notification_id: queued_ids.append(
            notification_id
        ),
    )

    result = dispatch_due_notifications.run(
        batch_size=10
    )

    assert result == {"queued": 1}
    assert queued_ids == [str(due_notification.pk)]


def test_stale_processing_notification_is_recovered():
    recipient = create_user("stale-recovery-user")
    locked_at = timezone.now() - timedelta(minutes=30)

    notification = create_notification(
        recipient,
        "stale-processing",
        channel=NotificationOutbox.Channel.IN_APP,
        status=NotificationOutbox.Status.PROCESSING,
        scheduled_for=timezone.now(),
        attempt_count=1,
        locked_at=locked_at,
    )

    attempt = NotificationDeliveryAttempt.objects.create(
        notification=notification,
        attempt_number=1,
        status=(
            NotificationDeliveryAttempt.Status.STARTED
        ),
        adapter_name="test-adapter",
    )

    result = recover_stale_notifications.run(
        batch_size=100,
        stale_after_minutes=15,
    )

    notification.refresh_from_db()
    attempt.refresh_from_db()

    assert result == {"recovered": 1}

    assert (
        notification.status
        == NotificationOutbox.Status.FAILED
    )
    assert notification.locked_at is None
    assert notification.next_attempt_at is not None
    assert notification.last_error_code == "worker_lost"

    assert (
        attempt.status
        == NotificationDeliveryAttempt.Status.FAILED
    )
    assert attempt.error_code == "worker_lost"
    assert attempt.completed_at is not None


def test_recent_processing_notification_is_not_recovered():
    recipient = create_user("recent-lock-user")
    locked_at = timezone.now() - timedelta(minutes=5)

    notification = create_notification(
        recipient,
        "recent-processing",
        channel=NotificationOutbox.Channel.IN_APP,
        status=NotificationOutbox.Status.PROCESSING,
        scheduled_for=timezone.now(),
        attempt_count=1,
        locked_at=locked_at,
    )

    attempt = NotificationDeliveryAttempt.objects.create(
        notification=notification,
        attempt_number=1,
        status=(
            NotificationDeliveryAttempt.Status.STARTED
        ),
        adapter_name="test-adapter",
    )

    result = recover_stale_notifications.run(
        batch_size=100,
        stale_after_minutes=15,
    )

    notification.refresh_from_db()
    attempt.refresh_from_db()

    assert result == {"recovered": 0}

    assert (
        notification.status
        == NotificationOutbox.Status.PROCESSING
    )
    assert notification.locked_at == locked_at

    assert (
        attempt.status
        == NotificationDeliveryAttempt.Status.STARTED
    )
    assert attempt.completed_at is None


def test_exhausted_stale_notification_is_not_retried():
    recipient = create_user("exhausted-recovery-user")
    locked_at = timezone.now() - timedelta(minutes=30)

    notification = create_notification(
        recipient,
        "exhausted-processing",
        channel=NotificationOutbox.Channel.IN_APP,
        status=NotificationOutbox.Status.PROCESSING,
        scheduled_for=timezone.now(),
        attempt_count=3,
        max_attempts=3,
        locked_at=locked_at,
    )

    attempt = NotificationDeliveryAttempt.objects.create(
        notification=notification,
        attempt_number=3,
        status=(
            NotificationDeliveryAttempt.Status.STARTED
        ),
        adapter_name="test-adapter",
    )

    result = recover_stale_notifications.run(
        batch_size=100,
        stale_after_minutes=15,
    )

    notification.refresh_from_db()
    attempt.refresh_from_db()

    assert result == {"recovered": 1}

    assert (
        notification.status
        == NotificationOutbox.Status.FAILED
    )
    assert notification.locked_at is None
    assert notification.next_attempt_at is None
    assert notification.attempt_count == 3
    assert notification.last_error_code == "worker_lost"

    assert (
        attempt.status
        == NotificationDeliveryAttempt.Status.FAILED
    )
    assert attempt.error_code == "worker_lost"
    assert attempt.completed_at is not None