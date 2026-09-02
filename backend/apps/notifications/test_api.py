import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from .models import InAppNotification
from .test_inbox import (
    create_sent_in_app_notification,
)
from .test_models import create_user


pytestmark = pytest.mark.django_db


def response_items(response):
    if isinstance(response.data, dict):
        return response.data.get("results", [])

    return response.data


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)

    return client


def test_anonymous_user_cannot_access_inbox():
    client = APIClient()

    list_response = client.get(
        reverse("notifications:inbox-list")
    )
    count_response = client.get(
        reverse("notifications:unread-count")
    )
    mark_all_response = client.post(
        reverse("notifications:mark-all-read"),
        {},
        format="json",
    )

    for response in (
        list_response,
        count_response,
        mark_all_response,
    ):
        assert response.status_code in {
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        }


def test_user_only_sees_their_own_notifications():
    user = create_user("api-inbox-user")
    unrelated_user = create_user("api-inbox-unrelated")

    _own_outbox, own_item = (
        create_sent_in_app_notification(
            user,
            "api-own-notification",
        )
    )

    create_sent_in_app_notification(
        unrelated_user,
        "api-unrelated-notification",
    )

    client = authenticated_client(user)

    response = client.get(
        reverse("notifications:inbox-list")
    )

    assert response.status_code == status.HTTP_200_OK

    items = response_items(response)

    assert len(items) == 1
    assert items[0]["id"] == str(own_item.pk)
    assert items[0]["is_read"] is False

    forbidden_fields = {
        "recipient",
        "recipient_id",
        "deduplication_key",
        "status",
        "attempt_count",
        "max_attempts",
        "locked_at",
        "last_error_code",
        "adapter_name",
    }

    assert forbidden_fields.isdisjoint(
        items[0].keys()
    )


def test_inbox_can_filter_unread_and_read_items():
    user = create_user("api-inbox-filter-user")

    _unread_outbox, unread_item = (
        create_sent_in_app_notification(
            user,
            "api-filter-unread",
        )
    )

    _read_outbox, read_item = (
        create_sent_in_app_notification(
            user,
            "api-filter-read",
        )
    )

    read_item.read_at = timezone.now()
    read_item.save(update_fields=["read_at"])

    client = authenticated_client(user)

    unread_response = client.get(
        reverse("notifications:inbox-list"),
        {"unread": "true"},
    )

    read_response = client.get(
        reverse("notifications:inbox-list"),
        {"unread": "false"},
    )

    invalid_response = client.get(
        reverse("notifications:inbox-list"),
        {"unread": "invalid"},
    )

    assert (
        unread_response.status_code
        == status.HTTP_200_OK
    )
    assert (
        read_response.status_code
        == status.HTTP_200_OK
    )
    assert (
        invalid_response.status_code
        == status.HTTP_400_BAD_REQUEST
    )

    unread_ids = {
        item["id"]
        for item in response_items(unread_response)
    }

    read_ids = {
        item["id"]
        for item in response_items(read_response)
    }

    assert unread_ids == {str(unread_item.pk)}
    assert read_ids == {str(read_item.pk)}


def test_unread_count_is_scoped_to_current_user():
    user = create_user("api-count-user")
    unrelated_user = create_user("api-count-unrelated")

    create_sent_in_app_notification(
        user,
        "api-count-unread-one",
    )
    create_sent_in_app_notification(
        user,
        "api-count-unread-two",
    )

    _read_outbox, read_item = (
        create_sent_in_app_notification(
            user,
            "api-count-read",
        )
    )
    read_item.read_at = timezone.now()
    read_item.save(update_fields=["read_at"])

    create_sent_in_app_notification(
        unrelated_user,
        "api-count-unrelated-item",
    )

    client = authenticated_client(user)

    response = client.get(
        reverse("notifications:unread-count")
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"unread_count": 2}


def test_user_can_mark_own_notification_read_idempotently():
    user = create_user("api-mark-read-user")

    _outbox, inbox_item = (
        create_sent_in_app_notification(
            user,
            "api-mark-read-item",
        )
    )

    client = authenticated_client(user)

    url = reverse(
        "notifications:mark-read",
        kwargs={
            "notification_id": inbox_item.pk,
        },
    )

    first_response = client.post(
        url,
        {},
        format="json",
    )

    second_response = client.post(
        url,
        {},
        format="json",
    )

    assert (
        first_response.status_code
        == status.HTTP_200_OK
    )
    assert (
        second_response.status_code
        == status.HTTP_200_OK
    )

    inbox_item.refresh_from_db()

    assert inbox_item.read_at is not None
    assert first_response.data["is_read"] is True
    assert second_response.data["is_read"] is True
    assert (
        second_response.data["read_at"]
        == first_response.data["read_at"]
    )


def test_user_cannot_mark_another_users_notification_read():
    owner = create_user("api-private-owner")
    unrelated_user = create_user(
        "api-private-unrelated"
    )

    _outbox, inbox_item = (
        create_sent_in_app_notification(
            owner,
            "api-private-item",
        )
    )

    client = authenticated_client(unrelated_user)

    response = client.post(
        reverse(
            "notifications:mark-read",
            kwargs={
                "notification_id": inbox_item.pk,
            },
        ),
        {},
        format="json",
    )

    assert (
        response.status_code
        == status.HTTP_404_NOT_FOUND
    )

    inbox_item.refresh_from_db()
    assert inbox_item.read_at is None


def test_mark_all_read_only_updates_current_users_items():
    user = create_user("api-mark-all-user")
    unrelated_user = create_user(
        "api-mark-all-unrelated"
    )

    _first_outbox, first_item = (
        create_sent_in_app_notification(
            user,
            "api-mark-all-first",
        )
    )

    _second_outbox, second_item = (
        create_sent_in_app_notification(
            user,
            "api-mark-all-second",
        )
    )

    _other_outbox, unrelated_item = (
        create_sent_in_app_notification(
            unrelated_user,
            "api-mark-all-other",
        )
    )

    client = authenticated_client(user)

    response = client.post(
        reverse("notifications:mark-all-read"),
        {},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"updated_count": 2}

    first_item.refresh_from_db()
    second_item.refresh_from_db()
    unrelated_item.refresh_from_db()

    assert first_item.read_at is not None
    assert second_item.read_at is not None
    assert unrelated_item.read_at is None

    assert (
        InAppNotification.objects
        .for_recipient(user)
        .unread()
        .count()
        == 0
    )