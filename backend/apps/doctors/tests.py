from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.clinics.models import Clinic
from apps.organizations.models import (
    Organization,
    OrganizationMembership,
)

from .models import (
    DoctorClinicAffiliation,
    DoctorProfile,
    DoctorRegistration,
)


pytestmark = pytest.mark.django_db

User = get_user_model()


def create_user(username):
    return User.objects.create_user(
        username=username,
        password="test-password",
    )


def create_organization(
    name="Healthcare Group",
    slug="healthcare-group",
    status=Organization.Status.ACTIVE,
):
    return Organization.objects.create(
        name=name,
        slug=slug,
        status=status,
    )


def create_clinic(
    organization,
    name="Central Clinic",
    slug="central-clinic",
    status=Clinic.Status.ACTIVE,
):
    return Clinic.objects.create(
        organization=organization,
        name=name,
        slug=slug,
        status=status,
        address_line_1="12 Health Road",
        locality="Salt Lake",
        district="Kolkata",
        state="West Bengal",
        postal_code="700091",
    )


def create_doctor(username="doctor-user", display_name="Dr Test"):
    user = create_user(username)

    return DoctorProfile.objects.create(
        user=user,
        display_name=display_name,
        status=DoctorProfile.Status.ACTIVE,
    )


def create_verified_registration(
    doctor,
    verifier,
    registration_number="REG-1001",
):
    return DoctorRegistration.objects.create(
        doctor=doctor,
        council_name="Test Medical Council",
        registration_number=registration_number,
        registered_name=doctor.display_name,
        verification_status=(
            DoctorRegistration.VerificationStatus.VERIFIED
        ),
        verified_at=timezone.now(),
        verified_by=verifier,
    )


def test_user_can_have_only_one_doctor_profile():
    user = create_user("single-profile-doctor")

    DoctorProfile.objects.create(
        user=user,
        display_name="Dr First Profile",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DoctorProfile.objects.create(
                user=user,
                display_name="Dr Duplicate Profile",
            )


def test_verified_registration_requires_audit_information():
    doctor = create_doctor()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DoctorRegistration.objects.create(
                doctor=doctor,
                council_name="Test Medical Council",
                registration_number="REG-2001",
                registered_name=doctor.display_name,
                verification_status=(
                    DoctorRegistration
                    .VerificationStatus
                    .VERIFIED
                ),
            )


def test_registration_number_is_unique_per_council():
    first_doctor = create_doctor(
        username="first-doctor",
        display_name="Dr First",
    )
    second_doctor = create_doctor(
        username="second-doctor",
        display_name="Dr Second",
    )

    DoctorRegistration.objects.create(
        doctor=first_doctor,
        council_name="Test Medical Council",
        registration_number="REG-3001",
        registered_name=first_doctor.display_name,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DoctorRegistration.objects.create(
                doctor=second_doctor,
                council_name="Test Medical Council",
                registration_number="REG-3001",
                registered_name=second_doctor.display_name,
            )


def test_active_affiliation_requires_joined_at():
    organization = create_organization()
    clinic = create_clinic(organization)
    doctor = create_doctor()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DoctorClinicAffiliation.objects.create(
                doctor=doctor,
                clinic=clinic,
                status=DoctorClinicAffiliation.Status.ACTIVE,
            )


def test_negative_consultation_fee_is_rejected():
    organization = create_organization()
    clinic = create_clinic(organization)
    doctor = create_doctor()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DoctorClinicAffiliation.objects.create(
                doctor=doctor,
                clinic=clinic,
                consultation_fee=Decimal("-1.00"),
            )


def test_public_queryset_requires_verified_available_doctor():
    verifier = create_user("registration-verifier")
    organization = create_organization()
    clinic = create_clinic(organization)

    public_doctor = create_doctor(
        username="public-doctor",
        display_name="Dr Public",
    )
    create_verified_registration(
        doctor=public_doctor,
        verifier=verifier,
    )
    DoctorClinicAffiliation.objects.create(
        doctor=public_doctor,
        clinic=clinic,
        status=DoctorClinicAffiliation.Status.ACTIVE,
        joined_at=timezone.now(),
        accepts_online_bookings=True,
    )

    unverified_doctor = create_doctor(
        username="unverified-doctor",
        display_name="Dr Unverified",
    )
    DoctorRegistration.objects.create(
        doctor=unverified_doctor,
        council_name="Test Medical Council",
        registration_number="REG-4002",
        registered_name=unverified_doctor.display_name,
    )
    DoctorClinicAffiliation.objects.create(
        doctor=unverified_doctor,
        clinic=clinic,
        status=DoctorClinicAffiliation.Status.ACTIVE,
        joined_at=timezone.now(),
    )

    assert list(DoctorProfile.objects.public()) == [
        public_doctor
    ]


def test_user_access_is_limited_to_their_organization():
    manager = create_user("clinic-manager")

    accessible_organization = create_organization()
    inaccessible_organization = create_organization(
        name="Other Healthcare Group",
        slug="other-healthcare-group",
    )

    accessible_clinic = create_clinic(
        accessible_organization,
    )
    inaccessible_clinic = create_clinic(
        inaccessible_organization,
        name="Other Clinic",
        slug="other-clinic",
    )

    OrganizationMembership.objects.create(
        organization=accessible_organization,
        user=manager,
        role=OrganizationMembership.Role.MANAGER,
        status=OrganizationMembership.Status.ACTIVE,
        joined_at=timezone.now(),
    )

    accessible_doctor = create_doctor(
        username="accessible-doctor",
        display_name="Dr Accessible",
    )
    inaccessible_doctor = create_doctor(
        username="inaccessible-doctor",
        display_name="Dr Inaccessible",
    )

    DoctorClinicAffiliation.objects.create(
        doctor=accessible_doctor,
        clinic=accessible_clinic,
    )
    DoctorClinicAffiliation.objects.create(
        doctor=inaccessible_doctor,
        clinic=inaccessible_clinic,
    )

    assert list(
        DoctorProfile.objects.accessible_to(manager)
    ) == [accessible_doctor]


def test_anonymous_user_cannot_access_doctors():
    class AnonymousUser:
        is_authenticated = False

    assert not DoctorProfile.objects.accessible_to(
        AnonymousUser()
    ).exists()