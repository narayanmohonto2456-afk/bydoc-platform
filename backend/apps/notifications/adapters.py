from dataclasses import dataclass
from typing import Protocol

from .models import NotificationOutbox


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
    Mark an in-app notification as available.

    The outbox record itself contains the notification that a
    future authenticated inbox API can display. No external
    service or network request is required.
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