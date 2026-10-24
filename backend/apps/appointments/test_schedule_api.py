from datetime import date

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.operations.models import OperationsEvent
from apps.organizations.models import OrganizationMembership

from .models import AvailabilityRule
from .test_api import create_affiliation, create_user


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
