import uuid

from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
    RegexValidator,
)
from django.db import models
from django.db.models import Q

from apps.organizations.models import (
    Organization,
    OrganizationMembership,
)


phone_validator = RegexValidator(
    regex=r"^\+[1-9]\d{7,14}$",
    message="Enter a valid phone number in E.164 format.",
)

indian_postal_code_validator = RegexValidator(
    regex=r"^[1-9][0-9]{5}$",
    message="Enter a valid six-digit Indian postal code.",
)


class ClinicQuerySet(models.QuerySet):
    def active(self):
        return self.filter(
            status=Clinic.Status.ACTIVE,
            organization__status=Organization.Status.ACTIVE,
        )

    def for_organization(self, organization):
        return self.filter(organization=organization)

    def accessible_to(self, user):
        if not getattr(user, "is_authenticated", False):
            return self.none()

        return self.filter(
            organization__memberships__user=user,
            organization__memberships__status=(
                OrganizationMembership.Status.ACTIVE
            ),
        ).distinct()


class Clinic(models.Model):
    class Status(models.TextChoices):
        ONBOARDING = "onboarding", "Onboarding"
        ACTIVE = "active", "Active"
        TEMPORARILY_CLOSED = (
            "temporarily_closed",
            "Temporarily closed",
        )
        SUSPENDED = "suspended", "Suspended"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="clinics",
    )

    name = models.CharField(
        max_length=200,
    )

    slug = models.SlugField(
        max_length=120,
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.ONBOARDING,
    )

    phone_number = models.CharField(
        max_length=16,
        validators=[phone_validator],
        blank=True,
    )

    email = models.EmailField(
        blank=True,
    )

    address_line_1 = models.CharField(
        max_length=255,
    )

    address_line_2 = models.CharField(
        max_length=255,
        blank=True,
    )

    locality = models.CharField(
        max_length=120,
    )

    district = models.CharField(
        max_length=120,
    )

    state = models.CharField(
        max_length=120,
    )

    postal_code = models.CharField(
        max_length=6,
        validators=[indian_postal_code_validator],
    )

    country_code = models.CharField(
        max_length=2,
        default="IN",
    )

    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[
            MinValueValidator(-90),
            MaxValueValidator(90),
        ],
        blank=True,
        null=True,
    )

    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[
            MinValueValidator(-180),
            MaxValueValidator(180),
        ],
        blank=True,
        null=True,
    )

    timezone = models.CharField(
        max_length=50,
        default="Asia/Kolkata",
    )

    wheelchair_accessible = models.BooleanField(
        default=False,
    )

    has_accessible_restroom = models.BooleanField(
        default=False,
    )

    has_waiting_area = models.BooleanField(
        default=False,
    )

    accepts_walk_ins = models.BooleanField(
        default=False,
    )

    schedule_updated_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    objects = ClinicQuerySet.as_manager()

    class Meta:
        db_table = "clinics_clinic"
        ordering = ["name"]

        constraints = [
            models.UniqueConstraint(
                fields=["organization", "slug"],
                name="unique_clinic_slug_per_org",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "onboarding",
                        "active",
                        "temporarily_closed",
                        "suspended",
                        "closed",
                    ]
                ),
                name="clinic_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(latitude__isnull=True)
                    | Q(latitude__gte=-90, latitude__lte=90)
                ),
                name="clinic_latitude_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(longitude__isnull=True)
                    | Q(longitude__gte=-180, longitude__lte=180)
                ),
                name="clinic_longitude_valid",
            ),
        ]

        indexes = [
            models.Index(
                fields=["organization", "status"],
                name="clinic_org_status_idx",
            ),
            models.Index(
                fields=["state", "district", "status"],
                name="clinic_location_idx",
            ),
            models.Index(
                fields=["status", "schedule_updated_at"],
                name="clinic_schedule_idx",
            ),
        ]

    def __str__(self) -> str:
        return self.name
