from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from apps.organizations.models import (
    Organization,
    OrganizationMembership,
)

from .models import Clinic


pytestmark = pytest.mark.django_db

User = get_user_model()


def create_organization(
    name="Care Clinic Group",
    slug="care-clinic-group",
    status=Organization.Status.ACTIVE,
):
    return Organization.objects.create(
        name=name,
        slug=slug,
        status=status,
    )


def create_clinic(
    organization,
    name="Care Clinic",
    slug="care-clinic",
    status=Clinic.Status.ACTIVE,
    **kwargs,
):
    defaults = {
        "address_line_1": "12 Health Road",
        "locality": "Salt Lake",
        "district": "Kolkata",
        "state": "West Bengal",
        "postal_code": "700091",
    }
    defaults.update(kwargs)

    return Clinic.objects.create(
        organization=organization,
        name=name,
        slug=slug,
        status=status,
        **defaults,
    )


def test_user_only_accesses_clinics_in_their_organization():
    user = User.objects.create_user(
        username="clinic-manager",
        password="test-password",
    )

    accessible_organization = create_organization()
    inaccessible_organization = create_organization(
        name="Other Group",
        slug="other-group",
    )

    OrganizationMembership.objects.create(
        organization=accessible_organization,
        user=user,
        role=OrganizationMembership.Role.MANAGER,
        status=OrganizationMembership.Status.ACTIVE,
        joined_at=timezone.now(),
    )

    accessible_clinic = create_clinic(
        organization=accessible_organization,
    )
    create_clinic(
        organization=inaccessible_organization,
        name="Other Clinic",
        slug="other-clinic",
    )

    result = Clinic.objects.accessible_to(user)

    assert list(result) == [accessible_clinic]


def test_anonymous_user_cannot_access_clinics():
    class AnonymousUser:
        is_authenticated = False

    organization = create_organization()
    create_clinic(organization=organization)

    result = Clinic.objects.accessible_to(AnonymousUser())

    assert not result.exists()


def test_active_queryset_requires_active_clinic_and_organization():
    active_organization = create_organization()
    suspended_organization = create_organization(
        name="Suspended Group",
        slug="suspended-group",
        status=Organization.Status.SUSPENDED,
    )

    active_clinic = create_clinic(
        organization=active_organization,
    )

    create_clinic(
        organization=active_organization,
        name="Closed Clinic",
        slug="closed-clinic",
        status=Clinic.Status.CLOSED,
    )

    create_clinic(
        organization=suspended_organization,
        name="Unavailable Clinic",
        slug="unavailable-clinic",
    )

    assert list(Clinic.objects.active()) == [active_clinic]


def test_clinic_slug_must_be_unique_within_organization():
    organization = create_organization()
    create_clinic(
        organization=organization,
        slug="central-clinic",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create_clinic(
                organization=organization,
                name="Duplicate Clinic",
                slug="central-clinic",
            )


def test_same_clinic_slug_is_allowed_in_different_organizations():
    first_organization = create_organization()
    second_organization = create_organization(
        name="Second Group",
        slug="second-group",
    )

    create_clinic(
        organization=first_organization,
        slug="central-clinic",
    )

    second_clinic = create_clinic(
        organization=second_organization,
        name="Second Central Clinic",
        slug="central-clinic",
    )

    assert second_clinic.pk is not None


def test_invalid_coordinates_are_rejected():
    organization = create_organization()

    clinic = Clinic(
        organization=organization,
        name="Invalid Location Clinic",
        slug="invalid-location",
        status=Clinic.Status.ACTIVE,
        address_line_1="10 Health Road",
        locality="Kolkata",
        district="Kolkata",
        state="West Bengal",
        postal_code="700001",
        latitude=Decimal("91.000000"),
        longitude=Decimal("181.000000"),
    )

    with pytest.raises(ValidationError) as error:
        clinic.full_clean()

    assert "latitude" in error.value.message_dict
    assert "longitude" in error.value.message_dict


def test_organization_with_clinic_cannot_be_deleted():
    organization = create_organization()
    create_clinic(organization=organization)

    with pytest.raises(ProtectedError):
        organization.delete()