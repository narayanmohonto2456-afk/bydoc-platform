import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class OrganizationQuerySet(models.QuerySet):
    def active(self):
        return self.filter(
            status=Organization.Status.ACTIVE,
        )

    def accessible_to(self, user):
        if not getattr(user, "is_authenticated", False):
            return self.none()

        return self.filter(
            memberships__user=user,
            memberships__status=(
                OrganizationMembership.Status.ACTIVE
            ),
        ).distinct()


class Organization(models.Model):
    class Type(models.TextChoices):
        INDEPENDENT_CLINIC = (
            "independent_clinic",
            "Independent clinic",
        )
        CLINIC_GROUP = "clinic_group", "Clinic group"
        NGO = "ngo", "NGO"
        INSTITUTION = "institution", "Institution"

    class Status(models.TextChoices):
        ONBOARDING = "onboarding", "Onboarding"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(
        max_length=200,
    )

    slug = models.SlugField(
        max_length=120,
        unique=True,
    )

    organization_type = models.CharField(
        max_length=30,
        choices=Type.choices,
        default=Type.INDEPENDENT_CLINIC,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ONBOARDING,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    objects = OrganizationQuerySet.as_manager()

    class Meta:
        db_table = "organizations_organization"
        ordering = ["name"]

        constraints = [
            models.CheckConstraint(
                condition=Q(
                    organization_type__in=[
                        "independent_clinic",
                        "clinic_group",
                        "ngo",
                        "institution",
                    ]
                ),
                name="organization_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "onboarding",
                        "active",
                        "suspended",
                        "closed",
                    ]
                ),
                name="organization_status_valid",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class OrganizationMembershipQuerySet(models.QuerySet):
    def active(self):
        return self.filter(
            status=OrganizationMembership.Status.ACTIVE,
        )

    def for_user(self, user):
        if not getattr(user, "is_authenticated", False):
            return self.none()

        return self.filter(user=user)


class OrganizationMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MANAGER = "manager", "Manager"
        RECEPTIONIST = "receptionist", "Receptionist"

    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        REVOKED = "revoked", "Revoked"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="memberships",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organization_memberships",
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.INVITED,
    )

    joined_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organization_invitations_created",
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    objects = OrganizationMembershipQuerySet.as_manager()

    class Meta:
        db_table = "organizations_membership"
        ordering = ["organization__name", "user__username"]

        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"],
                name="unique_organization_user_membership",
            ),
            models.CheckConstraint(
                condition=Q(
                    role__in=[
                        "owner",
                        "manager",
                        "receptionist",
                    ]
                ),
                name="organization_membership_role_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "invited",
                        "active",
                        "suspended",
                        "revoked",
                    ]
                ),
                name="organization_membership_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(status="active")
                    | Q(joined_at__isnull=False)
                ),
                name="active_membership_requires_joined_at",
            ),
        ]

        indexes = [
            models.Index(
                fields=["organization", "status"],
                name="org_membership_status_idx",
            ),
            models.Index(
                fields=["user", "status"],
                name="user_membership_status_idx",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.user} — "
            f"{self.organization} ({self.role})"
        )

class ClinicStaffAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    membership = models.ForeignKey(
        OrganizationMembership, on_delete=models.PROTECT, related_name="clinic_assignments",
    )
    clinic = models.ForeignKey(
        "clinics.Clinic", on_delete=models.PROTECT, related_name="staff_assignments",
    )
    is_active = models.BooleanField(default=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        null=True, blank=True, related_name="clinic_assignments_made",
    )
    reason = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "organizations_clinic_staff_assignment"
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "clinic"], name="unique_membership_clinic_assignment",
            ),
        ]
        indexes = [
            models.Index(fields=["clinic", "is_active"], name="clinic_staff_active_idx"),
        ]

    def clean(self):
        if self.membership_id and self.clinic_id:
            if self.membership.organization_id != self.clinic.organization_id:
                raise ValidationError("The clinic must belong to the membership organization.")
            if self.membership.role != OrganizationMembership.Role.RECEPTIONIST:
                raise ValidationError("Only receptionist memberships need clinic assignments.")
