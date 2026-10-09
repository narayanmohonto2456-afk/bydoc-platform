import base64

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import caches
from django.urls import reverse
from rest_framework.test import APIClient

from apps.preferences.models import UserPreference
from .rate_limits import consume_limit
from .serializers import RegistrationSerializer

pytestmark = pytest.mark.django_db
User = get_user_model()
PASSWORD = "Fjord!82-River$Puzzle"


@pytest.fixture(autouse=True)
def isolated_counters():
    caches["authentication"].clear()
    yield
    caches["authentication"].clear()


def browser():
    return APIClient(enforce_csrf_checks=True)


def csrf(client):
    response = client.get(reverse("accounts:csrf"))
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    assert settings.CSRF_COOKIE_NAME in client.cookies
    return response.data["csrf_token"]


def post(client, name, data, token=None, **headers):
    return client.post(
        reverse("accounts:" + name), data, format="json",
        HTTP_X_CSRFTOKEN=token or csrf(client), **headers,
    )


def test_registration_login_account_and_logout():
    client = browser()
    registered = post(client, "register", {
        "username": "patient-one", "password": PASSWORD, "first_name": "Patient",
    })
    assert registered.status_code == 201, registered.data
    assert set(registered.data) == {"id", "username", "first_name", "last_name"}
    user = User.objects.get(username="patient-one")
    assert user.check_password(PASSWORD)
    assert user.password != PASSWORD
    assert not user.is_staff and not user.is_superuser
    assert not user.groups.exists() and not user.user_permissions.exists()
    assert UserPreference.objects.filter(user=user).count() == 1
    assert client.get(reverse("accounts:me")).status_code == 401

    session = client.session
    session["before_login"] = "anonymous-session"
    session.save()
    previous_session_key = session.session_key
    old_token = csrf(client)
    signed_in = post(client, "login", {
        "username": user.username, "password": PASSWORD,
    }, token=old_token)
    assert signed_in.status_code == 200, signed_in.data
    assert str(signed_in.data["user"]["id"]) == str(user.pk)
    assert signed_in.data["csrf_token"] != old_token
    assert client.session.session_key != previous_session_key
    session_cookie = client.cookies[settings.SESSION_COOKIE_NAME]
    assert session_cookie["httponly"]
    assert session_cookie["samesite"] == "Lax"

    account = client.get(reverse("accounts:me"))
    assert account.status_code == 200
    assert str(account.data["id"]) == str(user.pk)
    assert account["Cache-Control"] == "no-store"
    assert client.get(reverse("appointments:my-appointments")).status_code == 200
    assert client.patch(reverse("accounts:me"), {}, format="json",
                        HTTP_X_CSRFTOKEN=signed_in.data["csrf_token"]).status_code == 405

    # Login rotates the token; a stale token cannot log out the new session.
    assert post(client, "logout", {}, token=old_token).status_code == 403
    logged_out = post(client, "logout", {}, token=signed_in.data["csrf_token"])
    assert logged_out.status_code == 204
    assert client.get(reverse("accounts:me")).status_code == 401
    assert client.get(reverse("appointments:my-appointments")).status_code == 401


@pytest.mark.parametrize("endpoint", ["register", "login"])
def test_anonymous_mutations_require_csrf(endpoint):
    client = browser()
    response = client.post(reverse("accounts:" + endpoint), {
        "username": "csrf-patient", "password": PASSWORD,
    }, format="json")
    assert response.status_code == 403
    assert response["Cache-Control"] == "no-store"
    assert not User.objects.filter(username="csrf-patient").exists()


def test_untrusted_origin_is_rejected_even_with_valid_token():
    client = browser()
    response = post(client, "register", {
        "username": "origin-patient", "password": PASSWORD,
    }, HTTP_ORIGIN="https://untrusted.example")
    assert response.status_code == 403
    assert not User.objects.filter(username="origin-patient").exists()


@pytest.mark.parametrize("field,value", [
    ("is_staff", True), ("is_superuser", True), ("is_active", False),
    ("groups", [1]), ("user_permissions", [1]), ("id", "chosen-id"),
    ("phone_number", "+919876543210"),
])
def test_registration_rejects_unapproved_fields(field, value):
    response = post(browser(), "register", {
        "username": "privilege-test", "password": PASSWORD, field: value,
    })
    assert response.status_code == 400
    assert not User.objects.filter(username="privilege-test").exists()


@pytest.mark.parametrize("password", ["123", "password", "123456789012", "x" * 129])
def test_password_validation(password):
    response = post(browser(), "register", {"username": "weak-test", "password": password})
    assert response.status_code == 400
    assert "password" in response.data
    assert not User.objects.filter(username="weak-test").exists()


def test_password_whitespace_is_preserved():
    password = " " + PASSWORD + " "
    client = browser()
    assert post(client, "register", {"username": "space-test", "password": password}).status_code == 201
    assert User.objects.get(username="space-test").check_password(password)
    assert post(client, "login", {"username": "space-test", "password": PASSWORD}).status_code == 400
    assert post(client, "login", {"username": "space-test", "password": password}).status_code == 200


def test_duplicate_registration_is_a_validation_error():
    User.objects.create_user(username="existing", password=PASSWORD)
    response = post(browser(), "register", {"username": "existing", "password": PASSWORD})
    assert response.status_code == 400
    assert User.objects.filter(username="existing").count() == 1


def test_registration_race_is_a_validation_error():
    from rest_framework.exceptions import ValidationError
    pending = RegistrationSerializer(data={"username": "race-user", "password": PASSWORD})
    assert pending.is_valid(), pending.errors
    User.objects.create_user(username="race-user", password=PASSWORD)
    with pytest.raises(ValidationError):
        pending.save()
    assert User.objects.filter(username="race-user").count() == 1


@pytest.mark.parametrize("kind", ["missing", "wrong-password", "inactive"])
def test_invalid_login_returns_same_generic_error(kind):
    if kind != "missing":
        User.objects.create_user(username="login-test", password=PASSWORD,
                                 is_active=kind != "inactive")
    response = post(browser(), "login", {
        "username": "login-test",
        "password": "wrong-password" if kind == "wrong-password" else PASSWORD,
    })
    assert response.status_code == 400
    assert response.data == {"detail": "Unable to sign in with these credentials."}


def test_basic_auth_cannot_bypass_login_rate_limits():
    User.objects.create_user(username="basic-test", password=PASSWORD)
    client = browser()
    credentials = base64.b64encode(f"basic-test:{PASSWORD}".encode()).decode()
    assert client.get(reverse("accounts:me"), HTTP_AUTHORIZATION="Basic " + credentials).status_code == 401
    assert client.get(reverse("appointments:my-appointments"), HTTP_AUTHORIZATION="Basic " + credentials).status_code == 401


def test_logout_requires_csrf_and_rejects_get():
    client = browser()
    user = User.objects.create_user(username="logout-test", password=PASSWORD)
    client.force_login(user)
    assert client.post(reverse("accounts:logout"), {}, format="json").status_code == 403
    assert client.get(reverse("accounts:logout")).status_code == 405
    assert client.get(reverse("accounts:me")).status_code == 200


def test_my_account_never_returns_another_user():
    user = User.objects.create_user(username="owner", password=PASSWORD)
    other = User.objects.create_user(username="other", password=PASSWORD)
    client = browser()
    client.force_login(user)
    response = client.get(reverse("accounts:me"), {"user_id": str(other.pk)})
    assert str(response.data["id"]) == str(user.pk)


def test_login_ip_limit_counts_attempts_despite_spoofed_forwarded_header(settings):
    settings.AUTH_RATE_LIMITS = {"login_ip": (2, 60), "login_account": (100, 300), "register_ip": (5, 3600)}
    client = browser()
    for i in range(2):
        assert post(client, "login", {"username": f"missing-{i}", "password": PASSWORD},
                    HTTP_X_FORWARDED_FOR=f"192.0.2.{i}").status_code == 400
    response = post(client, "login", {"username": "third", "password": PASSWORD},
                    HTTP_X_FORWARDED_FOR="192.0.2.99")
    assert response.status_code == 429
    assert int(response["Retry-After"]) > 0


def test_account_limit_applies_across_client_addresses(settings):
    settings.AUTH_RATE_LIMITS = {"login_ip": (100, 60), "login_account": (1, 300), "register_ip": (5, 3600)}
    first = post(browser(), "login", {"username": "target", "password": PASSWORD}, REMOTE_ADDR="192.0.2.1")
    second = post(browser(), "login", {"username": "target", "password": PASSWORD}, REMOTE_ADDR="192.0.2.2")
    assert first.status_code == 400
    assert second.status_code == 429


def test_registration_rate_limit(settings):
    settings.AUTH_RATE_LIMITS = {"login_ip": (30, 60), "login_account": (10, 300), "register_ip": (1, 3600)}
    client = browser()
    assert post(client, "register", {"username": "reg-one", "password": PASSWORD}).status_code == 201
    assert post(client, "register", {"username": "reg-two", "password": PASSWORD}).status_code == 429
    assert not User.objects.filter(username="reg-two").exists()


@pytest.mark.parametrize("endpoint", ["login", "register"])
def test_cache_failure_blocks_auth_with_safe_error(monkeypatch, endpoint):
    def unavailable(*args, **kwargs):
        raise ConnectionError("redis://private-credentials@internal")
    monkeypatch.setattr(caches["authentication"], "add", unavailable)
    response = post(browser(), endpoint, {"username": "cache-test", "password": PASSWORD})
    assert response.status_code == 503
    assert "redis" not in str(response.data)
    assert not User.objects.filter(username="cache-test").exists()


def test_rate_limit_allows_requests_in_next_window(settings, monkeypatch):
    from rest_framework.exceptions import Throttled
    settings.AUTH_RATE_LIMITS = {"login_ip": (1, 60)}
    monkeypatch.setattr("apps.accounts.rate_limits.time", lambda: 120.0)
    consume_limit("login_ip", "192.0.2.1")
    with pytest.raises(Throttled):
        consume_limit("login_ip", "192.0.2.1")
    monkeypatch.setattr("apps.accounts.rate_limits.time", lambda: 180.0)
    consume_limit("login_ip", "192.0.2.1")
