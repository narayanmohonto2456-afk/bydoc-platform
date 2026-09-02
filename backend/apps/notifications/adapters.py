from dataclasses import dataclass
from typing import Protocol

from .models import (
    InAppNotification,
    NotificationOutbox,
)


@dataclass(frozen=True)
class DeliveryResult:
    external_reference: str = ""


class NotificationDeliveryError(Exception):
    """
    Safe base exception for notification delivery failures.

    error_code may be stored in the database. Exception details
    and provider responses must not be persisted.
    """

    error_code = "delivery_error"


class TemporaryDeliveryError(NotificationDeliveryError):
    """A temporary error that may succeed when retried."""

    error_code = "temporary_delivery_error"


class PermanentDeliveryError(NotificationDeliveryError):
    """A permanent error that should not be retried."""

    error_code = "permanent_delivery_error"


class DeliveryConfigurationError(PermanentDeliveryError):
    """No delivery adapter is configured for the channel."""

    error_code = "delivery_not_configured"


class NotificationDeliveryAdapter(Protocol):
    name: str

    def deliver(
        self,
        notification: NotificationOutbox,
    ) -> DeliveryResult:
        ...


class InAppDeliveryAdapter:
    """
    Create a patient-visible inbox record idempotently.

    If a worker crashes after creating the inbox item but before
    marking the outbox item sent, a retry returns the same inbox
    record instead of creating a duplicate.
    """

    name = "in_app"

    def deliver(
        self,
        notification: NotificationOutbox,
    ) -> DeliveryResult:
        if (
            notification.channel
            != NotificationOutbox.Channel.IN_APP
        ):
            raise PermanentDeliveryError(
                "The in-app adapter cannot deliver this channel."
            )

        InAppNotification.objects.get_or_create(
            outbox=notification
        )

        return DeliveryResult(
            external_reference=(
                f"in-app:{notification.pk}"
            )
        )


def get_delivery_adapter(
    channel,
) -> NotificationDeliveryAdapter:
    """
    Return the configured adapter for one notification channel.

    Email, SMS and push remain disabled until credentials and an
    approved provider-specific adapter are configured.
    """
    adapters = {
        NotificationOutbox.Channel.IN_APP: (
            InAppDeliveryAdapter()
        ),
    }

    try:
        return adapters[channel]
    except KeyError as error:
        raise DeliveryConfigurationError(
            "No delivery adapter is configured for this channel."
        ) from error