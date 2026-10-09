import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from .models import AccountRecoveryRequest, VerifiedEmail
from .recovery import token_for
from .tasks import dispatch_recovery_email

pytestmark = pytest.mark.django_db
PASSWORD = "Fjord!82-River$Puzzle"


def post(client, name, data):
    client.get(reverse("accounts:csrf"))
    return client.post(reverse("accounts:" + name), data, format="json",
                       HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)


def test_verified_email_and_reset_flow():
    user = get_user_model().objects.create_user(username="patient", password=PASSWORD)
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user)
    response = post(client, "verify-email-request", {"address": "Patient@Example.com", "current_password": PASSWORD})
    assert response.status_code == 202, response.data
    record = AccountRecoveryRequest.objects.get(purpose="verify")
    assert not VerifiedEmail.objects.exists()
    assert dispatch_recovery_email() == 1
    assert len(mail.outbox) == 1
    assert "#token=" in mail.outbox[0].body
    token = token_for(record)
    assert post(client, "verify-email-confirm", {"token": token}).status_code == 204
    assert post(client, "verify-email-confirm", {"token": token}).status_code == 400
    assert VerifiedEmail.objects.get(user=user).address == "patient@example.com"
    old_session = APIClient()
    old_session.force_login(user)
    anonymous = APIClient(enforce_csrf_checks=True)
    assert post(anonymous, "reset-request", {"address": "patient@example.com"}).status_code == 202
    reset = AccountRecoveryRequest.objects.get(purpose="reset")
    assert post(anonymous, "reset-confirm", {"token": token_for(reset), "password": "New!83-River$Puzzle"}).status_code == 204
    assert post(anonymous, "reset-confirm", {"token": token_for(reset), "password": PASSWORD}).status_code == 400
    user.refresh_from_db()
    assert user.check_password("New!83-River$Puzzle")
    assert old_session.get(reverse("accounts:me")).status_code == 401


def test_unknown_and_unverified_addresses_are_generic():
    get_user_model().objects.create_user(username="legacy", password=PASSWORD, email="legacy@example.com")
    client = APIClient(enforce_csrf_checks=True)
    a = post(client, "reset-request", {"address": "missing@example.com"})
    b = post(client, "reset-request", {"address": "legacy@example.com"})
    assert a.status_code == b.status_code == 202
    assert a.data == b.data
    assert not AccountRecoveryRequest.objects.exists()


def test_expired_link_and_password_change_rejected():
    user = get_user_model().objects.create_user(username="expiry", password=PASSWORD)
    from .recovery import request_link
    record = request_link(user, "verify", "expiry@example.com")
    token = token_for(record)
    AccountRecoveryRequest.objects.filter(pk=record.pk).update(expires_at=timezone.now())
    assert post(APIClient(enforce_csrf_checks=True), "verify-email-confirm", {"token": token}).status_code == 400
    record = request_link(user, "verify", "expiry@example.com")
    user.set_password("Another!83-River$Puzzle")
    user.save()
    assert post(APIClient(enforce_csrf_checks=True), "verify-email-confirm", {"token": token_for(record)}).status_code == 400


def test_replacement_keeps_old_email_until_confirmed():
    user = get_user_model().objects.create_user(username="replace", password=PASSWORD)
    VerifiedEmail.objects.create(user=user, address="old@example.com", verified_at=timezone.now())
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user)
    assert post(client, "verify-email-request", {
        "address": "new@example.com", "current_password": PASSWORD,
    }).status_code == 202
    assert VerifiedEmail.objects.get(user=user).address == "old@example.com"
    record = AccountRecoveryRequest.objects.get()
    assert post(client, "verify-email-confirm", {"token": token_for(record)}).status_code == 204
    assert VerifiedEmail.objects.get(user=user).address == "new@example.com"


def test_request_failure_does_not_claim_success(monkeypatch):
    user = get_user_model().objects.create_user(username="failure", password=PASSWORD)
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user)
    def fail(*args, **kwargs):
        raise RuntimeError("database unavailable")
    monkeypatch.setattr("apps.accounts.views.request_link", fail)
    with pytest.raises(RuntimeError):
        post(client, "verify-email-request", {
            "address": "failure@example.com", "current_password": PASSWORD,
        })
    assert not AccountRecoveryRequest.objects.exists()
