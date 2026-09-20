import uuid

from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone


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
    or patient record. Authorization is handled separately.
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_user"
        ordering = ["-date_joined"]

    def save(self, *args, **kwargs):
        """Store omitted unique contacts as NULL, not empty strings."""
        if not self.email:
            self.email = None
        if not self.phone_number:
            self.phone_number = None
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.email or self.phone_number or self.username


class VerifiedEmail(models.Model):
    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE, related_name="verified_email")
    address = models.EmailField()
    verified_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(models.functions.Lower("address"), name="unique_verified_email_ci")]


class AccountRecoveryRequest(models.Model):
    class Purpose(models.TextChoices):
        VERIFY = "verify", "Verify email"
        RESET = "reset", "Reset password"

    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="recovery_requests")
    purpose = models.CharField(max_length=10, choices=Purpose.choices)
    address = models.EmailField()
    password_fingerprint = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    state = models.CharField(max_length=12, choices=State.choices, default=State.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    locked_at = models.DateTimeField(null=True, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["state", "next_attempt_at"], name="account_recovery_due_idx")]

class PatientProfile(models.Model):
    """
    Patient-owned contact and demographic information.

    This model intentionally stores no diagnosis, prescription,
    consultation note, or other clinical-record information.
    """

    class Gender(models.TextChoices):
        WOMAN = "woman", "Woman"
        MAN = "man", "Man"
        NON_BINARY = "non_binary", "Non-binary"
        PREFER_NOT_TO_SAY = (
            "prefer_not_to_say",
            "Prefer not to say",
        )

    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="patient_profile",
    )
    date_of_birth = models.DateField(
        blank=True,
        null=True,
    )
    gender = models.CharField(
        max_length=20,
        choices=Gender.choices,
        blank=True,
    )
    emergency_contact_name = models.CharField(
        max_length=150,
        blank=True,
    )
    emergency_contact_phone = models.CharField(
        max_length=16,
        blank=True,
        validators=[phone_validator],
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "accounts_patient_profile"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        emergency_contact_name="",
                        emergency_contact_phone="",
                    )
                    | (
                        models.Q(
                            emergency_contact_name__gt="",
                        )
                        & models.Q(
                            emergency_contact_phone__gt="",
                        )
                    )
                ),
                name="patient_profile_emergency_contact_complete",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.date_of_birth is not None
            and self.date_of_birth > timezone.localdate()
        ):
            raise ValidationError(
                {
                    "date_of_birth": (
                        "Date of birth cannot be in the future."
                    )
                }
            )

    def __str__(self) -> str:
        return f"Patient profile for {self.user}"
