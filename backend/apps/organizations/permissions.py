from django.db.models import F, Q

from apps.clinics.models import Clinic

from .models import ClinicStaffAssignment, Organization, OrganizationMembership


VISIBLE_CLINIC_STATUSES = (
    Clinic.Status.ACTIVE,
    Clinic.Status.ONBOARDING,
    Clinic.Status.TEMPORARILY_CLOSED,
)


def accessible_clinics(user):
    if not getattr(user, "is_authenticated", False):
        return Clinic.objects.none()

    active_memberships = OrganizationMembership.objects.active().filter(
        user=user,
        organization__status__in=(Organization.Status.ACTIVE, Organization.Status.ONBOARDING),
    )
    managed_organizations = active_memberships.filter(
        role__in=(OrganizationMembership.Role.OWNER, OrganizationMembership.Role.MANAGER),
    ).values("organization_id")
    receptionist_clinics = ClinicStaffAssignment.objects.filter(
        membership__in=active_memberships.filter(role=OrganizationMembership.Role.RECEPTIONIST),
        is_active=True,
        clinic__organization_id=F("membership__organization_id"),
    ).values("clinic_id")
    return Clinic.objects.filter(
        Q(organization_id__in=managed_organizations) | Q(id__in=receptionist_clinics),
        status__in=VISIBLE_CLINIC_STATUSES,
    ).distinct().order_by("name", "id")


def can_access_clinic(user, clinic_id):
    return accessible_clinics(user).filter(pk=clinic_id).exists()
