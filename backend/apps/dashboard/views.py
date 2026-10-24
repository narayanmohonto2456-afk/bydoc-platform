"""Read-only dashboard summaries with server-side role and object checks."""

from datetime import datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions
from rest_framework.exceptions import (
    APIException,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.appointments.models import Appointment
from apps.clinics.models import Clinic
from apps.doctors.models import DoctorProfile, DoctorRegistration
from apps.onboarding.models import ClinicApplication, DoctorApplication
from apps.organizations.models import Organization, OrganizationMembership
from apps.organizations.permissions import accessible_clinics
from apps.support.models import SupportCase

from .serializers import (
    AdminDashboardSerializer,
    ClinicDashboardSerializer,
    DashboardRolesSerializer,
    DoctorDashboardSerializer,
    PatientDashboardSerializer,
)


def active_memberships(user):
    return OrganizationMembership.objects.active().filter(
        user=user,
        organization__status__in=[Organization.Status.ACTIVE, Organization.Status.ONBOARDING],
    )


def clinic_memberships(user):
    return list(active_memberships(user))


def available_roles(user):
    roles = ["patient"]
    if DoctorProfile.objects.filter(user=user).exists():
        roles.append("doctor")
    if accessible_clinics(user).exists():
        roles.append("clinic")
    from apps.operations.permissions import has_any_role
    if has_any_role(user):
        roles.append("admin")
    return roles


def appointment_card(appointment):
    affiliation = appointment.slot.affiliation
    return {
        "id": appointment.id,
        "booking_reference": appointment.booking_reference,
        "starts_at": appointment.slot.starts_at,
        "status": appointment.status,
        "doctor_name": affiliation.doctor.display_name,
        "clinic_name": affiliation.clinic.name,
    }


class DashboardView(APIView):
    permission_classes = (permissions.IsAuthenticated,)


class RolesView(DashboardView):
    @extend_schema(responses={200: DashboardRolesSerializer})
    def get(self, request):
        roles = available_roles(request.user)
        preferred = next(role for role in ("admin", "clinic", "doctor", "patient") if role in roles)
        return Response({"roles": roles, "preferred": preferred})


class PatientDashboardView(DashboardView):
    @extend_schema(responses={200: PatientDashboardSerializer})
    def get(self, request):
        now = timezone.now()
        appointments = Appointment.objects.filter(patient=request.user)
        upcoming = appointments.filter(
            slot__starts_at__gte=now,
            status__in=[Appointment.Status.CONFIRMED, Appointment.Status.CHECKED_IN],
        )
        next_visit = upcoming.select_related(
            "slot__affiliation__doctor", "slot__affiliation__clinic",
        ).order_by("slot__starts_at").first()
        other_appointments = appointments.exclude(pk=next_visit.pk) if next_visit else appointments
        recent = other_appointments.select_related(
            "slot__affiliation__doctor", "slot__affiliation__clinic",
        ).order_by("-slot__starts_at")[:6]
        return Response({
            "upcoming_count": upcoming.count(),
            "open_support_count": SupportCase.objects.filter(requester=request.user).exclude(
                status__in=[SupportCase.Status.RESOLVED, SupportCase.Status.CLOSED],
            ).count(),
            "next_appointment": appointment_card(next_visit) if next_visit else None,
            "appointments": [appointment_card(item) for item in recent],
            "updated_at": now,
        })


class DoctorDashboardView(DashboardView):
    @extend_schema(responses={200: DoctorDashboardSerializer})
    def get(self, request):
        profile = DoctorProfile.objects.filter(user=request.user).first()
        if profile is None:
            raise PermissionDenied("A doctor profile is required.")
        now = timezone.now()
        affiliations = list(profile.clinic_affiliations.select_related("clinic").order_by("clinic__name"))
        registration = profile.registrations.order_by("-updated_at").first()
        return Response({
            "display_name": profile.display_name,
            "profile_status": profile.status,
            "registration_status": registration.verification_status if registration else "not_submitted",
            "upcoming_appointments_count": Appointment.objects.filter(
                slot__affiliation__doctor=profile,
                slot__starts_at__gte=now,
                status__in=[Appointment.Status.CONFIRMED, Appointment.Status.CHECKED_IN],
            ).count(),
            "affiliations": [{
                "clinic_name": item.clinic.name,
                "status": item.status,
                "accepts_online_bookings": item.accepts_online_bookings,
            } for item in affiliations],
            "updated_at": now,
        })


class ClinicDashboardView(DashboardView):
    @extend_schema(
        parameters=[OpenApiParameter("clinic_id", UUID, required=False)],
        responses={200: ClinicDashboardSerializer},
    )
    def get(self, request):
        membership_list = clinic_memberships(request.user)
        memberships = {item.organization_id: item.role for item in membership_list}
        clinics = list(accessible_clinics(request.user))
        if not clinics:
            raise PermissionDenied("An active clinic membership is required.")
        requested_id = request.query_params.get("clinic_id")
        if requested_id:
            try:
                selected_id = UUID(requested_id)
            except (ValueError, TypeError, AttributeError) as error:
                raise ValidationError({"clinic_id": "Enter a valid clinic ID."}) from error
            clinic = next((item for item in clinics if item.id == selected_id), None)
            if clinic is None:
                raise NotFound("Clinic not found.")
        else:
            clinic = clinics[0]
        try:
            clinic_timezone = ZoneInfo(clinic.timezone)
        except ZoneInfoNotFoundError as error:
            raise APIException("The clinic timezone is not configured correctly.") from error
        now = timezone.now()
        local_day = timezone.localdate(now, timezone=clinic_timezone)
        start = datetime.combine(local_day, time.min, tzinfo=clinic_timezone)
        end = start + timedelta(days=1)
        appointments = Appointment.objects.filter(
            slot__affiliation__clinic=clinic,
            slot__starts_at__gte=start,
            slot__starts_at__lt=end,
        )
        rows = appointments.select_related(
            "slot__affiliation__doctor", "slot__affiliation__clinic", "patient",
        ).order_by("slot__starts_at")[:20]
        return Response({
            "clinics": [{
                "id": item.id,
                "name": item.name,
                "status": item.status,
                "role": memberships[item.organization_id],
            } for item in clinics],
            "selected_clinic_id": clinic.id,
            "local_date": local_day,
            "timezone": clinic.timezone,
            "today_count": appointments.count(),
            "confirmed_count": appointments.filter(status=Appointment.Status.CONFIRMED).count(),
            "checked_in_count": appointments.filter(status=Appointment.Status.CHECKED_IN).count(),
            "completed_count": appointments.filter(status=Appointment.Status.COMPLETED).count(),
            "cancelled_count": appointments.filter(status=Appointment.Status.CANCELLED).count(),
            "no_show_count": appointments.filter(status=Appointment.Status.NO_SHOW).count(),
            "appointments": [{
                **appointment_card(item),
                "patient_name": item.patient.get_full_name() or item.patient.username,
            } for item in rows],
            "updated_at": now,
        })


class AdminDashboardView(DashboardView):
    @extend_schema(responses={200: AdminDashboardSerializer})
    def get(self, request):
        from apps.operations.permissions import has_any_role
        if not has_any_role(request.user):
            raise PermissionDenied("Platform administrator access is required.")
        return Response({
            "account_count": User.objects.count(),
            "doctor_count": DoctorProfile.objects.count(),
            "clinic_count": Clinic.objects.count(),
            "pending_registrations_count": DoctorRegistration.objects.filter(
                verification_status=DoctorRegistration.VerificationStatus.PENDING,
            ).count() + DoctorApplication.objects.filter(status="pending").count()
            + ClinicApplication.objects.filter(status="pending").count(),
            "open_support_count": SupportCase.objects.exclude(
                status__in=[SupportCase.Status.RESOLVED, SupportCase.Status.CLOSED],
            ).count(),
            "updated_at": timezone.now(),
        })
