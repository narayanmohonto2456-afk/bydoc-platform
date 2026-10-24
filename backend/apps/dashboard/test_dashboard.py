from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from apps.appointments.models import Appointment, AppointmentSlot
from apps.clinics.models import Clinic
from apps.doctors.models import DoctorClinicAffiliation, DoctorProfile
from apps.organizations.models import ClinicStaffAssignment, Organization, OrganizationMembership


def make_user(django_user_model, name):
    return django_user_model.objects.create_user(username=name, password="test-password-123")


def make_clinic(name):
    organization = Organization.objects.create(
        name=name, slug=name.lower().replace(" ", "-"), status=Organization.Status.ACTIVE,
    )
    clinic = Clinic.objects.create(
        organization=organization,
        name=name,
        slug="main",
        status=Clinic.Status.ACTIVE,
        address_line_1="1 Main Road",
        locality="Centre",
        district="Kolkata",
        state="West Bengal",
        postal_code="700001",
        timezone="UTC",
    )
    return organization, clinic


def make_membership(
    user, organization, status=OrganizationMembership.Status.ACTIVE,
    role=OrganizationMembership.Role.RECEPTIONIST,
):
    return OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=role,
        status=status,
        joined_at=timezone.now() if status == OrganizationMembership.Status.ACTIVE else None,
    )


def make_appointment(patient, clinic):
    doctor_user = patient.__class__.objects.create_user(
        username=f"doctor-{clinic.slug}-{clinic.organization.slug}", password="test-password-123",
    )
    doctor = DoctorProfile.objects.create(user=doctor_user, display_name="Dr Test")
    affiliation = DoctorClinicAffiliation.objects.create(
        doctor=doctor, clinic=clinic, status=DoctorClinicAffiliation.Status.ACTIVE,
        joined_at=timezone.now(),
    )
    starts_at = datetime.combine(timezone.localdate(timezone=ZoneInfo("UTC")), time(12), tzinfo=ZoneInfo("UTC"))
    slot = AppointmentSlot.objects.create(
        affiliation=affiliation, starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=15), status=AppointmentSlot.Status.BOOKED,
    )
    return Appointment.objects.create(slot=slot, patient=patient, booked_by=patient)


@pytest.mark.django_db
def test_dashboard_requires_authentication(client):
    for role in ("roles", "patient", "doctor", "clinic", "admin"):
        assert client.get(f"/api/v1/dashboard/{role}/").status_code in {401, 403}


@pytest.mark.django_db
def test_patient_sees_only_own_appointments(client, django_user_model):
    patient = make_user(django_user_model, "patient")
    another = make_user(django_user_model, "another")
    _, clinic_a = make_clinic("Alpha Clinic")
    _, clinic_b = make_clinic("Beta Clinic")
    own = make_appointment(patient, clinic_a)
    make_appointment(another, clinic_b)
    client.force_login(patient)

    assert client.get("/api/v1/dashboard/roles/").json() == {
        "roles": ["patient"], "preferred": "patient",
    }
    response = client.get("/api/v1/dashboard/patient/")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["appointments"]] == [str(own.id)]
    assert client.get("/api/v1/dashboard/doctor/").status_code == 403
    assert client.get("/api/v1/dashboard/clinic/").status_code == 403
    assert client.get("/api/v1/dashboard/admin/").status_code == 403


@pytest.mark.django_db
def test_doctor_dashboard_omits_patient_identity(client, django_user_model):
    doctor_user = make_user(django_user_model, "doctor")
    DoctorProfile.objects.create(user=doctor_user, display_name="Dr Example")
    client.force_login(doctor_user)

    assert client.get("/api/v1/dashboard/roles/").json()["preferred"] == "doctor"
    response = client.get("/api/v1/dashboard/doctor/")
    assert response.status_code == 200
    assert response.json()["display_name"] == "Dr Example"
    assert "patient_name" not in str(response.json())


@pytest.mark.django_db
def test_clinic_dashboard_is_scoped_to_active_membership(client, django_user_model):
    staff = make_user(django_user_model, "staff")
    patient = make_user(django_user_model, "patient")
    org_a, clinic_a = make_clinic("Alpha Clinic")
    org_b, clinic_b = make_clinic("Beta Clinic")
    membership = make_membership(staff, org_a)
    ClinicStaffAssignment.objects.create(membership=membership, clinic=clinic_a)
    own = make_appointment(patient, clinic_a)
    make_appointment(patient, clinic_b)
    client.force_login(staff)

    response = client.get("/api/v1/dashboard/clinic/")
    assert response.status_code == 200
    assert response.json()["today_count"] == 1
    assert response.json()["appointments"][0]["id"] == str(own.id)
    assert len(response.json()["clinics"]) == 1
    assert client.get(f"/api/v1/dashboard/clinic/?clinic_id={clinic_b.id}").status_code == 404
    second_membership = make_membership(staff, org_b)
    ClinicStaffAssignment.objects.create(membership=second_membership, clinic=clinic_b)
    selected = client.get(f"/api/v1/dashboard/clinic/?clinic_id={clinic_b.id}")
    assert selected.status_code == 200
    assert selected.json()["today_count"] == 1
    assert selected.json()["appointments"][0]["clinic_name"] == "Beta Clinic"
    second_membership.status = OrganizationMembership.Status.SUSPENDED
    second_membership.save(update_fields=["status"])
    membership.status = OrganizationMembership.Status.SUSPENDED
    membership.save(update_fields=["status"])
    assert client.get("/api/v1/dashboard/clinic/").status_code == 403


@pytest.mark.django_db
def test_admin_dashboard_requires_superuser(client, django_user_model):
    staff = make_user(django_user_model, "staff")
    staff.is_staff = True
    staff.save(update_fields=["is_staff"])
    client.force_login(staff)
    assert client.get("/api/v1/dashboard/admin/").status_code == 403

    admin = django_user_model.objects.create_superuser(
        username="admin", password="test-password-123",
    )
    client.force_login(admin)
    assert client.get("/api/v1/dashboard/roles/").json()["preferred"] == "admin"
    response = client.get("/api/v1/dashboard/admin/")
    assert response.status_code == 200
    assert response.json()["account_count"] == 2


@pytest.mark.django_db
def test_receptionist_cannot_see_all_locations_in_clinic_group(client, django_user_model):
    receptionist = make_user(django_user_model, "receptionist")
    manager = make_user(django_user_model, "manager")
    organization, _ = make_clinic("Clinic Group")
    Clinic.objects.create(
        organization=organization, name="Second Location", slug="second",
        status=Clinic.Status.ACTIVE, address_line_1="2 Main Road",
        locality="Centre", district="Kolkata", state="West Bengal",
        postal_code="700002", timezone="UTC",
    )
    make_membership(receptionist, organization)
    make_membership(manager, organization, role=OrganizationMembership.Role.MANAGER)

    client.force_login(receptionist)
    assert client.get("/api/v1/dashboard/roles/").json()["roles"] == ["patient"]
    assert client.get("/api/v1/dashboard/clinic/").status_code == 403

    client.force_login(manager)
    response = client.get("/api/v1/dashboard/clinic/")
    assert response.status_code == 200
    assert len(response.json()["clinics"]) == 2


@pytest.mark.django_db
def test_receptionist_assignment_limits_multi_clinic_dashboard(client, django_user_model):
    receptionist = make_user(django_user_model, "assigned-receptionist")
    organization, clinic_a = make_clinic("Assigned Group")
    clinic_b = Clinic.objects.create(
        organization=organization, name="Other Location", slug="other",
        status=Clinic.Status.ACTIVE, address_line_1="2 Main Road",
        locality="Centre", district="Kolkata", state="West Bengal",
        postal_code="700002", timezone="UTC",
    )
    membership = make_membership(receptionist, organization)
    assignment = ClinicStaffAssignment.objects.create(membership=membership, clinic=clinic_a)
    client.force_login(receptionist)

    response = client.get("/api/v1/dashboard/clinic/")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["clinics"]] == [str(clinic_a.id)]
    assert client.get(f"/api/v1/dashboard/clinic/?clinic_id={clinic_b.id}").status_code == 404

    assignment.is_active = False
    assignment.save(update_fields=["is_active"])
    assert client.get("/api/v1/dashboard/roles/").json()["roles"] == ["patient"]
    assert client.get("/api/v1/dashboard/clinic/").status_code == 403
