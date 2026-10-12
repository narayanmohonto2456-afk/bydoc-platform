import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import VerifiedEmail
from apps.clinics.models import Clinic
from apps.dashboard.views import available_roles
from apps.doctors.models import DoctorProfile, DoctorRegistration
from apps.organizations.models import OrganizationMembership

from .models import ApplicationStatus, ClinicApplication, DoctorApplication
from .services import ApplicationError, review_clinic, review_doctor

pytestmark = pytest.mark.django_db
User = get_user_model()


def applicant(username, verified=True):
    user = User.objects.create_user(username=username, email=f"{username}@example.com", password="test-password")
    if verified:
        VerifiedEmail.objects.create(user=user, address=user.email, verified_at=timezone.now())
    client = APIClient()
    client.force_authenticate(user=user)
    return user, client


def reviewer():
    return User.objects.create_superuser(username="reviewer", email="reviewer@example.com", password="test-password")


def doctor_details():
    return {
        "display_name": "Dr Maya Sen", "registered_name": "Maya Sen",
        "council_name": "State Medical Council", "registration_number": "WB-12345",
        "registration_year": 2019, "specialty_name": "General medicine", "attestation": True,
    }


def clinic_details():
    return {
        "clinic_name": "Riverside Clinic", "manager_name": "Anita Roy",
        "registration_authority": "Local licensing authority", "registration_number": "LIC-2026-4",
        "phone_number": "+919876543210", "email": "office@riverside.example",
        "address_line_1": "12 Lake Road", "locality": "Salt Lake",
        "district": "Kolkata", "state": "West Bengal", "postal_code": "700091",
        "attestation": True,
    }


def items(response):
    return response.data.get("results", response.data) if isinstance(response.data, dict) else response.data


def test_doctor_application_requires_verified_email_and_admin_review():
    user, client = applicant("doctor-applicant", verified=False)
    url = reverse("onboarding:doctor")
    assert client.post(url, doctor_details(), format="json").status_code == 409
    VerifiedEmail.objects.create(user=user, address=user.email, verified_at=timezone.now())
    submitted = client.post(url, doctor_details(), format="json")
    assert submitted.status_code == 201
    assert submitted.data["status"] == "pending"
    assert client.post(url, doctor_details(), format="json").status_code == 409
    application = DoctorApplication.objects.get(applicant=user)
    assert application.profile_id is None
    assert not DoctorProfile.objects.filter(user=user).exists()
    assert "doctor" not in available_roles(user)
    assert items(APIClient().get(reverse("doctors:list"))) == []

    admin = reviewer()
    with pytest.raises(ApplicationError, match="evidence"):
        review_doctor(application.pk, admin, True, "")
    review_doctor(application.pk, admin, True, "Checked registration against council listing.")
    application.refresh_from_db()
    profile = DoctorProfile.objects.get(user=user)
    registration = DoctorRegistration.objects.get(doctor=profile)
    assert application.status == ApplicationStatus.APPROVED
    assert application.reviewed_by == admin
    assert application.profile == profile
    assert registration.verification_status == DoctorRegistration.VerificationStatus.VERIFIED
    assert registration.verified_by == admin
    assert "doctor" in available_roles(user)
    # A verified doctor needs an approved clinic affiliation before public listing.
    assert items(APIClient().get(reverse("doctors:list"))) == []


def test_clinic_application_is_hidden_until_approved_and_owner_is_scoped():
    user, client = applicant("clinic-applicant")
    url = reverse("onboarding:clinic")
    result = client.post(url, clinic_details(), format="json")
    assert result.status_code == 201
    application = ClinicApplication.objects.get(applicant=user)
    assert application.clinic_id is None
    assert items(APIClient().get(reverse("clinics:list"))) == []
    other, other_client = applicant("clinic-other")
    assert other_client.get(url).data["status"] == "not_submitted"
    assert client.get(url).data["status"] == "pending"
    with pytest.raises(ApplicationError, match="independent"):
        review_clinic(application.pk, user, True, "I checked myself")
    admin = reviewer()
    review_clinic(application.pk, admin, True, "Confirmed licence and manager by phone.")
    application.refresh_from_db()
    assert application.status == ApplicationStatus.APPROVED
    assert application.clinic.status == Clinic.Status.ACTIVE
    assert items(APIClient().get(reverse("clinics:list")))[0]["name"] == "Riverside Clinic"
    membership = OrganizationMembership.objects.get(user=user)
    assert membership.role == OrganizationMembership.Role.OWNER
    assert membership.organization_id == application.clinic.organization_id
    assert "clinic" in available_roles(user)
    assert "clinic" not in available_roles(other)


def test_rejected_application_can_be_resubmitted_without_losing_review_history():
    user, client = applicant("doctor-resubmit")
    url = reverse("onboarding:doctor")
    first = client.post(url, doctor_details(), format="json")
    admin = reviewer()
    review_doctor(first.data["id"], admin, False, "Registration could not be matched to the council.")
    corrected = doctor_details()
    corrected["registration_number"] = "WB-67890"
    second = client.post(url, corrected, format="json")
    assert second.status_code == 201
    assert DoctorApplication.objects.filter(applicant=user).count() == 2
    assert DoctorApplication.objects.get(pk=first.data["id"]).status == ApplicationStatus.REJECTED
    assert client.get(url).data["id"] == second.data["id"]
    assert client.get(url).data["status"] == "pending"


def test_duplicate_doctor_registration_and_false_attestation_are_rejected():
    _, first = applicant("first-registration")
    _, second = applicant("second-registration")
    url = reverse("onboarding:doctor")
    assert first.post(url, doctor_details(), format="json").status_code == 201
    assert second.post(url, doctor_details(), format="json").status_code == 409
    false_details = doctor_details()
    false_details["attestation"] = False
    assert second.post(url, false_details, format="json").status_code == 400


def test_anonymous_or_client_supplied_approval_cannot_publish_an_application():
    url = reverse("onboarding:clinic")
    assert APIClient().post(url, clinic_details(), format="json").status_code == 401
    user, client = applicant("self-approval")
    details = {**clinic_details(), "status": "approved", "review_note": "approved by applicant"}
    response = client.post(url, details, format="json")
    assert response.status_code == 201
    application = ClinicApplication.objects.get(applicant=user)
    assert application.status == ApplicationStatus.PENDING
    assert application.clinic_id is None


def test_admin_review_action_requires_saved_note_and_approves_clinic():
    user, applicant_client = applicant("admin-reviewed-clinic")
    response = applicant_client.post(reverse("onboarding:clinic"), clinic_details(), format="json")
    assert response.status_code == 201
    application = ClinicApplication.objects.get(applicant=user)
    admin_client = Client()
    admin_client.force_login(reviewer())
    list_url = reverse("admin:onboarding_clinicapplication_changelist")
    action = {"action": "approve_applications", "_selected_action": [str(application.pk)]}

    assert admin_client.post(list_url, action).status_code == 302
    application.refresh_from_db()
    assert application.status == ApplicationStatus.PENDING
    assert application.clinic_id is None

    application.review_note = "Checked licence with issuing authority and contacted manager."
    application.save(update_fields=["review_note"])
    assert admin_client.post(list_url, action).status_code == 302
    application.refresh_from_db()
    assert application.status == ApplicationStatus.APPROVED
    assert application.clinic_id is not None


def test_rejection_remains_possible_if_applicant_email_is_no_longer_verified():
    user, client = applicant("changed-email-doctor")
    response = client.post(reverse("onboarding:doctor"), doctor_details(), format="json")
    assert response.status_code == 201
    user.email = "new-address@example.com"
    user.save(update_fields=["email"])
    admin = reviewer()
    with pytest.raises(ApplicationError, match="Verify"):
        review_doctor(response.data["id"], admin, True, "Could verify medical registration.")
    review_doctor(response.data["id"], admin, False, "Applicant's new email is unverified.")
    assert DoctorApplication.objects.get(pk=response.data["id"]).status == ApplicationStatus.REJECTED
