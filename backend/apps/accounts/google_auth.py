"""Validate Google identity tokens and bind stable Google subjects to users."""

import secrets
from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils import timezone
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from rest_framework.exceptions import APIException, ValidationError

from .models import GoogleIdentity, VerifiedEmail


User = get_user_model()


class GoogleAccountConflict(APIException):
    status_code = 409
    default_detail = (
        "This email already belongs to an account. Sign in with your password "
        "and connect Google from your account."
    )
    default_code = "google_account_conflict"


class GoogleNotConfigured(APIException):
    status_code = 503
    default_detail = "Google sign-in is not configured yet."
    default_code = "google_not_configured"


@dataclass(frozen=True)
class GoogleClaims:
    subject: str
    email: str
    first_name: str
    last_name: str


def verify_google_credential(credential: str) -> GoogleClaims:
    client_id = settings.GOOGLE_OAUTH_CLIENT_ID
    if not client_id:
        raise GoogleNotConfigured()
    transport = Request()

    def bounded_request(*args, **kwargs):
        kwargs["timeout"] = 5
        return transport(*args, **kwargs)

    try:
        claims = id_token.verify_oauth2_token(credential, bounded_request, client_id)
    except (ValueError, GoogleAuthError) as error:
        raise ValidationError({"credential": "Google sign-in could not be verified."}) from error

    subject = claims.get("sub")
    address = claims.get("email")
    if (not isinstance(subject, str) or not subject.strip() or len(subject) > 255
            or not isinstance(address, str) or claims.get("email_verified") is not True):
        raise ValidationError({"credential": "Google sign-in could not be verified."})

    email = address.strip().casefold()
    try:
        validate_email(email)
    except DjangoValidationError as error:
        raise ValidationError({"credential": "Google sign-in could not be verified."}) from error
    if len(email) > 254:
        raise ValidationError({"credential": "Google sign-in could not be verified."})

    # Google is authoritative for Gmail and Workspace addresses. A Google
    # account using a third-party email may no longer control that mailbox.
    domain = email.rsplit("@", 1)[1]
    hosted_domain = claims.get("hd")
    if domain not in {"gmail.com", "googlemail.com"} and (
        not isinstance(hosted_domain, str) or hosted_domain.casefold() != domain
    ):
        raise ValidationError({
            "credential": "Use a Gmail or Google Workspace account for Google sign-in."
        })

    first_name = claims.get("given_name")
    last_name = claims.get("family_name")
    return GoogleClaims(
        subject=subject,
        email=email,
        first_name=first_name[:150] if isinstance(first_name, str) else "",
        last_name=last_name[:150] if isinstance(last_name, str) else "",
    )


def google_sign_in(claims: GoogleClaims):
    identity = GoogleIdentity.objects.select_related("user").filter(subject=claims.subject).first()
    if identity:
        if not identity.user.is_active:
            raise ValidationError({"credential": "Unable to sign in with this Google account."})
        return identity.user

    try:
        with transaction.atomic():
            if (VerifiedEmail.objects.filter(address__iexact=claims.email).exists()
                    or User.objects.filter(email__iexact=claims.email).exists()):
                raise GoogleAccountConflict()
            user = User.objects.create_user(
                username=f"google_{secrets.token_hex(12)}",
                password=None,
                first_name=claims.first_name,
                last_name=claims.last_name,
                is_staff=False,
                is_superuser=False,
            )
            VerifiedEmail.objects.create(
                user=user, address=claims.email, verified_at=timezone.now(),
            )
            GoogleIdentity.objects.create(user=user, subject=claims.subject)
            return user
    except IntegrityError as error:
        identity = GoogleIdentity.objects.select_related("user").filter(subject=claims.subject).first()
        if identity and identity.user.is_active:
            return identity.user
        raise GoogleAccountConflict() from error


def link_google_identity(user, claims: GoogleClaims) -> None:
    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        if not locked_user.is_active:
            raise ValidationError({"credential": "Unable to connect this Google account."})
        if not VerifiedEmail.objects.filter(
            user=locked_user, address__iexact=claims.email,
        ).exists():
            raise ValidationError({
                "credential": "Verify this email address from your account before connecting Google."
            })
        existing = GoogleIdentity.objects.filter(user=locked_user).first()
        if existing:
            if existing.subject == claims.subject:
                return
            raise GoogleAccountConflict()
        try:
            GoogleIdentity.objects.create(user=locked_user, subject=claims.subject)
        except IntegrityError as error:
            raise GoogleAccountConflict() from error
