import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.notifications.models import NotificationOutbox
from apps.dashboard.test_dashboard import make_appointment, make_clinic
from apps.onboarding.models import DoctorApplication
from apps.support.models import SupportCase

from .models import OperationsEvent, StaffGrant, WebhookFailure
from .services import retry_delivery


pytestmark = pytest.mark.django_db
User = get_user_model()


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def grant(user, role, by):
    return StaffGrant.objects.create(user=user, role=role, granted_by=by)


def test_staff_roles_gate_queues_and_support_records():
    owner = User.objects.create_superuser(username="ops-owner", password="test")
    provider = User.objects.create_user(username="provider-agent", password="test")
    requester = User.objects.create_user(username="support-requester", password="test")
    case = SupportCase.objects.create(
        requester=requester, category=SupportCase.Category.OTHER,
        subject="Account help", description="Cannot use a feature.",
    )
    grant(provider, StaffGrant.Role.PROVIDER, owner)
    api = client_for(provider)
    assert api.get("/api/v1/operations/providers/").status_code == 200
    assert api.get("/api/v1/operations/support/").status_code == 403
    assert api.get(f"/api/v1/support/cases/{case.pk}/").status_code == 404
    assert api.get("/api/v1/operations/audit/").status_code == 403


def test_superuser_grants_and_revokes_scoped_access_with_audit():
    owner = User.objects.create_superuser(username="staff-owner", password="test")
    agent = User.objects.create_user(username="new-agent", password="test")
    api = client_for(owner)
    search = api.get("/api/v1/operations/staff/?search=new-agent")
    assert search.status_code == 200
    assert search.data["users"][0]["id"] == agent.pk
    assert client_for(agent).get("/api/v1/operations/staff/?search=staff").status_code == 403
    path = f"/api/v1/operations/staff/{agent.pk}/grant/"
    response = api.post(path, {"role": "support", "active": True, "note": "Assigned to the support team"}, format="json")
    assert response.status_code == 200
    assert client_for(agent).get("/api/v1/operations/support/").status_code == 200
    assert api.post(path, {"role": "support", "active": False, "note": "End of assignment"}, format="json").status_code == 200
    assert client_for(agent).get("/api/v1/operations/support/").status_code == 403
    assert list(OperationsEvent.objects.filter(subject_id=str(agent.pk)).values_list("action", flat=True)) == [
        "staff.access_revoked", "staff.access_granted",
    ]


def test_provider_approval_requires_complete_checklist_and_independent_review():
    owner = User.objects.create_superuser(username="review-owner", password="test")
    reviewer = User.objects.create_user(username="reviewer", password="test")
    applicant = User.objects.create_user(username="applicant", password="test")
    grant(reviewer, StaffGrant.Role.PROVIDER, owner)
    application = DoctorApplication.objects.create(
        applicant=applicant, attested_at=timezone.now(), display_name="Dr Example",
        registered_name="Example", council_name="Council", registration_number="TEST123",
    )
    path = f"/api/v1/operations/providers/doctor/{application.pk}/review/"
    api = client_for(reviewer)
    response = api.post(path, {"approve": True, "note": "Checked application", "checks": {
        "identity": True, "registration": True, "duplicate": False,
    }}, format="json")
    assert response.status_code == 409
    application.refresh_from_db()
    assert application.status == "pending"
    response = api.post(path, {"approve": False, "note": "Registration could not be verified", "checks": {
        "identity": True, "registration": False, "duplicate": True,
    }}, format="json")
    assert response.status_code == 200
    application.refresh_from_db()
    assert application.status == "rejected"
    assert OperationsEvent.objects.filter(action="provider.rejected", subject_id=str(application.pk)).exists()


def test_plain_django_staff_has_no_operations_access():
    user = User.objects.create_user(username="plain-staff", password="test", is_staff=True)
    api = client_for(user)
    assert api.get("/api/v1/operations/summary/").status_code == 403
    assert api.get("/api/v1/operations/support/").status_code == 403


def test_schedule_desk_validates_booking_reference():
    owner = User.objects.create_superuser(username="schedule-owner", password="test")
    agent = User.objects.create_user(username="schedule-agent", password="test")
    grant(agent, StaffGrant.Role.SCHEDULE, owner)
    api = client_for(agent)
    assert api.get("/api/v1/operations/appointments/?reference=not-a-uuid").status_code == 400
    assert api.get("/api/v1/operations/appointments/").data["results"] == []


def test_schedule_desk_finds_and_cancels_booking_without_deleting_record():
    owner = User.objects.create_superuser(username="desk-owner", password="test")
    agent = User.objects.create_user(username="desk-agent", password="test")
    patient = User.objects.create_user(username="desk-patient", password="test")
    grant(agent, StaffGrant.Role.SCHEDULE, owner)
    _, clinic = make_clinic("Desk Clinic")
    appointment = make_appointment(patient, clinic)
    api = client_for(agent)
    search = api.get(f"/api/v1/operations/appointments/?reference={appointment.booking_reference}")
    assert search.status_code == 200
    assert search.data["results"][0]["id"] == appointment.pk
    assert search.data["results"][0]["open_support_count"] == 0
    response = api.post(f"/api/v1/operations/appointments/{appointment.pk}/cancel/",
                        {"note": "Clinic requested cancellation"}, format="json")
    assert response.status_code == 200
    appointment.refresh_from_db()
    assert appointment.status == "cancelled"
    assert OperationsEvent.objects.filter(action="appointment.cancelled", subject_id=str(appointment.pk)).exists()


def test_provider_reactivation_requires_fresh_checklist():
    owner = User.objects.create_superuser(username="reactivate-owner", password="test")
    agent = User.objects.create_user(username="reactivate-agent", password="test")
    grant(agent, StaffGrant.Role.PROVIDER, owner)
    _, clinic = make_clinic("Reactivation Clinic")
    clinic.status = "suspended"
    clinic.save(update_fields=["status"])
    api = client_for(agent)
    path = f"/api/v1/operations/providers/clinic/{clinic.pk}/status/"
    assert api.post(path, {"suspend": False, "note": "Checked registration"}, format="json").status_code == 409
    assert api.post(path, {"suspend": False, "note": "Checked registration and identity", "checks": {
        "identity": True, "registration": True, "duplicate": True,
    }}, format="json").status_code == 200
    clinic.refresh_from_db()
    assert clinic.status == "active"
    assert OperationsEvent.objects.filter(action="provider.reactivated", subject_id=str(clinic.pk)).exists()


def test_delivery_retry_is_scoped_and_audited():
    owner = User.objects.create_superuser(username="delivery-owner", password="test")
    agent = User.objects.create_user(username="delivery-agent", password="test")
    recipient = User.objects.create_user(username="delivery-recipient", password="test")
    grant(agent, StaffGrant.Role.DELIVERY, owner)
    item = NotificationOutbox.objects.create(
        deduplication_key="operations-test-delivery", recipient=recipient,
        channel=NotificationOutbox.Channel.EMAIL,
        category=NotificationOutbox.Category.APPOINTMENT_CANCELLED,
        template_key="appointment_cancelled", status=NotificationOutbox.Status.FAILED,
        scheduled_for=timezone.now(), attempt_count=5, max_attempts=5,
    )
    retry_delivery(notification_id=item.pk, actor=agent, note="Transient delivery failure")
    item.refresh_from_db()
    assert item.max_attempts == 6
    assert item.next_attempt_at is not None
    assert OperationsEvent.objects.filter(action="delivery.retry_requested", subject_id=str(item.pk)).exists()


def test_only_verified_failed_webhooks_appear_in_finance_queue(monkeypatch):
    from apps.payments import gateway

    owner = User.objects.create_superuser(username="finance-owner", password="test")
    grant(owner, StaffGrant.Role.FINANCE, owner)
    monkeypatch.setattr(gateway, "configured", lambda: True)
    monkeypatch.setattr(gateway, "webhook_signature_valid", lambda body, signature: signature == "valid")
    api = APIClient()
    path = "/api/v1/payments/webhook/razorpay/"
    assert api.post(path, {"event": "payment.captured", "payload": {}}, format="json",
                    HTTP_X_RAZORPAY_SIGNATURE="invalid", HTTP_X_RAZORPAY_EVENT_ID="evt_test").status_code == 400
    assert WebhookFailure.objects.count() == 0
    assert api.post(path, {"event": "payment.captured", "payload": {}}, format="json",
                    HTTP_X_RAZORPAY_SIGNATURE="valid", HTTP_X_RAZORPAY_EVENT_ID="evt_test").status_code == 400
    assert WebhookFailure.objects.get(pk="evt_test").error_code == "KeyError"
    queue = client_for(owner).get("/api/v1/operations/payments/")
    assert queue.status_code == 200
    assert queue.data["webhook_failures"][0]["event_id"] == "evt_test"
