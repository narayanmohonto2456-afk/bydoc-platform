import pytest
from django.contrib.auth import get_user_model
from django.core.cache import caches
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from .google_auth import GoogleClaims, verify_google_credential
from .models import AccountRecoveryRequest, GoogleIdentity, VerifiedEmail
from .recovery import token_for


pytestmark = pytest.mark.django_db
User = get_user_model()
PASSWORD = "Fjord!82-River$Puzzle"


@pytest.fixture(autouse=True)
def clear_auth_limits():
    caches["authentication"].clear()
    yield
    caches["authentication"].clear()


def browser():
    return APIClient(enforce_csrf_checks=True)


def post(client, name, data):
    client.get(reverse("accounts:csrf"))
    return client.post(
        reverse(f"accounts:{name}"), data, format="json",
        HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
    )


def claims(subject="google-sub-1", email="patient@gmail.com"):
    return GoogleClaims(subject, email, "Patient", "Example")


def test_registration_requests_verification_and_email_login_after_confirmation():
    client = browser()
    response = post(client, "register", {
        "username": "email-patient", "email": "Patient@Example.com", "password": PASSWORD,
    })
    assert response.status_code == 201, response.data
    user = User.objects.get(username="email-patient")
    assert user.email is None
    assert not VerifiedEmail.objects.filter(user=user).exists()
    record = AccountRecoveryRequest.objects.get(user=user, purpose="verify")
    assert record.address == "patient@example.com"

    before = post(client, "login", {"username": "patient@example.com", "password": PASSWORD})
    assert before.status_code == 400
    assert post(client, "verify-email-confirm", {"token": token_for(record)}).status_code == 204
    after = post(client, "login", {"username": "PATIENT@EXAMPLE.COM", "password": PASSWORD})
    assert after.status_code == 200, after.data
    assert after.data["user"]["id"] == str(user.pk)


def test_email_login_does_not_trust_unverified_user_email():
    User.objects.create_user(username="legacy", email="unverified@example.com", password=PASSWORD)
    response = post(browser(), "login", {
        "username": "unverified@example.com", "password": PASSWORD,
    })
    assert response.status_code == 400
    assert response.data == {"detail": "Unable to sign in with these credentials."}


def test_registration_keeps_email_addresses_out_of_usernames():
    response = post(browser(), "register", {
        "username": "patient@example.com", "email": "patient@example.com", "password": PASSWORD,
    })
    assert response.status_code == 400
    assert "username" in response.data
    assert not User.objects.exists()


def test_google_sign_in_creates_non_staff_user_and_reuses_subject(monkeypatch):
    monkeypatch.setattr("apps.accounts.views.verify_google_credential", lambda _: claims())
    client = browser()
    first = post(client, "google-sign-in", {"credential": "signed-token"})
    assert first.status_code == 200, first.data
    user = User.objects.get(pk=first.data["user"]["id"])
    assert not user.has_usable_password()
    assert not user.is_staff and not user.is_superuser
    assert GoogleIdentity.objects.get(user=user).subject == "google-sub-1"
    assert VerifiedEmail.objects.get(user=user).address == "patient@gmail.com"
    response = client.get(reverse("accounts:google-status"))
    assert response.data == {
        "connected": True, "verified_email": "patient@gmail.com", "has_password": False,
    }
    assert post(client, "logout", {}).status_code == 204
    second = post(client, "google-sign-in", {"credential": "signed-token"})
    assert second.status_code == 200
    assert second.data["user"]["id"] == str(user.pk)
    assert User.objects.count() == 1


def test_google_never_auto_links_existing_email(monkeypatch):
    user = User.objects.create_user(username="existing", password=PASSWORD)
    VerifiedEmail.objects.create(user=user, address="patient@gmail.com", verified_at=timezone.now())
    monkeypatch.setattr("apps.accounts.views.verify_google_credential", lambda _: claims())
    response = post(browser(), "google-sign-in", {"credential": "signed-token"})
    assert response.status_code == 409
    assert not GoogleIdentity.objects.exists()
    assert User.objects.count() == 1


def test_existing_user_can_link_matching_verified_google_email(monkeypatch):
    user = User.objects.create_user(username="existing", password=PASSWORD)
    VerifiedEmail.objects.create(user=user, address="patient@gmail.com", verified_at=timezone.now())
    monkeypatch.setattr("apps.accounts.views.verify_google_credential", lambda _: claims())
    client = browser()
    client.force_login(user)
    assert post(client, "google-link", {"credential": "signed-token"}).status_code == 204
    assert GoogleIdentity.objects.get(user=user).subject == "google-sub-1"
    assert post(client, "google-link", {"credential": "signed-token"}).status_code == 204
    assert GoogleIdentity.objects.count() == 1
    response = post(browser(), "google-sign-in", {"credential": "signed-token"})
    assert response.data["user"]["id"] == str(user.pk)


def test_link_requires_matching_verified_email_and_csrf(monkeypatch):
    user = User.objects.create_user(username="existing", password=PASSWORD)
    VerifiedEmail.objects.create(user=user, address="different@gmail.com", verified_at=timezone.now())
    monkeypatch.setattr("apps.accounts.views.verify_google_credential", lambda _: claims())
    client = browser()
    client.force_login(user)
    assert client.post(reverse("accounts:google-link"), {"credential": "signed-token"}, format="json").status_code == 403
    assert post(client, "google-link", {"credential": "signed-token"}).status_code == 400
    assert not GoogleIdentity.objects.exists()


def test_google_sign_in_requires_csrf(monkeypatch):
    monkeypatch.setattr("apps.accounts.views.verify_google_credential", lambda _: claims())
    response = browser().post(reverse("accounts:google-sign-in"), {"credential": "signed-token"}, format="json")
    assert response.status_code == 403
    assert not User.objects.exists()


def test_google_sign_in_waits_for_client_id(settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = ""
    response = post(browser(), "google-sign-in", {"credential": "signed-token"})
    assert response.status_code == 503
    assert not User.objects.exists()


def test_invalid_google_token_cannot_create_account(settings, monkeypatch):
    settings.GOOGLE_OAUTH_CLIENT_ID = "web-client-id"

    def reject_token(*args):
        raise ValueError("Invalid signature")

    monkeypatch.setattr("apps.accounts.google_auth.id_token.verify_oauth2_token", reject_token)
    response = post(browser(), "google-sign-in", {"credential": "bad-token"})
    assert response.status_code == 400
    assert not User.objects.exists()


@pytest.mark.parametrize("payload,accepted", [
    ({"sub": "sub-1", "email": "member@gmail.com", "email_verified": True}, True),
    ({"sub": "sub-1", "email": "member@clinic.org", "email_verified": True, "hd": "clinic.org"}, True),
    ({"sub": "sub-1", "email": "member@other.org", "email_verified": True}, False),
    ({"sub": "sub-1", "email": "member@gmail.com", "email_verified": False}, False),
])
def test_google_claim_validation_uses_configured_audience(settings, monkeypatch, payload, accepted):
    settings.GOOGLE_OAUTH_CLIENT_ID = "web-client-id"
    def fake_verify(token, request, audience):
        assert token == "signed-token"
        assert audience == "web-client-id"
        return payload
    monkeypatch.setattr("apps.accounts.google_auth.id_token.verify_oauth2_token", fake_verify)
    if accepted:
        assert verify_google_credential("signed-token").subject == "sub-1"
    else:
        from rest_framework.exceptions import ValidationError
        with pytest.raises(ValidationError):
            verify_google_credential("signed-token")
