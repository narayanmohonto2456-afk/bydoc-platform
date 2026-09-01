import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .adapters import (
    NotificationDeliveryError,
    PermanentDeliveryError,
    TemporaryDeliveryError,
    get_delivery_adapter,
)
from .models import (
    NotificationDeliveryAttempt,
    NotificationOutbox,
)


logger = logging.getLogger(__name__)

MAX_RETRY_DELAY_SECONDS = 3600


def _retry_delay_seconds(attempt_number):
    """
    Exponential backoff:

    Attempt 1: 60 seconds
    Attempt 2: 120 seconds
    Attempt 3: 240 seconds

    The delay is capped at one hour.
    """
    return min(
        60 * (2 ** max(attempt_number - 1, 0)),
        MAX_RETRY_DELAY_SECONDS,
    )


@transaction.atomic
def _claim_notification(notification_id):
    """
    Atomically claim one due notification.

    Only the outbox row is selected and locked. Related nullable
    records must not be joined into a SELECT FOR UPDATE query.
    """
    try:
        notification = (
            NotificationOutbox.objects
            .select_for_update()
            .get(pk=notification_id)
        )
    except NotificationOutbox.DoesNotExist:
        return None, None

    now = timezone.now()

    if notification.status not in {
        NotificationOutbox.Status.PENDING,
        NotificationOutbox.Status.FAILED,
    }:
        return None, None

    if notification.scheduled_for > now:
        return None, None

    if (
        notification.next_attempt_at is not None
        and notification.next_attempt_at > now
    ):
        return None, None

    if (
        notification.attempt_count
        >= notification.max_attempts
    ):
        return None, None

    notification.attempt_count += 1
    notification.status = (
        NotificationOutbox.Status.PROCESSING
    )
    notification.locked_at = now
    notification.next_attempt_at = None
    notification.save(
        update_fields=[
            "attempt_count",
            "status",
            "locked_at",
            "next_attempt_at",
            "updated_at",
        ]
    )

    attempt = NotificationDeliveryAttempt.objects.create(
        notification=notification,
        attempt_number=notification.attempt_count,
        status=(
            NotificationDeliveryAttempt.Status.STARTED
        ),
        adapter_name="pending",
    )

    return notification, attempt


@transaction.atomic
def _mark_delivery_succeeded(
    notification_id,
    attempt_id,
    adapter_name,
    external_reference,
):
    notification = (
        NotificationOutbox.objects
        .select_for_update()
        .get(pk=notification_id)
    )

    attempt = (
        NotificationDeliveryAttempt.objects
        .select_for_update()
        .get(pk=attempt_id)
    )

    now = timezone.now()

    attempt.status = (
        NotificationDeliveryAttempt.Status.SUCCEEDED
    )
    attempt.adapter_name = adapter_name
    attempt.external_reference = external_reference[:200]
    attempt.error_code = ""
    attempt.completed_at = now
    attempt.save(
        update_fields=[
            "status",
            "adapter_name",
            "external_reference",
            "error_code",
            "completed_at",
        ]
    )

    notification.status = NotificationOutbox.Status.SENT
    notification.sent_at = now
    notification.locked_at = None
    notification.next_attempt_at = None
    notification.last_error_code = ""
    notification.save(
        update_fields=[
            "status",
            "sent_at",
            "locked_at",
            "next_attempt_at",
            "last_error_code",
            "updated_at",
        ]
    )


@transaction.atomic
def _mark_delivery_failed(
    notification_id,
    attempt_id,
    adapter_name,
    error_code,
    permanent=False,
):
    notification = (
        NotificationOutbox.objects
        .select_for_update()
        .get(pk=notification_id)
    )

    attempt = (
        NotificationDeliveryAttempt.objects
        .select_for_update()
        .get(pk=attempt_id)
    )

    now = timezone.now()

    safe_error_code = error_code[:100]

    attempt.status = (
        NotificationDeliveryAttempt.Status.FAILED
    )
    attempt.adapter_name = adapter_name[:100]
    attempt.error_code = safe_error_code
    attempt.completed_at = now
    attempt.save(
        update_fields=[
            "status",
            "adapter_name",
            "error_code",
            "completed_at",
        ]
    )

    if permanent:
        notification.attempt_count = (
            notification.max_attempts
        )

    has_attempts_remaining = (
        notification.attempt_count
        < notification.max_attempts
    )

    retry_delay = None

    if has_attempts_remaining and not permanent:
        retry_delay = _retry_delay_seconds(
            notification.attempt_count
        )
        notification.next_attempt_at = (
            now + timedelta(seconds=retry_delay)
        )
    else:
        notification.next_attempt_at = None

    notification.status = NotificationOutbox.Status.FAILED
    notification.locked_at = None
    notification.last_error_code = safe_error_code
    notification.save(
        update_fields=[
            "status",
            "attempt_count",
            "locked_at",
            "next_attempt_at",
            "last_error_code",
            "updated_at",
        ]
    )

    return retry_delay


@shared_task(
    name="notifications.deliver_notification",
)
def deliver_notification(notification_id):
    """
    Deliver one outbox notification.

    Database state controls retry limits. Only safe error codes are
    persisted; exception messages and provider responses are not.
    """
    notification, attempt = _claim_notification(
        notification_id
    )

    if notification is None:
        return {
            "notification_id": str(notification_id),
            "status": "not_due_or_unavailable",
        }

    adapter_name = "unavailable"

    try:
        adapter = get_delivery_adapter(
            notification.channel
        )
        adapter_name = adapter.name

        result = adapter.deliver(notification)

    except PermanentDeliveryError as error:
        _mark_delivery_failed(
            notification.pk,
            attempt.pk,
            adapter_name,
            error.error_code,
            permanent=True,
        )

        return {
            "notification_id": str(notification.pk),
            "status": "permanently_failed",
            "error_code": error.error_code,
        }

    except TemporaryDeliveryError as error:
        retry_delay = _mark_delivery_failed(
            notification.pk,
            attempt.pk,
            adapter_name,
            error.error_code,
        )

        if retry_delay is not None:
            deliver_notification.apply_async(
                args=[str(notification.pk)],
                countdown=retry_delay,
            )

        return {
            "notification_id": str(notification.pk),
            "status": "retry_scheduled",
            "error_code": error.error_code,
        }

    except NotificationDeliveryError as error:
        retry_delay = _mark_delivery_failed(
            notification.pk,
            attempt.pk,
            adapter_name,
            error.error_code,
        )

        if retry_delay is not None:
            deliver_notification.apply_async(
                args=[str(notification.pk)],
                countdown=retry_delay,
            )

        return {
            "notification_id": str(notification.pk),
            "status": "retry_scheduled",
            "error_code": error.error_code,
        }

    except Exception:
        logger.exception(
            "Unexpected notification delivery failure for %s.",
            notification.pk,
        )

        error_code = "unexpected_delivery_error"

        retry_delay = _mark_delivery_failed(
            notification.pk,
            attempt.pk,
            adapter_name,
            error_code,
        )

        if retry_delay is not None:
            deliver_notification.apply_async(
                args=[str(notification.pk)],
                countdown=retry_delay,
            )

        return {
            "notification_id": str(notification.pk),
            "status": "retry_scheduled",
            "error_code": error_code,
        }

    _mark_delivery_succeeded(
        notification.pk,
        attempt.pk,
        adapter.name,
        result.external_reference,
    )

    return {
        "notification_id": str(notification.pk),
        "status": "sent",
    }


@shared_task(
    name="notifications.dispatch_due_notifications",
)
def dispatch_due_notifications(batch_size=100):
    """
    Queue a bounded batch of due outbox records.
    """
    batch_size = max(
        1,
        min(int(batch_size), 500),
    )

    notification_ids = list(
        NotificationOutbox.objects
        .due()
        .order_by("scheduled_for")
        .values_list("pk", flat=True)[:batch_size]
    )

    for notification_id in notification_ids:
        deliver_notification.delay(
            str(notification_id)
        )

    return {
        "queued": len(notification_ids),
    }

@shared_task(
    name="notifications.recover_stale_notifications",
)
def recover_stale_notifications(
    batch_size=100,
    stale_after_minutes=15,
):
    """
    Recover notifications abandoned by a crashed worker.

    A recovered notification becomes immediately eligible for the
    normal dispatcher unless it has exhausted all attempts.
    """
    batch_size = max(
        1,
        min(int(batch_size), 500),
    )
    stale_after_minutes = max(
        1,
        int(stale_after_minutes),
    )

    now = timezone.now()
    stale_before = now - timedelta(
        minutes=stale_after_minutes
    )

    notification_ids = list(
        NotificationOutbox.objects
        .filter(
            status=NotificationOutbox.Status.PROCESSING,
            locked_at__lte=stale_before,
        )
        .order_by("locked_at")
        .values_list("pk", flat=True)[:batch_size]
    )

    recovered = 0

    for notification_id in notification_ids:
        with transaction.atomic():
            try:
                notification = (
                    NotificationOutbox.objects
                    .select_for_update(skip_locked=True)
                    .get(pk=notification_id)
                )
            except NotificationOutbox.DoesNotExist:
                continue

            if (
                notification.status
                != NotificationOutbox.Status.PROCESSING
            ):
                continue

            if (
                notification.locked_at is None
                or notification.locked_at > stale_before
            ):
                continue

            attempt = (
                NotificationDeliveryAttempt.objects
                .select_for_update()
                .filter(
                    notification=notification,
                    attempt_number=(
                        notification.attempt_count
                    ),
                    status=(
                        NotificationDeliveryAttempt
                        .Status
                        .STARTED
                    ),
                )
                .first()
            )

            if attempt is not None:
                attempt.status = (
                    NotificationDeliveryAttempt
                    .Status
                    .FAILED
                )
                attempt.error_code = "worker_lost"
                attempt.completed_at = now
                attempt.save(
                    update_fields=[
                        "status",
                        "error_code",
                        "completed_at",
                    ]
                )

            has_attempts_remaining = (
                notification.attempt_count
                < notification.max_attempts
            )

            notification.status = (
                NotificationOutbox.Status.FAILED
            )
            notification.locked_at = None
            notification.last_error_code = "worker_lost"
            notification.next_attempt_at = (
                now
                if has_attempts_remaining
                else None
            )
            notification.save(
                update_fields=[
                    "status",
                    "locked_at",
                    "last_error_code",
                    "next_attempt_at",
                    "updated_at",
                ]
            )

            recovered += 1

    return {
        "recovered": recovered,
    }