import uuid

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower


class ApplicationStatus(models.TextChoices):
    PENDING = "pending", "Pending review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class ReviewFields(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status = models.CharField(max_length=10, choices=ApplicationStatus.choices, default=ApplicationStatus.PENDING)
    attested_at = models.DateTimeField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="%(class)s_reviews", null=True, blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)

    class Meta:
        abstract = True


class DoctorApplication(ReviewFields):
    display_name = models.CharField(max_length=200)
    registered_name = models.CharField(max_length=200)
    council_name = models.CharField(max_length=200)
    registration_number = models.CharField(max_length=100)
    registration_year = models.PositiveSmallIntegerField(null=True, blank=True)
    specialty_name = models.CharField(max_length=120, blank=True)
    profile = models.OneToOneField(
        "doctors.DoctorProfile", on_delete=models.PROTECT, null=True, blank=True,
        related_name="onboarding_application",
    )

    class Meta:
        ordering = ("-submitted_at",)
        constraints = [models.UniqueConstraint(  # noqa: RUF012 - Django model metadata
            fields=("applicant",), condition=Q(status="pending"),
            name="one_pending_doctor_application",
        ), models.UniqueConstraint(
            Lower("council_name"), Lower("registration_number"),
            condition=Q(status="pending"), name="one_pending_medical_registration",
        )]

    def __str__(self):
        return f"{self.display_name} ({self.status})"


class ClinicApplication(ReviewFields):
    clinic_name = models.CharField(max_length=200)
    manager_name = models.CharField(max_length=200)
    registration_authority = models.CharField(max_length=200)
    registration_number = models.CharField(max_length=100)
    phone_number = models.CharField(
        max_length=16,
        validators=[RegexValidator(r"^\+[1-9]\d{7,14}$", "Use a phone number such as +919876543210.")],
    )
    email = models.EmailField()
    address_line_1 = models.CharField(max_length=255)
    locality = models.CharField(max_length=120)
    district = models.CharField(max_length=120)
    state = models.CharField(max_length=120)
    postal_code = models.CharField(
        max_length=6,
        validators=[RegexValidator(r"^[1-9][0-9]{5}$", "Enter a six-digit Indian postal code.")],
    )
    clinic = models.OneToOneField(
        "clinics.Clinic", on_delete=models.PROTECT, null=True, blank=True,
        related_name="onboarding_application",
    )

    class Meta:
        ordering = ("-submitted_at",)
        constraints = [models.UniqueConstraint(  # noqa: RUF012 - Django model metadata
            fields=("applicant",), condition=Q(status="pending"),
            name="one_pending_clinic_application",
        )]

    def __str__(self):
        return f"{self.clinic_name} ({self.status})"
