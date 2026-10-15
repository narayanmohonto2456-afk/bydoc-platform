from django.db import transaction
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.appointments.services import cancel_appointment
from apps.clinics.models import Clinic
from apps.doctors.models import DoctorProfile, DoctorRegistration
from apps.notifications.models import NotificationOutbox
from apps.organizations.models import Organization
from apps.onboarding.services import review_clinic, review_doctor
from apps.payments.models import PaymentIntent

from .models import OperationsEvent, PaymentInvestigation, StaffGrant
from .permissions import has_role


class OperationsError(Exception):
    pass


def require_role(user, role):
    if not has_role(user, role):
        raise OperationsError("This action requires a specific operations role.")


def record(actor, action, subject_type, subject_id, note="", metadata=None):
    return OperationsEvent.objects.create(
        actor=actor, action=action, subject_type=subject_type,
        subject_id=str(subject_id), note=note[:500], metadata=metadata or {},
    )


@transaction.atomic
def decide_application(*, kind, application_id, actor, approve, note, checks):
    require_role(actor, StaffGrant.Role.PROVIDER)
    if approve and not all(checks.values()):
        raise OperationsError("Complete every verification check before approval.")
    if not checks or set(checks) != {"identity", "registration", "duplicate"}:
        raise OperationsError("Identity, registration, and duplicate checks are required.")
    if kind == "doctor":
        application = review_doctor(application_id, actor, approve, note)
    elif kind == "clinic":
        application = review_clinic(application_id, actor, approve, note)
    else:
        raise OperationsError("Unknown application type.")
    record(actor, f"provider.{application.status}", f"{kind}_application", application.pk, note,
           {"checks": checks})
    return application


@transaction.atomic
def change_provider_status(*, kind, provider_id, actor, suspend, note, checks=None):
    require_role(actor, StaffGrant.Role.PROVIDER)
    if not note.strip():
        raise OperationsError("A reason is required.")
    if kind == "doctor":
        provider = DoctorProfile.objects.select_for_update().get(pk=provider_id)
        expected = DoctorProfile.Status.ACTIVE if suspend else DoctorProfile.Status.SUSPENDED
        target = DoctorProfile.Status.SUSPENDED if suspend else DoctorProfile.Status.ACTIVE
    elif kind == "clinic":
        provider = Clinic.objects.select_for_update().get(pk=provider_id)
        expected = Clinic.Status.ACTIVE if suspend else Clinic.Status.SUSPENDED
        target = Clinic.Status.SUSPENDED if suspend else Clinic.Status.ACTIVE
    else:
        raise OperationsError("Unknown provider type.")
    if provider.status != expected:
        raise OperationsError("Provider status changed; reload before continuing.")
    if not suspend:
        if set(checks or {}) != {"identity", "registration", "duplicate"} or not all(checks.values()):
            raise OperationsError("Complete every re-verification check before reactivation.")
        if kind == "doctor" and not DoctorRegistration.objects.filter(
            doctor=provider, verification_status=DoctorRegistration.VerificationStatus.VERIFIED
        ).exists():
            raise OperationsError("A verified doctor registration is required before reactivation.")
        if kind == "clinic" and provider.organization.status != Organization.Status.ACTIVE:
            raise OperationsError("The clinic organization must be active before reactivation.")
    provider.status = target
    provider.save(update_fields=["status", "updated_at"])
    record(actor, "provider.suspended" if suspend else "provider.reactivated", kind, provider.pk, note,
           {"checks": checks or {}})
    return provider


@transaction.atomic
def set_investigation(*, intent_id, actor, resolved, note):
    require_role(actor, StaffGrant.Role.FINANCE)
    if not note.strip():
        raise OperationsError("Record the investigation outcome or next step.")
    intent = PaymentIntent.objects.select_for_update().get(pk=intent_id)
    investigation, _ = PaymentInvestigation.objects.update_or_create(
        intent=intent, defaults={"resolved": resolved, "note": note.strip(), "updated_by": actor},
    )
    record(actor, "payment.investigation_resolved" if resolved else "payment.investigation_opened",
           "payment_intent", intent.pk, note)
    return investigation


@transaction.atomic
def cancel_for_support(*, appointment_id, actor, note):
    require_role(actor, StaffGrant.Role.SCHEDULE)
    if not note.strip():
        raise OperationsError("A cancellation reason is required.")
    current = Appointment.objects.select_for_update().get(pk=appointment_id)
    if current.status != Appointment.Status.CONFIRMED:
        raise OperationsError("Only confirmed appointments can be cancelled from the desk.")
    appointment = cancel_appointment(appointment_id, actor, note)
    record(actor, "appointment.cancelled", "appointment", appointment.pk, note)
    return appointment


@transaction.atomic
def retry_delivery(*, notification_id, actor, note):
    require_role(actor, StaffGrant.Role.DELIVERY)
    if not note.strip():
        raise OperationsError("A retry reason is required.")
    item = NotificationOutbox.objects.select_for_update().get(pk=notification_id)
    if item.status != NotificationOutbox.Status.FAILED:
        raise OperationsError("Only failed deliveries can be retried.")
    if item.attempt_count >= item.max_attempts:
        if item.max_attempts >= 20:
            raise OperationsError("Maximum manual retries reached.")
        item.max_attempts += 1
    item.next_attempt_at = timezone.now()
    item.save(update_fields=["max_attempts", "next_attempt_at", "updated_at"])
    record(actor, "delivery.retry_requested", "notification", item.pk, note,
           {"attempt_count": item.attempt_count})
    from apps.notifications.tasks import deliver_notification
    transaction.on_commit(lambda: deliver_notification.delay(str(item.pk)))
    return item


@transaction.atomic
def set_staff_grant(*, user, role, active, actor, note):
    if not actor.is_active or not actor.is_superuser:
        raise OperationsError("Only a superuser can manage staff access.")
    if user.pk == actor.pk or user.is_superuser:
        raise OperationsError("This account cannot be changed here.")
    if not note.strip():
        raise OperationsError("A reason is required.")
    if role not in StaffGrant.Role.values:
        raise OperationsError("Unknown role.")
    grant, _ = StaffGrant.objects.update_or_create(
        user=user, role=role,
        defaults={"active": active, "granted_by": actor},
    )
    record(actor, "staff.access_granted" if active else "staff.access_revoked", "user", user.pk,
           note, {"role": role})
    return grant
