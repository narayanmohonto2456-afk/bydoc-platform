import uuid

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import User, VerifiedEmail
from apps.clinics.models import Clinic
from apps.doctors.models import DoctorProfile, DoctorRegistration
from apps.organizations.models import Organization, OrganizationMembership

from .models import ApplicationStatus, ClinicApplication, DoctorApplication


class ApplicationError(Exception):
    pass


def has_verified_email(user):
    return bool(user.email) and VerifiedEmail.objects.filter(
        user=user, address__iexact=user.email
    ).exists()


def require_verified_email(user):
    if not has_verified_email(user):
        raise ApplicationError("Verify your account email before applying.")


@transaction.atomic
def submit_doctor(user, details):
    User.objects.select_for_update().get(pk=user.pk)
    require_verified_email(user)
    if DoctorProfile.objects.filter(user=user).exists():
        raise ApplicationError("This account already has a doctor profile.")
    if DoctorApplication.objects.filter(applicant=user, status=ApplicationStatus.PENDING).exists():
        raise ApplicationError("Your doctor application is already awaiting review.")
    council = details["council_name"].strip()
    number = details["registration_number"].strip().upper()
    if DoctorRegistration.objects.filter(
        council_name__iexact=council, registration_number__iexact=number
    ).exists() or DoctorApplication.objects.filter(
        council_name__iexact=council, registration_number__iexact=number,
        status=ApplicationStatus.PENDING,
    ).exists():
        raise ApplicationError("This registration is already under review or registered. Contact support if it is yours.")
    return DoctorApplication.objects.create(
        applicant=user, attested_at=timezone.now(),
        **{**details, "council_name": council, "registration_number": number},
    )


@transaction.atomic
def submit_clinic(user, details):
    User.objects.select_for_update().get(pk=user.pk)
    require_verified_email(user)
    if ClinicApplication.objects.filter(applicant=user, status=ApplicationStatus.PENDING).exists():
        raise ApplicationError("Your clinic application is already awaiting review.")
    return ClinicApplication.objects.create(
        applicant=user, attested_at=timezone.now(),
        **{**details, "registration_number": details["registration_number"].strip().upper()},
    )


def require_reviewer(application, reviewer, note):
    from apps.operations.models import StaffGrant
    from apps.operations.permissions import has_role

    if not has_role(reviewer, StaffGrant.Role.PROVIDER) or reviewer.pk == application.applicant_id:
        raise ApplicationError("An independent platform administrator must review this application.")
    if application.status != ApplicationStatus.PENDING:
        raise ApplicationError("This application has already been reviewed.")
    if not note.strip():
        raise ApplicationError("Record the evidence checked and the reason for this decision.")


@transaction.atomic
def review_doctor(application_id, reviewer, approve, note):
    application = DoctorApplication.objects.select_for_update().select_related("applicant").get(pk=application_id)
    require_reviewer(application, reviewer, note)
    if approve:
        require_verified_email(application.applicant)
        if DoctorProfile.objects.filter(user=application.applicant).exists():
            raise ApplicationError("This account already has a doctor profile.")
        if DoctorRegistration.objects.filter(
            council_name__iexact=application.council_name,
            registration_number__iexact=application.registration_number,
        ).exists():
            raise ApplicationError("This registration already belongs to a doctor.")
        profile = DoctorProfile.objects.create(
            user=application.applicant,
            display_name=application.display_name,
            status=DoctorProfile.Status.ACTIVE,
        )
        DoctorRegistration.objects.create(
            doctor=profile,
            council_name=application.council_name,
            registration_number=application.registration_number,
            registered_name=application.registered_name,
            registration_year=application.registration_year,
            verification_status=DoctorRegistration.VerificationStatus.VERIFIED,
            verified_at=timezone.now(),
            verified_by=reviewer,
        )
        application.profile = profile
    application.status = ApplicationStatus.APPROVED if approve else ApplicationStatus.REJECTED
    application.reviewed_by = reviewer
    application.reviewed_at = timezone.now()
    application.review_note = note.strip()
    application.save()
    return application


@transaction.atomic
def review_clinic(application_id, reviewer, approve, note):
    application = ClinicApplication.objects.select_for_update().select_related("applicant").get(pk=application_id)
    require_reviewer(application, reviewer, note)
    if approve:
        require_verified_email(application.applicant)
        if Clinic.objects.filter(
            name__iexact=application.clinic_name, postal_code=application.postal_code,
        ).exists():
            raise ApplicationError("A clinic with this name and postal code exists. Review for a duplicate or claim.")
        slug = (slugify(application.clinic_name)[:75] or "clinic") + "-" + uuid.uuid4().hex
        organization = Organization.objects.create(
            name=application.clinic_name,
            slug=slug,
            organization_type=Organization.Type.INDEPENDENT_CLINIC,
            status=Organization.Status.ACTIVE,
        )
        clinic = Clinic.objects.create(
            organization=organization,
            name=application.clinic_name,
            slug=slug[:120],
            status=Clinic.Status.ACTIVE,
            phone_number=application.phone_number,
            email=application.email,
            address_line_1=application.address_line_1,
            locality=application.locality,
            district=application.district,
            state=application.state,
            postal_code=application.postal_code,
        )
        OrganizationMembership.objects.create(
            organization=organization,
            user=application.applicant,
            role=OrganizationMembership.Role.OWNER,
            status=OrganizationMembership.Status.ACTIVE,
            joined_at=timezone.now(),
        )
        application.clinic = clinic
    application.status = ApplicationStatus.APPROVED if approve else ApplicationStatus.REJECTED
    application.reviewed_by = reviewer
    application.reviewed_at = timezone.now()
    application.review_note = note.strip()
    application.save()
    return application
