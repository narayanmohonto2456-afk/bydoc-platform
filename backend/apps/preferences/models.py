import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class UserPreference(models.Model):
    """
    Non-clinical interface and accessibility preferences.

    These settings affect only presentation and data usage. They must
    never contain medical, diagnosis or appointment information.
    """

    class Language(models.TextChoices):
        ENGLISH = "en", "English"
        BENGALI = "bn", "বাংলা"
        HINDI = "hi", "हिन्दी"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="preferences",
    )

    preferred_language = models.CharField(
        max_length=10,
        choices=Language.choices,
        default=Language.ENGLISH,
    )

    low_data_mode = models.BooleanField(
        default=False,
        help_text=(
            "Reduce non-essential images, animation and background "
            "network activity."
        ),
    )

    large_text = models.BooleanField(
        default=False,
        help_text=(
            "Request larger text in supported user interfaces."
        ),
    )

    high_contrast = models.BooleanField(
        default=False,
        help_text=(
            "Request a higher-contrast interface theme."
        ),
    )

    reduce_motion = models.BooleanField(
        default=False,
        help_text=(
            "Reduce non-essential animation and movement."
        ),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "user_preference"

        constraints = [
            models.CheckConstraint(
                condition=Q(
                    preferred_language__in=[
                        "en",
                        "bn",
                        "hi",
                    ]
                ),
                name="preference_language_valid",
            ),
        ]

        indexes = [
            models.Index(
                fields=["preferred_language"],
                name="preference_language_idx",
            ),
            models.Index(
                fields=[
                    "low_data_mode",
                    "updated_at",
                ],
                name="preference_low_data_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.user}: "
            f"{self.get_preferred_language_display()}"
        )