import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import translation
from rest_framework.test import APIClient


pytestmark = pytest.mark.django_db

User = get_user_model()

MESSAGES = [
    ("en", "This language is not supported."),
    ("bn", "এই ভাষাটি সমর্থিত নয়।"),
    ("hi", "यह भाषा समर्थित नहीं है।"),
]


@pytest.fixture(autouse=True)
def restore_language():
    previous_language = translation.get_language()

    yield

    if previous_language is None:
        translation.deactivate_all()
    else:
        translation.activate(previous_language)


@pytest.fixture
def user():
    return User.objects.create_user(
        username="translation-test-user",
        password="test-password",
    )


@pytest.mark.parametrize("language,expected", MESSAGES)
def test_invalid_language_error_uses_request_header(
    user,
    language,
    expected,
):
    client = APIClient()

    # Authentication occurs inside DRF, so session middleware
    # does not override the Accept-Language selection.
    client.force_authenticate(user=user)

    response = client.patch(
        reverse("preferences:my-preferences"),
        {"preferred_language": "fr"},
        format="json",
        HTTP_ACCEPT_LANGUAGE=language,
    )

    assert response.status_code == 400
    assert str(
        response.data["preferred_language"][0]
    ) == expected
    assert response["Content-Language"] == language

    user.preferences.refresh_from_db()
    assert user.preferences.preferred_language == "en"


@pytest.mark.parametrize("language,expected", MESSAGES)
def test_session_preference_overrides_request_header(
    user,
    language,
    expected,
):
    preference = user.preferences
    preference.preferred_language = language
    preference.save(
        update_fields=[
            "preferred_language",
            "updated_at",
        ]
    )

    client = APIClient()
    client.force_login(user)

    conflicting_language = (
        "hi" if language != "hi" else "bn"
    )

    response = client.patch(
        reverse("preferences:my-preferences"),
        {"preferred_language": "fr"},
        format="json",
        HTTP_ACCEPT_LANGUAGE=conflicting_language,
    )

    assert response.status_code == 400
    assert str(
        response.data["preferred_language"][0]
    ) == expected
    assert response["Content-Language"] == language

    preference.refresh_from_db()
    assert preference.preferred_language == language

def test_session_language_change_returns_new_language(user):
    from django.conf import settings

    client = APIClient()
    client.force_login(user)
    url = reverse("preferences:my-preferences")

    response = client.patch(
        url,
        {"preferred_language": "bn"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["preferred_language"] == "bn"
    assert response["Content-Language"] == "bn"
    assert (
        response.cookies[settings.LANGUAGE_COOKIE_NAME].value
        == "bn"
    )

    user.preferences.refresh_from_db()
    assert user.preferences.preferred_language == "bn"

    invalid_response = client.patch(
        url,
        {"preferred_language": "fr"},
        format="json",
    )

    assert invalid_response.status_code == 400
    assert invalid_response["Content-Language"] == "bn"
    assert str(
        invalid_response.data["preferred_language"][0]
    ) == "এই ভাষাটি সমর্থিত নয়।"