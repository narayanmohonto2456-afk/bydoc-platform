import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from .models import AuthSession


pytestmark = pytest.mark.django_db
PASSWORD = "Fjord!82-River$Puzzle"


def browser():
    client = APIClient(enforce_csrf_checks=True)
    csrf = client.get(reverse("accounts:csrf")).data["csrf_token"]
    return client, csrf


@override_settings(API_LEGACY_SESSION_AUTH=False)
def test_jwt_cookie_login_refresh_and_logout():
    user = get_user_model().objects.create_user(username="jwt-patient", password=PASSWORD)
    client, csrf = browser()
    login = client.post(reverse("accounts:login"), {
        "username": user.username, "password": PASSWORD,
    }, format="json", HTTP_X_CSRFTOKEN=csrf)
    assert login.status_code == 200
    assert settings.AUTH_ACCESS_COOKIE_NAME in client.cookies
    assert settings.AUTH_REFRESH_COOKIE_NAME in client.cookies
    assert settings.SESSION_COOKIE_NAME not in client.cookies
    assert client.cookies[settings.AUTH_ACCESS_COOKIE_NAME]["httponly"]
    assert client.get(reverse("accounts:me")).status_code == 200

    first_refresh = client.cookies[settings.AUTH_REFRESH_COOKIE_NAME].value
    refreshed = client.post(reverse("accounts:token-refresh"), {}, format="json",
                            HTTP_X_CSRFTOKEN=login.data["csrf_token"])
    assert refreshed.status_code == 200
    assert client.cookies[settings.AUTH_REFRESH_COOKIE_NAME].value != first_refresh
    assert client.post(reverse("accounts:logout"), {}, format="json").status_code == 403
    assert client.post(reverse("accounts:logout"), {}, format="json",
                       HTTP_X_CSRFTOKEN=login.data["csrf_token"]).status_code == 204
    assert client.get(reverse("accounts:me")).status_code == 401
    assert AuthSession.objects.filter(user=user, revoked_at__isnull=False).count() == 1


@override_settings(API_LEGACY_SESSION_AUTH=False)
def test_refresh_replay_revokes_the_session():
    user = get_user_model().objects.create_user(username="jwt-replay", password=PASSWORD)
    client, csrf = browser()
    login = client.post(reverse("accounts:login"), {
        "username": user.username, "password": PASSWORD,
    }, format="json", HTTP_X_CSRFTOKEN=csrf)
    old_refresh = client.cookies[settings.AUTH_REFRESH_COOKIE_NAME].value
    assert client.post(reverse("accounts:token-refresh"), {}, format="json",
                       HTTP_X_CSRFTOKEN=login.data["csrf_token"]).status_code == 200
    client.cookies[settings.AUTH_REFRESH_COOKIE_NAME] = old_refresh
    replay = client.post(reverse("accounts:token-refresh"), {}, format="json",
                         HTTP_X_CSRFTOKEN=login.data["csrf_token"])
    assert replay.status_code == 401, replay.data
    assert client.get(reverse("accounts:me")).status_code == 401


@override_settings(API_LEGACY_SESSION_AUTH=False)
def test_bearer_access_works_without_a_browser_cookie():
    user = get_user_model().objects.create_user(username="jwt-bearer", password=PASSWORD)
    client, csrf = browser()
    client.post(reverse("accounts:login"), {
        "username": user.username, "password": PASSWORD,
    }, format="json", HTTP_X_CSRFTOKEN=csrf)
    access = client.cookies[settings.AUTH_ACCESS_COOKIE_NAME].value
    client.cookies.pop(settings.AUTH_ACCESS_COOKIE_NAME)
    response = client.get(reverse("accounts:me"), HTTP_AUTHORIZATION=f"Bearer {access}")
    assert response.status_code == 200
