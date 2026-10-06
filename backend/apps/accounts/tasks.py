"""Database-backed account mail dispatcher. A crash after sending may duplicate mail."""
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import AccountRecoveryRequest as Request
from .recovery import deliver_one


MAX_ATTEMPTS = 5


@transaction.atomic
def _claim_email(pk):
    record = Request.objects.select_for_update().filter(pk=pk).first()
    if record is None:
        return None
    now = timezone.now()
    if (
        record.state not in (Request.State.PENDING, Request.State.FAILED)
        or record.used_at is not None
        or record.expires_at <= now
        or record.attempts >= MAX_ATTEMPTS
        or (record.next_attempt_at is not None and record.next_attempt_at > now)
    ):
        return None
    record.state = Request.State.PROCESSING
    record.attempts += 1
    record.locked_at = now
    record.next_attempt_at = None
    record.save(update_fields=["state", "attempts", "locked_at", "next_attempt_at"])
    return record


@transaction.atomic
def _finish_email(claim, *, sent):
    record = Request.objects.select_for_update().filter(pk=claim.pk).first()
    if record is None:
        return False
    # A stale worker must not finish a newer attempt after lease recovery.
    if (
        record.state != Request.State.PROCESSING
        or record.attempts != claim.attempts
        or record.locked_at != claim.locked_at
    ):
        return False
    record.locked_at = None
    if sent:
        record.state = Request.State.SENT
        record.next_attempt_at = None
    else:
        record.state = Request.State.FAILED
        record.next_attempt_at = timezone.now() + timedelta(minutes=2 ** record.attempts)
    record.save(update_fields=["state", "locked_at", "next_attempt_at"])
    return True


@shared_task(name="accounts.dispatch_recovery_email")
def dispatch_recovery_email(batch_size=50):
    now = timezone.now()
    batch_size = max(1, min(int(batch_size), 500))
    ids = list(
        Request.objects.filter(
            state__in=[Request.State.PENDING, Request.State.FAILED],
            expires_at__gt=now,
            attempts__lt=MAX_ATTEMPTS,
            used_at__isnull=True,
        ).filter(
            Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now)
        ).order_by("created_at", "pk").values_list("pk", flat=True)[:batch_size]
    )
    for pk in ids:
        claim = _claim_email(pk)
        if claim is None:
            continue
        try:
            deliver_one(claim)
        except Exception:
            _finish_email(claim, sent=False)
        else:
            _finish_email(claim, sent=True)
    return len(ids)


@shared_task(name="accounts.recover_stale_recovery_email")
def recover_stale_recovery_email():
    return Request.objects.filter(
        state=Request.State.PROCESSING,
        locked_at__lt=timezone.now() - timedelta(minutes=15),
    ).update(state=Request.State.FAILED, locked_at=None, next_attempt_at=timezone.now())
