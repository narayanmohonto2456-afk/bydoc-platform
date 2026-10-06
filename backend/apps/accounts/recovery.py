"""Single-use account links and durable local email delivery."""
import hashlib
from datetime import timedelta
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import AccountRecoveryRequest, User, VerifiedEmail


LINK_LIFETIME = timedelta(minutes=30)
SALT = "accounts.recovery.v1"


def fingerprint(user):
    return hashlib.sha256(user.password.encode()).hexdigest()


def token_for(record):
    return signing.dumps(str(record.pk), salt=SALT)


@transaction.atomic
def request_link(user, purpose, address):
    user = User.objects.select_for_update().get(pk=user.pk)
    if purpose == AccountRecoveryRequest.Purpose.VERIFY:
        AccountRecoveryRequest.objects.filter(
            user=user,
            purpose=AccountRecoveryRequest.Purpose.VERIFY,
            used_at__isnull=True,
        ).update(used_at=timezone.now())
    return AccountRecoveryRequest.objects.create(
        user=user, purpose=purpose, address=address,
        password_fingerprint=fingerprint(user),
        expires_at=timezone.now() + LINK_LIFETIME,
    )


def consume_link(token, purpose, password=None):
    try:
        request_id = signing.loads(token, salt=SALT, max_age=int(LINK_LIFETIME.total_seconds()))
    except (signing.BadSignature, signing.SignatureExpired):
        raise ValidationError({"token": "This link is invalid or expired."})
    # Lock the user first for consistent ordering with request creation and email replacement.
    try:
        record_user_id = AccountRecoveryRequest.objects.values_list("user_id", flat=True).get(pk=request_id)
    except (AccountRecoveryRequest.DoesNotExist, ValueError):
        raise ValidationError({"token": "This link is invalid or expired."})
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=record_user_id)
        record = AccountRecoveryRequest.objects.select_for_update().get(pk=request_id)
        if (record.purpose != purpose or record.used_at or record.expires_at <= timezone.now()
                or record.password_fingerprint != fingerprint(user) or not user.is_active):
            raise ValidationError({"token": "This link is invalid or expired."})
        if purpose == AccountRecoveryRequest.Purpose.VERIFY:
            existing = VerifiedEmail.objects.filter(address__iexact=record.address).exclude(user=user).exists()
            if existing:
                raise ValidationError({"token": "This email address is unavailable."})
            try:
                VerifiedEmail.objects.update_or_create(
                    user=user, defaults={"address": record.address, "verified_at": timezone.now()},
                )
            except IntegrityError:
                raise ValidationError({"token": "This email address is unavailable."})
        else:
            # Replacing a verified address revokes reset links sent to the old one.
            if not VerifiedEmail.objects.filter(
                user=user, address__iexact=record.address,
            ).exists():
                raise ValidationError({"token": "This link is invalid or expired."})
            if password is None:
                raise ValidationError({"password": "A new password is required."})
            try:
                validate_password(password, user=user)
            except DjangoValidationError as error:
                raise ValidationError({"password": error.messages}) from error
            user.set_password(password)
            user.save(update_fields=["password", "updated_at"])
            # Django's session auth hash invalidates all existing sessions.
        record.used_at = timezone.now()
        record.save(update_fields=["used_at"])
        return user


def deliver_one(record):
    if record.expires_at <= timezone.now() or record.used_at:
        return
    base = settings.ACCOUNT_LINK_BASE_URL.rstrip("/")
    path = "verify-email" if record.purpose == AccountRecoveryRequest.Purpose.VERIFY else "reset-password"
    url = f"{base}/{path}#token={quote(token_for(record))}"
    subject = "Verify your SehatSaathi email" if record.purpose == AccountRecoveryRequest.Purpose.VERIFY else "Reset your SehatSaathi password"
    send_mail(subject, f"Open this link within 30 minutes: {url}", settings.DEFAULT_FROM_EMAIL, [record.address])
