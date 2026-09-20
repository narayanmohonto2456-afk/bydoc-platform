"""Database-backed account mail dispatcher. Duplicate email delivery is possible after a crash."""
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import AccountRecoveryRequest as Request
from .recovery import deliver_one


@shared_task(name="accounts.dispatch_recovery_email")
def dispatch_recovery_email(batch_size=50):
    now = timezone.now()
    ids = list(Request.objects.filter(
        state__in=[Request.State.PENDING, Request.State.FAILED],
        expires_at__gt=now, attempts__lt=5,
    ).filter(next_attempt_at__isnull=True).values_list("pk", flat=True)[:batch_size])
    ids += list(Request.objects.filter(
        state= Request.State.FAILED, next_attempt_at__lte=now,
        expires_at__gt=now, attempts__lt=5,
    ).values_list("pk", flat=True)[:max(0, batch_size-len(ids))])
    for pk in ids:
        with transaction.atomic():
            record = Request.objects.select_for_update().get(pk=pk)
            if record.state not in [Request.State.PENDING, Request.State.FAILED] or record.used_at or record.expires_at <= timezone.now():
                continue
            record.state = Request.State.PROCESSING
            record.attempts += 1
            record.locked_at = timezone.now()
            record.save(update_fields=["state", "attempts", "locked_at"])
        try:
            deliver_one(record)
        except Exception:
            with transaction.atomic():
                record = Request.objects.select_for_update().get(pk=pk)
                record.state = Request.State.FAILED
                record.locked_at = None
                record.next_attempt_at = timezone.now() + timedelta(minutes=2 ** record.attempts)
                record.save(update_fields=["state", "locked_at", "next_attempt_at"])
        else:
            Request.objects.filter(pk=pk, state=Request.State.PROCESSING).update(
                state=Request.State.SENT, locked_at=None, next_attempt_at=None,
            )
    return len(ids)


@shared_task(name="accounts.recover_stale_recovery_email")
def recover_stale_recovery_email():
    return Request.objects.filter(
        state=Request.State.PROCESSING,
        locked_at__lt=timezone.now() - timedelta(minutes=15),
    ).update(state=Request.State.FAILED, locked_at=None, next_attempt_at=timezone.now())
