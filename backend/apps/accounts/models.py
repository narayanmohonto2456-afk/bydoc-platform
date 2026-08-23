import uuid

from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models


phone_validator = RegexValidator(
    regex=r"^\+[1-9]\d{7,14}$",
    message=(
        "Enter a phone number in E.164 format, "
        "for example +919876543210."
    ),
)


class User(AbstractUser):
    """
    Platform identity for patients, caregivers, clinic staff,
    doctors, support staff and administrators.

    Authentication does not automatically grant access to a clinic
    or patient record. Authorization will be handled separately.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    email = models.EmailField(
        unique=True,
        blank=True,
        null=True,
    )

    phone_number = models.CharField(
        max_length=16,
        unique=True,
        blank=True,
        null=True,
        validators=[phone_validator],
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "accounts_user"
        ordering = ["-date_joined"]

    def __str__(self) -> str:
        return (
            self.email
            or self.phone_number
            or self.username
        )