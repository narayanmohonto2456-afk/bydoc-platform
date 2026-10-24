from datetime import date

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.operations.models import OperationsEvent
from apps.organizations.models import OrganizationMembership

from .models import AppointmentSlot, AvailabilityRule, ScheduleException
from .test_api import create_affiliation, create_future_slot, create_user, slot_local_date


pytestmark = pytest.mark.django_db


def manager_client(affiliation):
    manager = create_user("schedule-manager")
    OrganizationMembership.objects.create(
        organization=affiliation.clinic.organization,
        user=manager,
        role=OrganizationMembership.Role.MANAGER,
        status=OrganizationMembership.Status.ACTIVE,
        joined_at=timezone.now(),
    )
    client = APIClient()
    client.force_authenticate(user=manager)
    return client


def rule_payload(affiliation, start="09:00", end="12:00"):
    return {
        "affiliation_id": str(affiliation.pk),
        "weekday": date.today().weekday(),
        "start_time": start,
        "end_time": end,
        "valid_from": date.today().isoformat(),
        "reason": "Clinic schedule published",
    }


def test_manager_can_create_rule_with_audit_and_reject_overlap():
    affiliation = create_affiliation()
    client = manager_client(affiliation)
    url = f"/api/v1/appointments/clinics/{affiliation.clinic_id}/schedule/rules/"

    first = client.post(url, rule_payload(affiliation), format="json")
    assert first.status_code == 201
    assert AvailabilityRule.objects.filter(affiliation=affiliation).count() == 1
    assert OperationsEvent.objects.filter(
        action="schedule.rule.created", subject_id=first.data["id"],
    ).exists()
    affiliation.clinic.refresh_from_db()
    assert affiliation.clinic.schedule_updated_at is not None

    overlapping = client.post(
        url, rule_payload(affiliation, start="11:00", end="13:00"), format="json",
    )
    assert overlapping.status_code == 400
    assert AvailabilityRule.objects.filter(affiliation=affiliation).count() == 1


def test_manager_cannot_create_rule_for_another_clinic():
    own = create_affiliation()
    other = create_affiliation(
        organization_slug="other-schedule-org",
        clinic_slug="other-schedule-clinic",
        doctor_username="other-schedule-doctor",
    )
    client = manager_client(own)
    response = client.post(
        f"/api/v1/appointments/clinics/{other.clinic_id}/schedule/rules/",
        rule_payload(other),
        format="json",
    )
    assert response.status_code == 404
    assert not AvailabilityRule.objects.filter(affiliation=other).exists()


def test_closure_blocks_open_slot_and_prevents_held_slot_confirmation():
    affiliation = create_affiliation()
    open_slot = create_future_slot(affiliation, hours_from_now=25)
    held_slot = create_future_slot(affiliation, hours_from_now=24)
    patient_client = APIClient()
    patient_client.force_authenticate(user=create_user("closure-patient"))
    hold = patient_client.post(
        f"/api/v1/appointments/slots/{held_slot.pk}/hold/", {}, format="json",
    )
    assert hold.status_code == 200

    manager = manager_client(affiliation)
    response = manager.post(
        f"/api/v1/appointments/clinics/{affiliation.clinic_id}/schedule/exceptions/",
        {
            "affiliation_id": str(affiliation.pk),
            "exception_date": slot_local_date(open_slot).isoformat(),
            "exception_type": "closed",
            "reason": "Doctor leave",
        },
        format="json",
    )
    assert response.status_code == 201
    assert ScheduleException.objects.filter(affiliation=affiliation).count() == 1
    open_slot.refresh_from_db()
    assert open_slot.status == AppointmentSlot.Status.BLOCKED
    booking = patient_client.post(
        f"/api/v1/appointments/slots/{held_slot.pk}/book/",
        {
            "hold_token": hold.data["hold_token"],
            "booking_request_id": "8f78521a-721c-444e-9fd6-a334b799dd80",
        },
        format="json",
    )
    assert booking.status_code == 409


def test_clinic_staff_can_block_open_slot_but_not_booked_slot():
    affiliation = create_affiliation()
    slot = create_future_slot(affiliation)
    manager = manager_client(affiliation)
    url = f"/api/v1/appointments/clinics/{affiliation.clinic_id}/schedule/slots/{slot.pk}/block/"
    blocked = manager.post(url, {"reason": "Equipment unavailable"}, format="json")
    assert blocked.status_code == 200
    slot.refresh_from_db()
    assert slot.status == AppointmentSlot.Status.BLOCKED
    assert OperationsEvent.objects.filter(
        action="schedule.slot.blocked", subject_id=str(slot.pk),
    ).exists()

    booked = create_future_slot(
        affiliation, hours_from_now=26, status_value=AppointmentSlot.Status.BOOKED,
    )
    booked_response = manager.post(
        f"/api/v1/appointments/clinics/{affiliation.clinic_id}/schedule/slots/{booked.pk}/block/",
        {"reason": "Equipment unavailable"},
        format="json",
    )
    assert booked_response.status_code == 409
    booked.refresh_from_db()
    assert booked.status == AppointmentSlot.Status.BOOKED
