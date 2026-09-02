from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from .adapters import InAppDeliveryAdapter
from .models import (
    InAppNotification,
    NotificationOutbox,
)
from .test_models import (
    create_notification,
    create_user,
)


pytestmark = pytest.mark.django_db


def create_sent_in_app_notification(
    recipient,
    deduplication_key,
):
    now = timezone.now()

    outbox = create_notification(
        recipient,
        deduplication_key,
        channel=NotificationOutbox.Channel.IN_APP,
        status=NotificationOutbox.Status.SENT,
        sent_at=now,
        scheduled_for=now,
    )

    inbox_item = InAppNotification.objects.create(
        outbox=outbox
    )

    return outbox, inbox_item


def test_recipient_only_sees_their_sent_in_app_items():
    recipient = create_user("inbox-recipient")
    unrelated_user = create_user("inbox-unrelated")

    own_outbox, own_item = (
        create_sent_in_app_notification(
            recipient,
            "inbox-own-item",
        )
    )

    _other_outbox, other_item = (
        create_sent_in_app_notification(
            unrelated_user,
            "inbox-other-item",
        )
    )

    pending_outbox = create_notification(
        recipient,
        "inbox-pending-item",
        channel=NotificationOutbox.Channel.IN_APP,
        status=NotificationOutbox.Status.PENDING,
        scheduled_for=timezone.now(),
    )
    pending_item = InAppNotification.objects.create(
        outbox=pending_outbox
    )

    email_outbox = create_notification(
        recipient,
        "inbox-email-item",
        channel=NotificationOutbox.Channel.EMAIL,
        status=NotificationOutbox.Status.SENT,
        sent_at=timezone.now(),
        scheduled_for=timezone.now(),
    )
    email_item = InAppNotification.objects.create(
        outbox=email_outbox
    )

    returned_ids = set(
        InAppNotification.objects
        .for_recipient(recipient)
        .values_list("pk", flat=True)
    )

    assert returned_ids == {own_item.pk}
    assert other_item.pk not in returned_ids
    assert pending_item.pk not in returned_ids
    assert email_item.pk not in returned_ids
    assert own_outbox.recipient == recipient


def test_unread_queryset_excludes_read_items():
    recipient = create_user("inbox-unread-user")

    _first_outbox, unread_item = (
        create_sent_in_app_notification(
            recipient,
            "inbox-unread-item",
        )
    )

    _second_outbox, read_item = (
        create_sent_in_app_notification(
            recipient,
            "inbox-read-item",
        )
    )

    read_item.read_at = timezone.now()
    read_item.save(update_fields=["read_at"])

    unread_ids = set(
        InAppNotification.objects
        .for_recipient(recipient)
        .unread()
        .values_list("pk", flat=True)
    )

    assert unread_ids == {unread_item.pk}
    assert read_item.pk not in unread_ids


def test_outbox_can_have_only_one_inbox_item():
    recipient = create_user("inbox-unique-user")

    outbox, _inbox_item = (
        create_sent_in_app_notification(
            recipient,
            "inbox-unique-item",
        )
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            InAppNotification.objects.create(
                outbox=outbox
            )


def test_read_timestamp_cannot_precede_creation():
    recipient = create_user("inbox-timestamp-user")

    _outbox, inbox_item = (
        create_sent_in_app_notification(
            recipient,
            "inbox-invalid-timestamp",
        )
    )

    invalid_read_time = (
        inbox_item.created_at - timedelta(minutes=1)
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            (
                InAppNotification.objects
                .filter(pk=inbox_item.pk)
                .update(read_at=invalid_read_time)
            )


def test_in_app_adapter_is_idempotent():
    recipient = create_user("inbox-adapter-user")

    notification = create_notification(
        recipient,
        "inbox-adapter-idempotency",
        channel=NotificationOutbox.Channel.IN_APP,
        scheduled_for=timezone.now(),
    )

    adapter = InAppDeliveryAdapter()

    first_result = adapter.deliver(notification)
    second_result = adapter.deliver(notification)

    assert first_result == second_result

    assert (
        InAppNotification.objects
        .filter(outbox=notification)
        .count()
        == 1
    )

    assert first_result.external_reference == (
        f"in-app:{notification.pk}"
    )