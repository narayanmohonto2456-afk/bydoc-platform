import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import translation

from .models import UserPreference


pytestmark = pytest.mark.django_db

User = get_user_model()


def create_user(
    username,
    language=UserPreference.Language.ENGLISH,
):
    user = User.objects.create_user(
        username=username,
        password="test-password",
    )

    user.preferences.preferred_language = language
    user.preferences.save(
        update_fields=[
            "preferred_language",
            "updated_at",
        ]
    )

    return user


def authenticated_client(user):
    client = Client()
    client.force_login(user)

    return client


def test_bengali_preference_is_activated_for_session_user():
    user = create_user(
        "bengali-middleware-user",
        UserPreference.Language.BENGALI,
    )
    client = authenticated_client(user)

    response = client.get(
        reverse("preferences:language-list")
    )

    assert response.status_code == 200
    assert response["Content-Language"] == "bn"


def test_hindi_preference_is_activated_for_session_user():
    user = create_user(
        "hindi-middleware-user",
        UserPreference.Language.HINDI,
    )
    client = authenticated_client(user)

    response = client.get(
        reverse("preferences:language-list")
    )

    assert response.status_code == 200
    assert response["Content-Language"] == "hi"


def test_english_preference_is_activated_for_session_user():
    user = create_user(
        "english-middleware-user",
        UserPreference.Language.ENGLISH,
    )
    client = authenticated_client(user)

    response = client.get(
        reverse("preferences:language-list")
    )

    assert response.status_code == 200
    assert response["Content-Language"] == "en"


def test_anonymous_request_uses_accept_language_header():
    client = Client()

    response = client.get(
        reverse("preferences:language-list"),
        HTTP_ACCEPT_LANGUAGE="hi",
    )

    assert response.status_code == 200
    assert response["Content-Language"] == "hi"


def test_anonymous_request_uses_language_cookie():
    client = Client()
    client.cookies[
        settings.LANGUAGE_COOKIE_NAME
    ] = "bn"

    response = client.get(
        reverse("preferences:language-list")
    )

    assert response.status_code == 200
    assert response["Content-Language"] == "bn"


def test_saved_preference_overrides_request_header():
    user = create_user(
        "stored-language-user",
        UserPreference.Language.BENGALI,
    )
    client = authenticated_client(user)

    response = client.get(
        reverse("preferences:language-list"),
        HTTP_ACCEPT_LANGUAGE="hi",
    )

    assert response.status_code == 200
    assert response["Content-Language"] == "bn"


def test_missing_preference_is_recreated_safely():
    user = create_user("missing-preference-user")

    UserPreference.objects.filter(
        user=user
    ).delete()

    assert not UserPreference.objects.filter(
        user=user
    ).exists()

    client = authenticated_client(user)

    response = client.get(
        reverse("preferences:language-list")
    )

    assert response.status_code == 200
    assert response["Content-Language"] == "en"

    recreated_preference = UserPreference.objects.get(
        user=user
    )

    assert (
        recreated_preference.preferred_language
        == UserPreference.Language.ENGLISH
    )


def test_language_does_not_leak_between_users():
    bengali_user = create_user(
        "isolated-bengali-user",
        UserPreference.Language.BENGALI,
    )
    english_user = create_user(
        "isolated-english-user",
        UserPreference.Language.ENGLISH,
    )

    bengali_client = authenticated_client(
        bengali_user
    )
    english_client = authenticated_client(
        english_user
    )

    bengali_response = bengali_client.get(
        reverse("preferences:language-list")
    )

    english_response = english_client.get(
        reverse("preferences:language-list")
    )

    second_bengali_response = bengali_client.get(
        reverse("preferences:language-list")
    )

    assert (
        bengali_response["Content-Language"]
        == "bn"
    )
    assert (
        english_response["Content-Language"]
        == "en"
    )
    assert (
        second_bengali_response["Content-Language"]
        == "bn"
    )


def test_thread_language_is_restored_after_request():
    translation.activate("en")

    user = create_user(
        "restored-language-user",
        UserPreference.Language.BENGALI,
    )
    client = authenticated_client(user)

    response = client.get(
        reverse("preferences:language-list")
    )

    assert response.status_code == 200
    assert response["Content-Language"] == "bn"
    assert translation.get_language() == "en"

    translation.deactivate()