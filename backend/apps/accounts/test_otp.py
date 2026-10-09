import re
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .models import OtpChallenge, VerifiedEmail, VerifiedPhone
from .otp import code_for
from .tasks import dispatch_otp


pytestmark = pytest.mark.django_db
User = get_user_model()


def browser():
    client = APIClient(enforce_csrf_checks=True)
    csrf = client.get("/api/v1/auth/csrf/").data["csrf_token"]
    return client, csrf


@override_settings(API_LEGACY_SESSION_AUTH=False)
def test_email_otp_is_delivered_once_and_signs_in():
    user = User.objects.create_user(username="otp-email-user", password="strong-test-password-123")
    VerifiedEmail.objects.create(user=user, address="patient@example.com", verified_at=timezone.now())
    client, csrf = browser()
    payload = {"channel": "email", "identifier": "PATIENT@example.com"}
    requested = client.post("/api/v1/auth/otp/request/", payload, format="json", HTTP_X_CSRFTOKEN=csrf)
    assert requested.status_code == 202
    assert OtpChallenge.objects.filter(user=user).count() == 1
    assert dispatch_otp() == 1
    assert len(mail.outbox) == 1
    code = re.search(r"\b[0-9]{6}\b", mail.outbox[0].body).group()
    confirmed = client.post("/api/v1/auth/otp/confirm/", {**payload, "code": code},
                            format="json", HTTP_X_CSRFTOKEN=csrf)
    assert confirmed.status_code == 200
    assert settings.AUTH_ACCESS_COOKIE_NAME in client.cookies
    assert client.get("/api/v1/auth/me/").status_code == 200
    replay = client.post("/api/v1/auth/otp/confirm/", {**payload, "code": code},
                         format="json", HTTP_X_CSRFTOKEN=confirmed.data["csrf_token"])
    assert replay.status_code == 400


def test_email_otp_request_does_not_reveal_unknown_account():
    client, csrf = browser()
    response = client.post("/api/v1/auth/otp/request/", {
        "channel": "email", "identifier": "missing@example.com",
    }, format="json", HTTP_X_CSRFTOKEN=csrf)
    assert response.status_code == 202
    assert OtpChallenge.objects.count() == 0


def test_wrong_otp_attempts_are_persisted_and_bounded():
    user = User.objects.create_user(username="otp-attempt-user", password="strong-test-password-123")
    VerifiedEmail.objects.create(user=user, address="patient@example.com", verified_at=timezone.now())
    challenge = OtpChallenge.objects.create(
        user=user, purpose="login", channel="email", destination="patient@example.com",
        state="sent", expires_at=timezone.now() + timezone.timedelta(minutes=10),
    )
    client, csrf = browser()
    wrong = "000000" if code_for(challenge) != "000000" else "000001"
    for _ in range(5):
        response = client.post("/api/v1/auth/otp/confirm/", {
            "channel": "email", "identifier": "patient@example.com", "code": wrong,
        }, format="json", HTTP_X_CSRFTOKEN=csrf)
        assert response.status_code == 400
    challenge.refresh_from_db()
    assert challenge.attempts == 5


@override_settings(
    OTP_SMS_ENABLED=True, AWS_SMS_REGION="ap-south-1", AWS_SMS_ORIGINATION_ID="BYDOC",
    AWS_SMS_ENTITY_ID="entity-test", AWS_SMS_LOGIN_TEMPLATE_ID="login-test",
    AWS_SMS_VERIFY_TEMPLATE_ID="verify-test",
)
def test_sms_requires_phone_verification_then_allows_login():
    user = User.objects.create_user(
        username="otp-phone-user", password="strong-test-password-123", phone_number="+919876543210",
    )
    client, csrf = browser()
    client.force_login(user)
    requested = client.post("/api/v1/auth/phone/verify/request/", {}, format="json", HTTP_X_CSRFTOKEN=csrf)
    assert requested.status_code == 202
    challenge = OtpChallenge.objects.get(user=user, purpose="verify_phone")
    with patch("apps.accounts.otp.boto3.client") as sms_client:
        assert dispatch_otp() == 1
    options = sms_client.return_value.send_text_message.call_args.kwargs
    assert options["DestinationPhoneNumber"] == user.phone_number
    assert options["DestinationCountryParameters"]["IN_TEMPLATE_ID"] == "verify-test"
    confirmed = client.post("/api/v1/auth/phone/verify/confirm/", {
        "code": code_for(challenge),
    }, format="json", HTTP_X_CSRFTOKEN=csrf)
    assert confirmed.status_code == 204
    assert VerifiedPhone.objects.filter(user=user, number=user.phone_number).exists()

    other, other_csrf = browser()
    requested = other.post("/api/v1/auth/otp/request/", {
        "channel": "sms", "identifier": user.phone_number,
    }, format="json", HTTP_X_CSRFTOKEN=other_csrf)
    assert requested.status_code == 202
    login_challenge = OtpChallenge.objects.get(user=user, purpose="login")
    with patch("apps.accounts.otp.boto3.client") as sms_client:
        dispatch_otp()
    assert sms_client.return_value.send_text_message.call_args.kwargs["DestinationCountryParameters"]["IN_TEMPLATE_ID"] == "login-test"
    signed_in = other.post("/api/v1/auth/otp/confirm/", {
        "channel": "sms", "identifier": user.phone_number, "code": code_for(login_challenge),
    }, format="json", HTTP_X_CSRFTOKEN=other_csrf)
    assert signed_in.status_code == 200


@override_settings(OTP_SMS_ENABLED=False)
def test_sms_request_fails_closed_when_sender_is_missing():
    client, csrf = browser()
    response = client.post("/api/v1/auth/otp/request/", {
        "channel": "sms", "identifier": "+919876543210",
    }, format="json", HTTP_X_CSRFTOKEN=csrf)
    assert response.status_code == 503


def test_changing_profile_phone_removes_sms_sign_in_identity():
    user = User.objects.create_user(
        username="changed-phone-user", password="strong-test-password-123", phone_number="+919876543210",
    )
    VerifiedPhone.objects.create(user=user, number=user.phone_number, verified_at=timezone.now())
    client, csrf = browser()
    client.force_login(user)
    client.get("/api/v1/auth/profile/")
    response = client.patch("/api/v1/auth/profile/", {
        "phone_number": "+919876543211",
    }, format="json", HTTP_X_CSRFTOKEN=csrf)
    assert response.status_code == 200
    assert not VerifiedPhone.objects.filter(user=user).exists()
