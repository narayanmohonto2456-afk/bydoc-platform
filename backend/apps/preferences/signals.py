from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserPreference


@receiver(
    post_save,
    sender=settings.AUTH_USER_MODEL,
    dispatch_uid="preferences_create_user_preference",
)
def create_user_preference(
    sender,
    instance,
    created,
    raw=False,
    **kwargs,
):
    """
    Create one default preference record for each new user.

    Existing preferences are never overwritten when a user account is
    updated.
    """
    if raw or not created:
        return

    UserPreference.objects.get_or_create(
        user=instance,
    )