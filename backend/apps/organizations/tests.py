import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.clinics.models import Clinic
from .models import ClinicStaffAssignment, Organization, OrganizationMembership
from .permissions import can_access_clinic


User = get_user_model()


@pytest.mark.django_db
def test_user_only_accesses_organization_with_active_membership():
    user = User.objects.create_user(
        username="clinic_manager",
    )

    allowed_organization = Organization.objects.create(
        name="Allowed Clinic",
        slug="allowed-clinic",
        status=Organization.Status.ACTIVE,
    )

    blocked_organization = Organization.objects.create(
        name="Blocked Clinic",
        slug="blocked-clinic",
        status=Organization.Status.ACTIVE,
    )

    OrganizationMembership.objects.create(
        organization=allowed_organization,
        user=user,
        role=OrganizationMembership.Role.MANAGER,
        status=OrganizationMembership.Status.ACTIVE,
        joined_at=timezone.now(),
    )

    OrganizationMembership.objects.create(
        organization=blocked_organization,
        user=user,
        role=OrganizationMembership.Role.MANAGER,
        status=OrganizationMembership.Status.INVITED,
    )

    accessible = Organization.objects.accessible_to(user)

    assert list(accessible) == [allowed_organization]
    assert blocked_organization not in accessible


@pytest.mark.django_db
def test_anonymous_user_cannot_access_organizations():
    Organization.objects.create(
        name="Private Clinic",
        slug="private-clinic",
        status=Organization.Status.ACTIVE,
    )

    accessible = Organization.objects.accessible_to(
        AnonymousUser()
    )

    assert not accessible.exists()


@pytest.mark.django_db
def test_duplicate_membership_is_rejected_by_database():
    user = User.objects.create_user(
        username="receptionist",
    )

    organization = Organization.objects.create(
        name="Shanti Clinic",
        slug="shanti-clinic",
    )

    OrganizationMembership.objects.create(
        organization=organization,
        user=user,
        role=OrganizationMembership.Role.RECEPTIONIST,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            OrganizationMembership.objects.create(
                organization=organization,
                user=user,
                role=OrganizationMembership.Role.MANAGER,
            )


@pytest.mark.django_db
def test_active_membership_requires_joined_at():
    user = User.objects.create_user(
        username="active_without_date",
    )

    organization = Organization.objects.create(
        name="Date Constraint Clinic",
        slug="date-constraint-clinic",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            OrganizationMembership.objects.create(
                organization=organization,
                user=user,
                role=OrganizationMembership.Role.MANAGER,
                status=OrganizationMembership.Status.ACTIVE,
                joined_at=None,
            )


@pytest.mark.django_db
def test_organization_with_membership_cannot_be_deleted():
    user = User.objects.create_user(
        username="protected_member",
    )

    organization = Organization.objects.create(
        name="Protected Clinic",
        slug="protected-clinic",
    )

    OrganizationMembership.objects.create(
        organization=organization,
        user=user,
        role=OrganizationMembership.Role.OWNER,
    )

    with pytest.raises(ProtectedError):
        organization.delete()

@pytest.mark.django_db
def test_cross_organization_assignment_cannot_grant_clinic_access():
    user = User.objects.create_user(username="cross-org-receptionist")
    own = Organization.objects.create(name="Own", slug="own", status=Organization.Status.ACTIVE)
    other = Organization.objects.create(name="Other", slug="other", status=Organization.Status.ACTIVE)
    membership = OrganizationMembership.objects.create(
        organization=own, user=user, role=OrganizationMembership.Role.RECEPTIONIST,
        status=OrganizationMembership.Status.ACTIVE, joined_at=timezone.now(),
    )
    foreign_clinic = Clinic.objects.create(
        organization=other, name="Foreign", slug="foreign", status=Clinic.Status.ACTIVE,
        address_line_1="1 Main Road", locality="Centre", district="Kolkata",
        state="West Bengal", postal_code="700001", timezone="UTC",
    )
    assignment = ClinicStaffAssignment(membership=membership, clinic=foreign_clinic)
    with pytest.raises(ValidationError):
        assignment.full_clean()

    # Even malformed rows inserted outside ModelForm cannot cross the permission boundary.
    ClinicStaffAssignment.objects.create(membership=membership, clinic=foreign_clinic)
    assert not can_access_clinic(user, foreign_clinic.pk)
