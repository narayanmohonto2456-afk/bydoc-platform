from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from .models import PatientProfile
from .serializers import PatientProfileSerializer


pytestmark = pytest.mark.django_db

User = get_user_model()


def create_user(username, phone_number=None):
    return User.objects.create_user(
        username=username,
        password="ProfileTestPassword123!",
        phone_number=phone_number,
    )


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def profile_url():
    return reverse("accounts:my-patient-profile")


def test_authenticated_user_can_view_empty_profile():
    user = create_user("empty-profile-user")
    client = authenticated_client(user)

    response = client.get(profile_url())

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {
        "first_name": "",
        "last_name": "",
        "phone_number": None,
        "date_of_birth": None,
        "gender": "",
        "emergency_contact_name": "",
        "emergency_contact_phone": "",
    }

    assert PatientProfile.objects.filter(user=user).exists()


def test_authenticated_user_can_update_profile():
    user = create_user("update-profile-user")
    client = authenticated_client(user)

    response = client.patch(
        profile_url(),
        {
            "first_name": "Narayan",
            "last_name": "Mohanta",
            "phone_number": "+919876543210",
            "date_of_birth": "2002-01-15",
            "gender": PatientProfile.Gender.MAN,
            "emergency_contact_name": "Emergency Contact",
            "emergency_contact_phone": "+919876543211",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["first_name"] == "Narayan"
    assert response.data["last_name"] == "Mohanta"
    assert response.data["phone_number"] == "+919876543210"
    assert response.data["date_of_birth"] == "2002-01-15"
    assert response.data["gender"] == PatientProfile.Gender.MAN

    user.refresh_from_db()
    profile = PatientProfile.objects.get(user=user)

    assert user.first_name == "Narayan"
    assert user.last_name == "Mohanta"
    assert user.phone_number == "+919876543210"
    assert profile.emergency_contact_name == "Emergency Contact"


def test_profile_update_requires_complete_emergency_contact():
    user = create_user("incomplete-emergency-user")
    client = authenticated_client(user)

    response = client.patch(
        profile_url(),
        {"emergency_contact_name": "Only Name"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "emergency_contact_name" in response.data
    assert "emergency_contact_phone" in response.data


def test_profile_rejects_future_date_of_birth():
    user = create_user("future-date-user")
    client = authenticated_client(user)

    future_date = timezone.localdate() + timedelta(days=1)

    response = client.patch(
        profile_url(),
        {"date_of_birth": future_date.isoformat()},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "date_of_birth" in response.data


def test_profile_rejects_invalid_phone_number():
    user = create_user("invalid-phone-user")
    client = authenticated_client(user)

    response = client.patch(
        profile_url(),
        {"phone_number": "9876543210"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "phone_number" in response.data


def test_profile_rejects_phone_number_used_by_another_user():
    create_user(
        "existing-phone-user",
        phone_number="+919876543210",
    )
    user = create_user("duplicate-phone-user")
    client = authenticated_client(user)

    response = client.patch(
        profile_url(),
        {"phone_number": "+919876543210"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "phone_number" in response.data


def test_profile_rejects_unsupported_fields():
    user = create_user("strict-profile-user")
    client = authenticated_client(user)

    response = client.patch(
        profile_url(),
        {"is_staff": True},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "non_field_errors" in response.data


def test_profiles_are_private_to_each_authenticated_user():
    first_user = create_user("first-private-profile-user")
    second_user = create_user("second-private-profile-user")

    first_client = authenticated_client(first_user)
    second_client = authenticated_client(second_user)

    first_client.patch(
        profile_url(),
        {
            "first_name": "First",
            "emergency_contact_name": "First Contact",
            "emergency_contact_phone": "+919876543211",
        },
        format="json",
    )

    response = second_client.get(profile_url())

    assert response.status_code == status.HTTP_200_OK
    assert response.data["first_name"] == ""
    assert response.data["emergency_contact_name"] == ""


def test_phone_claimed_after_validation_returns_400():
    user = create_user("phone-race-user")
    profile = PatientProfile.objects.create(user=user)
    number = "+919876543212"
    serializer = PatientProfileSerializer(profile, data={"phone_number": number}, partial=True)
    assert serializer.is_valid(), serializer.errors
    create_user("phone-race-winner", phone_number=number)

    from rest_framework.exceptions import ValidationError as APIValidationError
    with pytest.raises(APIValidationError) as error:
        serializer.save()
    assert "phone_number" in error.value.detail
    user.refresh_from_db()
    assert user.phone_number is None


def test_profile_patch_enforces_session_csrf():
    user = create_user("csrf-profile-user")
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user)
    assert client.patch(profile_url(), {"first_name": "Blocked"}, format="json").status_code == 403
    csrf_response = client.get(reverse("accounts:csrf"))
    assert csrf_response.status_code == 200
    token = csrf_response.data["csrf_token"]
    changed = client.patch(profile_url(), {"first_name": "Allowed"}, format="json", HTTP_X_CSRFTOKEN=token)
    assert changed.status_code == 200, changed.data
    user.refresh_from_db()
    assert user.first_name == "Allowed"
