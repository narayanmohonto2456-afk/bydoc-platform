import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .models import UserPreference


pytestmark = pytest.mark.django_db

User = get_user_model()


def create_user(username):
    return User.objects.create_user(
        username=username,
        password="test-password",
    )


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_supported_languages_are_public():
    client = APIClient()

    response = client.get(
        reverse("preferences:language-list")
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == [
        {
            "code": "en",
            "name": "English",
        },
        {
            "code": "bn",
            "name": "বাংলা",
        },
        {
            "code": "hi",
            "name": "हिन्दी",
        },
    ]


def test_anonymous_user_cannot_view_preferences():
    client = APIClient()

    response = client.get(
        reverse("preferences:my-preferences")
    )

    assert response.status_code in {
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    }


def test_authenticated_user_can_view_preferences():
    user = create_user("preference-api-user")
    client = authenticated_client(user)

    response = client.get(
        reverse("preferences:my-preferences")
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {
        "preferred_language": "en",
        "language_name": "English",
        "low_data_mode": False,
        "large_text": False,
        "high_contrast": False,
        "reduce_motion": False,
        "updated_at": response.data["updated_at"],
    }
    assert response["Content-Language"] == "en"


def test_user_can_update_preferred_language():
    user = create_user("language-api-user")
    client = authenticated_client(user)

    response = client.patch(
        reverse("preferences:my-preferences"),
        {
            "preferred_language": "bn",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["preferred_language"] == "bn"
    assert response.data["language_name"] == "বাংলা"
    assert response["Content-Language"] == "bn"

    language_cookie = response.cookies[
        settings.LANGUAGE_COOKIE_NAME
    ]

    assert language_cookie.value == "bn"

    user.preferences.refresh_from_db()

    assert user.preferences.preferred_language == "bn"


def test_partial_update_preserves_other_preferences():
    user = create_user("partial-preference-user")
    preferences = user.preferences

    preferences.large_text = True
    preferences.high_contrast = True
    preferences.save(
        update_fields=[
            "large_text",
            "high_contrast",
            "updated_at",
        ]
    )

    client = authenticated_client(user)

    response = client.patch(
        reverse("preferences:my-preferences"),
        {
            "low_data_mode": True,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["low_data_mode"] is True
    assert response.data["large_text"] is True
    assert response.data["high_contrast"] is True
    assert response.data["reduce_motion"] is False


def test_user_can_enable_all_accessibility_preferences():
    user = create_user("accessibility-api-user")
    client = authenticated_client(user)

    response = client.patch(
        reverse("preferences:my-preferences"),
        {
            "low_data_mode": True,
            "large_text": True,
            "high_contrast": True,
            "reduce_motion": True,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["low_data_mode"] is True
    assert response.data["large_text"] is True
    assert response.data["high_contrast"] is True
    assert response.data["reduce_motion"] is True

    user.preferences.refresh_from_db()

    assert user.preferences.low_data_mode is True
    assert user.preferences.large_text is True
    assert user.preferences.high_contrast is True
    assert user.preferences.reduce_motion is True


def test_unsupported_language_is_rejected():
    user = create_user("invalid-language-api-user")
    client = authenticated_client(user)

    response = client.patch(
        reverse("preferences:my-preferences"),
        {
            "preferred_language": "fr",
        },
        format="json",
    )

    assert (
        response.status_code
        == status.HTTP_400_BAD_REQUEST
    )
    assert "preferred_language" in response.data

    user.preferences.refresh_from_db()

    assert (
        user.preferences.preferred_language
        == UserPreference.Language.ENGLISH
    )


def test_user_cannot_update_another_users_preferences():
    first_user = create_user("first-preference-api-user")
    second_user = create_user("second-preference-api-user")

    second_user.preferences.preferred_language = "hi"
    second_user.preferences.large_text = True
    second_user.preferences.save(
        update_fields=[
            "preferred_language",
            "large_text",
            "updated_at",
        ]
    )

    client = authenticated_client(first_user)

    response = client.patch(
        reverse("preferences:my-preferences"),
        {
            "preferred_language": "bn",
            "large_text": True,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK

    first_user.preferences.refresh_from_db()
    second_user.preferences.refresh_from_db()

    assert first_user.preferences.preferred_language == "bn"
    assert first_user.preferences.large_text is True
    assert second_user.preferences.preferred_language == "hi"
    assert second_user.preferences.large_text is True


def test_protected_fields_are_ignored():
    user = create_user("protected-preference-user")
    other_user = create_user(
        "protected-preference-other-user"
    )
    client = authenticated_client(user)

    preference_id = user.preferences.pk

    response = client.patch(
        reverse("preferences:my-preferences"),
        {
            "user": str(other_user.pk),
            "id": str(other_user.preferences.pk),
            "created_at": "2000-01-01T00:00:00Z",
            "preferred_language": "hi",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK

    user.preferences.refresh_from_db()

    assert user.preferences.pk == preference_id
    assert user.preferences.user == user
    assert user.preferences.preferred_language == "hi"


def test_post_and_delete_are_not_allowed():
    user = create_user("method-preference-user")
    client = authenticated_client(user)
    url = reverse("preferences:my-preferences")

    post_response = client.post(
        url,
        {},
        format="json",
    )

    delete_response = client.delete(url)

    assert (
        post_response.status_code
        == status.HTTP_405_METHOD_NOT_ALLOWED
    )
    assert (
        delete_response.status_code
        == status.HTTP_405_METHOD_NOT_ALLOWED
    )