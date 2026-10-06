import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError
from datetime import timedelta

from .models import AccountRecoveryRequest, VerifiedEmail
from .recovery import consume_link, request_link, token_for
from .tasks import _claim_email, _finish_email, dispatch_recovery_email

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
    assert old_session.get(reverse("accounts:me")).status_code == 403


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


def test_replacing_verified_email_revokes_old_reset_link():
    user = get_user_model().objects.create_user(username="replacement", password=PASSWORD)
    VerifiedEmail.objects.create(user=user, address="old@example.com", verified_at=timezone.now())
    old_reset = request_link(user, AccountRecoveryRequest.Purpose.RESET, "old@example.com")
    replacement = request_link(user, AccountRecoveryRequest.Purpose.VERIFY, "new@example.com")
    consume_link(token_for(replacement), AccountRecoveryRequest.Purpose.VERIFY)

    with pytest.raises(ValidationError):
        consume_link(token_for(old_reset), AccountRecoveryRequest.Purpose.RESET,
                     "New!83-River$Puzzle")
    user.refresh_from_db()
    assert user.check_password(PASSWORD)
    assert VerifiedEmail.objects.get(user=user).address == "new@example.com"


def test_new_verification_request_revokes_previous_link():
    user = get_user_model().objects.create_user(username="verify-twice", password=PASSWORD)
    first = request_link(user, AccountRecoveryRequest.Purpose.VERIFY, "first@example.com")
    second = request_link(user, AccountRecoveryRequest.Purpose.VERIFY, "second@example.com")

    with pytest.raises(ValidationError):
        consume_link(token_for(first), AccountRecoveryRequest.Purpose.VERIFY)
    consume_link(token_for(second), AccountRecoveryRequest.Purpose.VERIFY)
    assert VerifiedEmail.objects.get(user=user).address == "second@example.com"


def test_wrong_current_password_does_not_revoke_pending_link():
    user = get_user_model().objects.create_user(username="verify-password", password=PASSWORD)
    pending = request_link(user, AccountRecoveryRequest.Purpose.VERIFY, "first@example.com")
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user)
    response = post(client, "verify-email-request", {
        "address": "second@example.com", "current_password": "incorrect-password",
    })
    assert response.status_code == 400
    consume_link(token_for(pending), AccountRecoveryRequest.Purpose.VERIFY)
    assert VerifiedEmail.objects.get(user=user).address == "first@example.com"


def test_mail_claim_respects_backoff_and_fences_old_worker():
    user = get_user_model().objects.create_user(username="mail-race", password=PASSWORD)
    record = request_link(user, AccountRecoveryRequest.Purpose.VERIFY, "mail@example.com")
    record.state = AccountRecoveryRequest.State.FAILED
    record.attempts = 1
    record.next_attempt_at = timezone.now() + timedelta(minutes=10)
    record.save(update_fields=["state", "attempts", "next_attempt_at"])
    assert _claim_email(record.pk) is None

    AccountRecoveryRequest.objects.filter(pk=record.pk).update(next_attempt_at=timezone.now())
    old_claim = _claim_email(record.pk)
    assert old_claim.attempts == 2
    # Simulate lease recovery while the old worker is still delivering.
    AccountRecoveryRequest.objects.filter(pk=record.pk).update(
        state=AccountRecoveryRequest.State.FAILED,
        locked_at=None,
        next_attempt_at=timezone.now(),
    )
    new_claim = _claim_email(record.pk)
    assert new_claim.attempts == 3
    assert _finish_email(old_claim, sent=True) is False
    assert _finish_email(new_claim, sent=True) is True
    record.refresh_from_db()
    assert record.state == AccountRecoveryRequest.State.SENT


def test_failed_mail_waits_for_retry_time(monkeypatch):
    user = get_user_model().objects.create_user(username="mail-retry", password=PASSWORD)
    record = request_link(user, AccountRecoveryRequest.Purpose.VERIFY, "retry@example.com")
    def fail(_record):
        raise RuntimeError("mail backend unavailable")
    monkeypatch.setattr("apps.accounts.tasks.deliver_one", fail)
    assert dispatch_recovery_email() == 1
    record.refresh_from_db()
    assert record.state == AccountRecoveryRequest.State.FAILED
    assert record.attempts == 1
    assert record.next_attempt_at > timezone.now()
    assert dispatch_recovery_email() == 0
