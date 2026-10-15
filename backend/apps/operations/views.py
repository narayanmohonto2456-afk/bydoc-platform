from datetime import timedelta
import uuid

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiTypes, extend_schema

from apps.appointments.models import Appointment
from apps.appointments.services import AppointmentBookingError
from apps.clinics.models import Clinic
from apps.doctors.models import DoctorProfile
from apps.notifications.models import NotificationOutbox
from apps.onboarding.models import ApplicationStatus, ClinicApplication, DoctorApplication
from apps.onboarding.services import ApplicationError
from apps.payments import gateway
from apps.payments.models import PaymentIntent, PaymentWebhookEvent
from apps.payments.services import PaymentError
from apps.payments.tasks import reconcile_one
from apps.support.models import SupportCase, SupportCaseEvent
from apps.support.serializers import SupportCaseListSerializer

from .models import OperationsEvent, StaffGrant, WebhookFailure
from .permissions import has_role, roles_for
from .serializers import DecisionSerializer, EscalationSerializer, GrantSerializer, InvestigationSerializer, ReasonSerializer, StatusSerializer
from .services import (
    OperationsError, cancel_for_support, change_provider_status,
    decide_application, record, retry_delivery,
    set_investigation, set_staff_grant,
)

User = get_user_model()


def failure(error):
    return Response({"detail": str(error)}, status=status.HTTP_409_CONFLICT)


def require(request, role):
    if not has_role(request.user, role):
        raise PermissionDenied("This operations role is required.")


class OperationsView(APIView):
    permission_classes = (permissions.IsAuthenticated,)


class MeView(OperationsView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        return Response({"roles": roles_for(request.user), "superuser": request.user.is_superuser})


class SummaryView(OperationsView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        roles = roles_for(request.user)
        if not roles:
            raise PermissionDenied()
        counts = {}
        if StaffGrant.Role.PROVIDER in roles:
            counts["providers"] = DoctorApplication.objects.filter(status=ApplicationStatus.PENDING).count() + ClinicApplication.objects.filter(status=ApplicationStatus.PENDING).count()
        if StaffGrant.Role.SUPPORT in roles:
            counts["support"] = SupportCase.objects.active().count()
        if StaffGrant.Role.FINANCE in roles:
            counts["payments"] = PaymentIntent.objects.filter(status__in=[PaymentIntent.Status.REVIEW, PaymentIntent.Status.REFUND_DUE, PaymentIntent.Status.REFUND_PENDING]).count()
        if StaffGrant.Role.SCHEDULE in roles:
            counts["appointments"] = Appointment.objects.filter(status=Appointment.Status.CONFIRMED, slot__starts_at__gte=timezone.now()).count()
        if StaffGrant.Role.DELIVERY in roles:
            counts["deliveries"] = NotificationOutbox.objects.filter(status=NotificationOutbox.Status.FAILED).count()
        return Response({"counts": counts, "updated_at": timezone.now()})


class ProvidersView(OperationsView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        require(request, StaffGrant.Role.PROVIDER)
        doctors = DoctorApplication.objects.select_related("applicant").order_by("-submitted_at")[:40]
        clinics = ClinicApplication.objects.select_related("applicant").order_by("-submitted_at")[:40]
        items = []
        for kind, applications in (("doctor", doctors), ("clinic", clinics)):
            for app in applications:
                row = {"id": app.id, "kind": kind, "name": app.display_name if kind == "doctor" else app.clinic_name,
                       "applicant": app.applicant.username, "status": app.status, "submitted_at": app.submitted_at,
                       "review_note": app.review_note, "reviewed_at": app.reviewed_at,
                       "registration_number": app.registration_number}
                if kind == "doctor":
                    row.update({"authority": app.council_name, "registered_name": app.registered_name})
                else:
                    row.update({"authority": app.registration_authority, "registered_name": app.manager_name,
                                "postal_code": app.postal_code, "district": app.district})
                items.append(row)
        items.sort(key=lambda item: item["submitted_at"], reverse=True)
        return Response({"results": items[:60]})


class ReviewProviderView(OperationsView):
    @extend_schema(request=DecisionSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request, kind, application_id):
        require(request, StaffGrant.Role.PROVIDER)
        data = DecisionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            application = decide_application(kind=kind, application_id=application_id, actor=request.user, **data.validated_data)
        except (DoctorApplication.DoesNotExist, ClinicApplication.DoesNotExist):
            return Response({"detail": "Application not found."}, status=404)
        except (ApplicationError, OperationsError) as error:
            return failure(error)
        return Response({"id": application.id, "status": application.status})


class ProviderStatusView(OperationsView):
    @extend_schema(request=StatusSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request, kind, provider_id):
        require(request, StaffGrant.Role.PROVIDER)
        data = StatusSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            provider = change_provider_status(kind=kind, provider_id=provider_id, actor=request.user, **data.validated_data)
        except (DoctorProfile.DoesNotExist, Clinic.DoesNotExist):
            return Response({"detail": "Provider not found."}, status=404)
        except OperationsError as error:
            return failure(error)
        return Response({"id": provider.pk, "status": provider.status})


class ActiveProvidersView(OperationsView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        require(request, StaffGrant.Role.PROVIDER)
        doctors = DoctorProfile.objects.filter(status__in=[DoctorProfile.Status.ACTIVE, DoctorProfile.Status.SUSPENDED]).order_by("-updated_at")[:40]
        clinics = Clinic.objects.filter(status__in=[Clinic.Status.ACTIVE, Clinic.Status.SUSPENDED]).order_by("-updated_at")[:40]
        items = ([{"id": item.pk, "kind": "doctor", "name": item.display_name, "status": item.status} for item in doctors]
                 + [{"id": item.pk, "kind": "clinic", "name": item.name, "status": item.status} for item in clinics])
        return Response({"results": items})


class PaymentsView(OperationsView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        require(request, StaffGrant.Role.FINANCE)
        old = timezone.now() - timedelta(hours=1)
        intents = PaymentIntent.objects.select_related("appointment", "investigation").filter(
            Q(status__in=[PaymentIntent.Status.REVIEW, PaymentIntent.Status.REFUND_DUE, PaymentIntent.Status.REFUND_PENDING])
            | Q(status=PaymentIntent.Status.PENDING, created_at__lte=old)
        ).order_by("created_at")[:100]
        results = []
        for intent in intents:
            investigation = getattr(intent, "investigation", None)
            results.append({"id": intent.pk, "booking_reference": intent.appointment.booking_reference,
                            "status": intent.status, "amount_paise": intent.amount_paise,
                            "last_error": intent.last_error, "created_at": intent.created_at,
                            "refund_requested_at": intent.refund_requested_at,
                            "investigation": None if investigation is None else {"resolved": investigation.resolved, "note": investigation.note}})
        failures = WebhookFailure.objects.filter(resolved=False).order_by("-last_seen_at")[:50]
        return Response({"results": results, "recent_webhook_count": PaymentWebhookEvent.objects.filter(received_at__gte=timezone.now() - timedelta(days=1)).count(),
                         "gateway_configured": bool(gateway.configured()),
                         "webhook_failures": [{"event_id": item.event_id, "event_type": item.event_type,
                                               "error_code": item.error_code, "failed_count": item.failed_count,
                                               "last_seen_at": item.last_seen_at} for item in failures]})


class ReconcilePaymentView(OperationsView):
    @extend_schema(request=ReasonSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request, intent_id):
        require(request, StaffGrant.Role.FINANCE)
        data = ReasonSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            intent = reconcile_one(intent_id)
        except PaymentIntent.DoesNotExist:
            return Response({"detail": "Payment not found."}, status=404)
        except (PaymentError, gateway.GatewayError, KeyError) as error:
            return failure(error)
        record(request.user, "payment.reconciled", "payment_intent", intent.pk, data.validated_data["note"], {"status": intent.status})
        return Response({"id": intent.pk, "status": intent.status})


class PaymentInvestigationView(OperationsView):
    @extend_schema(request=InvestigationSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request, intent_id):
        require(request, StaffGrant.Role.FINANCE)
        data = InvestigationSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            investigation = set_investigation(intent_id=intent_id, actor=request.user, **data.validated_data)
        except PaymentIntent.DoesNotExist:
            return Response({"detail": "Payment not found."}, status=404)
        except OperationsError as error:
            return failure(error)
        return Response({"resolved": investigation.resolved})


class SupportQueueView(OperationsView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        require(request, StaffGrant.Role.SUPPORT)
        cases = SupportCase.objects.active().select_related("assigned_to").order_by("-created_at")[:100]
        now = timezone.now()
        results = []
        for case in cases:
            deadline = case.created_at + timedelta(hours={"high": 4, "normal": 24, "low": 48}[case.priority])
            results.append({**SupportCaseListSerializer(case).data,
                            "assigned_to": None if not case.assigned_to else {"id": case.assigned_to_id, "username": case.assigned_to.username},
                            "response_due_at": deadline, "overdue": now > deadline and case.status == SupportCase.Status.OPEN})
        assignees = User.objects.filter(is_active=True).filter(
            Q(is_superuser=True) | Q(operations_grants__role=StaffGrant.Role.SUPPORT,
                                       operations_grants__active=True)
        ).distinct().order_by("username")[:100]
        return Response({"results": results, "assignees": [{"id": user.pk, "username": user.username} for user in assignees]})


class EscalateSupportView(OperationsView):
    @extend_schema(request=EscalationSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request, case_id):
        require(request, StaffGrant.Role.SUPPORT)
        data = EscalationSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        with transaction.atomic():
            case = get_object_or_404(SupportCase.objects.select_for_update(), pk=case_id)
            if case.status == SupportCase.Status.CLOSED:
                return failure(OperationsError("Closed cases cannot be escalated."))
            previous = case.priority
            case.priority = data.validated_data["priority"]
            case.save(update_fields=["priority", "updated_at"])
            SupportCaseEvent.objects.create(case=case, actor=request.user,
                                            event_type=SupportCaseEvent.EventType.COMMENTED,
                                            message=data.validated_data["note"],
                                            metadata={"previous_priority": previous, "new_priority": case.priority})
            record(request.user, "support.escalated", "support_case", case.pk, data.validated_data["note"],
                   {"previous_priority": previous, "new_priority": case.priority})
        return Response({"id": case.pk, "priority": case.priority})


class AppointmentsView(OperationsView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        require(request, StaffGrant.Role.SCHEDULE)
        reference = request.query_params.get("reference", "").strip()
        if reference:
            try:
                reference = uuid.UUID(reference)
            except ValueError:
                return Response({"detail": "Enter a valid booking reference."}, status=400)
            appointments = Appointment.objects.filter(booking_reference=reference)
        else:
            now = timezone.now()
            appointments = Appointment.objects.filter(
                Q(status=Appointment.Status.CONFIRMED, slot__starts_at__gte=now)
                | Q(status=Appointment.Status.CANCELLED, cancelled_at__gte=now - timedelta(days=7))
            )
        appointments = appointments.select_related(
            "slot__affiliation__clinic", "slot__affiliation__doctor", "payment_intent"
        ).annotate(open_support_count=Count("support_cases", filter=~Q(
            support_cases__status__in=[SupportCase.Status.RESOLVED, SupportCase.Status.CLOSED]
        ))).order_by("slot__starts_at")[:100]
        results = []
        for item in appointments:
            payment = getattr(item, "payment_intent", None)
            results.append({"id": item.pk, "booking_reference": item.booking_reference, "status": item.status,
                            "starts_at": item.slot.starts_at, "clinic": item.slot.affiliation.clinic.name,
                            "doctor": item.slot.affiliation.doctor.display_name,
                            "payment_status": payment.status if payment else None,
                            "open_support_count": item.open_support_count})
        return Response({"results": results})


class CancelAppointmentView(OperationsView):
    @extend_schema(request=ReasonSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request, appointment_id):
        require(request, StaffGrant.Role.SCHEDULE)
        data = ReasonSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            appointment = cancel_for_support(appointment_id=appointment_id, actor=request.user, **data.validated_data)
        except Appointment.DoesNotExist:
            return Response({"detail": "Appointment not found."}, status=404)
        except (OperationsError, AppointmentBookingError) as error:
            return failure(error)
        return Response({"id": appointment.pk, "status": appointment.status})


class DeliveriesView(OperationsView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        require(request, StaffGrant.Role.DELIVERY)
        stale = timezone.now() - timedelta(minutes=15)
        items = NotificationOutbox.objects.filter(
            Q(status=NotificationOutbox.Status.FAILED)
            | Q(status=NotificationOutbox.Status.PROCESSING, locked_at__lte=stale)
        ).order_by("created_at")[:100]
        return Response({"results": [{"id": item.pk, "channel": item.channel, "category": item.category,
                                       "status": item.status, "attempt_count": item.attempt_count,
                                       "max_attempts": item.max_attempts, "last_error_code": item.last_error_code,
                                       "scheduled_for": item.scheduled_for} for item in items]})


class RetryDeliveryView(OperationsView):
    @extend_schema(request=ReasonSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request, notification_id):
        require(request, StaffGrant.Role.DELIVERY)
        data = ReasonSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            item = retry_delivery(notification_id=notification_id, actor=request.user, **data.validated_data)
        except NotificationOutbox.DoesNotExist:
            return Response({"detail": "Delivery not found."}, status=404)
        except OperationsError as error:
            return failure(error)
        return Response({"id": item.pk, "status": item.status, "queued": True})


class AuditView(OperationsView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied()
        items = OperationsEvent.objects.select_related("actor")[:100]
        return Response({"results": [{"id": item.pk, "actor": item.actor.username, "action": item.action,
                                       "subject_type": item.subject_type, "subject_id": item.subject_id,
                                       "note": item.note, "metadata": item.metadata, "created_at": item.created_at} for item in items]})


class StaffView(OperationsView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied()
        grants = StaffGrant.objects.select_related("user").order_by("user__username", "role")[:200]
        search = request.query_params.get("search", "").strip()
        if len(search) > 100:
            return Response({"detail": "Search is too long."}, status=400)
        users = User.objects.none()
        if len(search) >= 2:
            users = User.objects.filter(is_active=True, is_superuser=False).filter(
                Q(username__icontains=search) | Q(email__icontains=search)
            ).order_by("username")[:20]
        return Response({"results": [{"user_id": item.user_id, "username": item.user.username,
                                       "role": item.role, "active": item.active} for item in grants],
                         "users": [{"id": user.pk, "username": user.username, "email": user.email} for user in users]})


class StaffGrantView(OperationsView):
    @extend_schema(request=GrantSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request, user_id):
        if not request.user.is_superuser:
            raise PermissionDenied()
        data = GrantSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = get_object_or_404(User, pk=user_id, is_active=True)
        try:
            grant = set_staff_grant(user=user, actor=request.user, **data.validated_data)
        except OperationsError as error:
            return failure(error)
        return Response({"user_id": user.pk, "role": grant.role, "active": grant.active})
