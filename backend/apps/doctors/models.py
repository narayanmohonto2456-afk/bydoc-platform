


import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.clinics.models import Clinic
from apps.organizations.models import Organization, OrganizationMembership


class Specialty(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "doctors_specialty"
        ordering = ["name"]
        verbose_name_plural = "specialties"

    def __str__(self) -> str:
        return self.name


class Language(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(
        max_length=10,
        unique=True,
        help_text="Language code such as en, hi or bn.",
    )
    name = models.CharField(max_length=80, unique=True)
    native_name = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "doctors_language"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.native_name or self.name


class DoctorProfileQuerySet(models.QuerySet):
    def public(self):
        return self.filter(
            status=DoctorProfile.Status.ACTIVE,
            registrations__verification_status=(
                DoctorRegistration.VerificationStatus.VERIFIED
            ),
            clinic_affiliations__status=DoctorClinicAffiliation.Status.ACTIVE,
            clinic_affiliations__clinic__status=Clinic.Status.ACTIVE,
            clinic_affiliations__clinic__organization__status=(
                Organization.Status.ACTIVE
            ),
        ).distinct()

    def accessible_to(self, user):
        if not getattr(user, "is_authenticated", False):
            return self.none()
        return self.filter(
            clinic_affiliations__clinic__organization__memberships__user=user,
            clinic_affiliations__clinic__organization__memberships__status=(
                OrganizationMembership.Status.ACTIVE
            ),
        ).distinct()


class DoctorProfile(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        SUSPENDED = "suspended", "Suspended"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="doctor_profile",
    )
    display_name = models.CharField(max_length=200)
    professional_summary = models.TextField(blank=True)
    experience_start_year = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1900), MaxValueValidator(2100)],
        blank=True,
        null=True,
    )
    primary_specialty = models.ForeignKey(
        Specialty,
        on_delete=models.SET_NULL,
        related_name="primary_doctors",
        blank=True,
        null=True,
    )
    specialties = models.ManyToManyField(
        Specialty,
        related_name="doctor_profiles",
        blank=True,
    )
    languages = models.ManyToManyField(
        Language,
        related_name="doctor_profiles",
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = DoctorProfileQuerySet.as_manager()

    class Meta:
        db_table = "doctors_profile"
        ordering = ["display_name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["draft", "active", "inactive", "suspended"]),
                name="doctor_profile_status_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "display_name"],
                name="doctor_status_name_idx",
            ),
        ]

    def __str__(self) -> str:
        return self.display_name


class DoctorRegistration(models.Model):
    class VerificationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"
        REVOKED = "revoked", "Revoked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doctor = models.ForeignKey(
        DoctorProfile,
        on_delete=models.PROTECT,
        related_name="registrations",
    )
    council_name = models.CharField(max_length=200)
    registration_number = models.CharField(max_length=100)
    registered_name = models.CharField(max_length=200)
    registration_year = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1900), MaxValueValidator(2100)],
        blank=True,
        null=True,
    )
    valid_until = models.DateField(blank=True, null=True)
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )
    verified_at = models.DateTimeField(blank=True, null=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="doctor_registrations_verified",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "doctors_registration"
        ordering = ["council_name", "registration_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["council_name", "registration_number"],
                name="unique_council_registration",
            ),
            models.CheckConstraint(
                condition=Q(
                    verification_status__in=[
                        "pending", "verified", "rejected", "expired", "revoked"
                    ]
                ),
                name="doctor_reg_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(verification_status="verified")
                    | (Q(verified_at__isnull=False) & Q(verified_by__isnull=False))
                ),
                name="verified_reg_requires_audit",
            ),
        ]
        indexes = [
            models.Index(
                fields=["verification_status", "registration_number"],
                name="doctor_reg_verify_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.council_name} - {self.registration_number}"


class DoctorQualification(models.Model):
    class VerificationStatus(models.TextChoices):
        UNVERIFIED = "unverified", "Unverified"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doctor = models.ForeignKey(
        DoctorProfile,
        on_delete=models.PROTECT,
        related_name="qualifications",
    )
    degree_name = models.CharField(max_length=200)
    institution_name = models.CharField(max_length=250)
    awarding_body = models.CharField(max_length=250, blank=True)
    completion_year = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1900), MaxValueValidator(2100)],
        blank=True,
        null=True,
    )
    country_code = models.CharField(max_length=2, default="IN")
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNVERIFIED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "doctors_qualification"
        ordering = ["-completion_year", "degree_name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    verification_status__in=["unverified", "verified", "rejected"]
                ),
                name="doctor_qual_status_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.degree_name} - {self.institution_name}"


class DoctorClinicAffiliation(models.Model):
    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        ENDED = "ended", "Ended"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doctor = models.ForeignKey(
        DoctorProfile,
        on_delete=models.PROTECT,
        related_name="clinic_affiliations",
    )
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="doctor_affiliations",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.INVITED,
    )
    consultation_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )
    currency_code = models.CharField(max_length=3, default="INR")
    appointment_duration_minutes = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(5), MaxValueValidator(240)],
        default=15,
    )
    accepts_online_bookings = models.BooleanField(default=False)
    joined_at = models.DateTimeField(blank=True, null=True)
    ended_at = models.DateTimeField(blank=True, null=True)
    fee_updated_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "doctors_clinic_affiliation"
        ordering = ["clinic__name", "doctor__display_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["doctor", "clinic"],
                name="unique_doctor_clinic",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["invited", "active", "suspended", "ended"]),
                name="doctor_affiliation_status_valid",
            ),
            models.CheckConstraint(
                condition=(~Q(status="active") | Q(joined_at__isnull=False)),
                name="active_affiliation_joined",
            ),
            models.CheckConstraint(
                condition=(
                    Q(consultation_fee__isnull=True)
                    | Q(consultation_fee__gte=0)
                ),
                name="doctor_fee_nonnegative",
            ),
        ]
        indexes = [
            models.Index(
                fields=["clinic", "status"],
                name="clinic_doctor_status_idx",
            ),
            models.Index(
                fields=["doctor", "status"],
                name="doctor_clinic_status_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.doctor} - {self.clinic}"