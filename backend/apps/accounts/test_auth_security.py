"""Regression coverage for recovery and authentication factor changes."""

import pytest
from django.core.cache import caches
from django.test import Client, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from .models import AccountRecoveryRequest, OtpChallenge, User, VerifiedEmail, VerifiedPhone
from .otp import code_for, create_challenge
from .recovery import consume_link, request_link, token_for


pytestmark = pytest.mark.django_db
PASSWORD = "Original-password-726!"
NEW_PASSWORD = "Replacement-password-839!"


@pytest.fixture(autouse=True)
def isolated_counters():
    caches["authentication"].clear()
    yield
    caches["authentication"].clear()


def email_user():
    user = User.objects.create_user(username="security-patient", password=PASSWORD)
    VerifiedEmail.objects.create(user=user, address="old@example.test", verified_at=timezone.now())
    return user


def test_email_replacement_invalidates_old_mailbox_reset_link():
    user = email_user()
    old_reset = request_link(user, AccountRecoveryRequest.Purpose.RESET, "old@example.test")
    replacement = request_link(user, AccountRecoveryRequest.Purpose.VERIFY, "new@example.test")
    consume_link(token_for(replacement), AccountRecoveryRequest.Purpose.VERIFY)

    with pytest.raises(ValidationError):
        consume_link(token_for(old_reset), AccountRecoveryRequest.Purpose.RESET, NEW_PASSWORD)
    user.refresh_from_db()
    assert user.check_password(PASSWORD)
    assert VerifiedEmail.objects.get(user=user).address == "new@example.test"


def test_old_verification_link_cannot_restore_an_earlier_mailbox():
    user = email_user()
    older = request_link(user, AccountRecoveryRequest.Purpose.VERIFY, "older@example.test")
    replacement = request_link(user, AccountRecoveryRequest.Purpose.VERIFY, "new@example.test")
    consume_link(token_for(replacement), AccountRecoveryRequest.Purpose.VERIFY)

    with pytest.raises(ValidationError):
        consume_link(token_for(older), AccountRecoveryRequest.Purpose.VERIFY)
    assert VerifiedEmail.objects.get(user=user).address == "new@example.test"


@override_settings(API_LEGACY_SESSION_AUTH=False)
def test_password_reset_invalidates_previously_issued_login_otp():
    user = email_user()
    challenge = create_challenge(user, "login", "email", "old@example.test")
    challenge.state = OtpChallenge.State.SENT
    challenge.save(update_fields=["state"])
    code = code_for(challenge)
    reset = request_link(user, AccountRecoveryRequest.Purpose.RESET, "old@example.test")
    consume_link(token_for(reset), AccountRecoveryRequest.Purpose.RESET, NEW_PASSWORD)
    client = APIClient(enforce_csrf_checks=True)
    csrf = client.get("/api/v1/auth/csrf/").data["csrf_token"]

    response = client.post("/api/v1/auth/otp/confirm/", {
        "channel": "email", "identifier": "old@example.test", "code": code,
    }, format="json", HTTP_X_CSRFTOKEN=csrf)

    assert response.status_code == 400
    assert client.get("/api/v1/auth/me/").status_code == 401


SMS_SETTINGS = dict(
    OTP_SMS_ENABLED=True, AWS_SMS_REGION="ap-south-1", AWS_SMS_ORIGINATION_ID="TEST",
    AWS_SMS_ENTITY_ID="test", AWS_SMS_LOGIN_TEMPLATE_ID="test", AWS_SMS_VERIFY_TEMPLATE_ID="test",
)


@override_settings(**SMS_SETTINGS)
@pytest.mark.parametrize("payload", [{}, {"current_password": "wrong-password"}])
def test_session_alone_cannot_request_sms_enrollment(payload):
    user = email_user()
    user.phone_number = "+919876540002"
    user.save(update_fields=["phone_number"])
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post("/api/v1/auth/phone/verify/request/", payload, format="json")

    assert response.status_code == 400
    assert not OtpChallenge.objects.filter(user=user, purpose="verify_phone").exists()


@pytest.mark.parametrize("payload", [{}, {"current_password": "wrong-password"}])
def test_pending_sms_code_cannot_enroll_a_factor_without_current_password(payload):
    user = email_user()
    user.phone_number = "+919876540002"
    user.save(update_fields=["phone_number"])
    challenge = create_challenge(user, "verify_phone", "sms", user.phone_number)
    challenge.state = OtpChallenge.State.SENT
    challenge.save(update_fields=["state"])
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post("/api/v1/auth/phone/verify/confirm/", {
        **payload, "code": code_for(challenge),
    }, format="json")

    assert response.status_code == 400
    assert not VerifiedPhone.objects.filter(user=user).exists()


def test_admin_login_uses_shared_authentication_limits(settings):
    settings.AUTH_RATE_LIMITS = {**settings.AUTH_RATE_LIMITS, "login_ip": (2, 60)}
    User.objects.create_user(username="review-admin", password=PASSWORD, is_staff=True)
    client = Client(enforce_csrf_checks=True)
    client.get("/admin/login/")
    payload = {
        "username": "review-admin", "password": "wrong-password",
        "csrfmiddlewaretoken": client.cookies[settings.CSRF_COOKIE_NAME].value,
    }

    assert client.post("/admin/login/", payload).status_code == 200
    assert client.post("/admin/login/", payload).status_code == 200
    response = client.post("/admin/login/", payload)
    assert response.status_code == 429
    assert int(response["Retry-After"]) > 0


def test_admin_login_fails_closed_when_counter_store_is_unavailable(settings, monkeypatch):
    client = Client(enforce_csrf_checks=True)
    client.get("/admin/login/")

    def unavailable(*args, **kwargs):
        raise RuntimeError("Cache unavailable")

    monkeypatch.setattr(caches["authentication"], "incr", unavailable)
    response = client.post("/admin/login/", {
        "username": "review-admin", "password": "wrong-password",
        "csrfmiddlewaretoken": client.cookies[settings.CSRF_COOKIE_NAME].value,
    })
    assert response.status_code == 503
