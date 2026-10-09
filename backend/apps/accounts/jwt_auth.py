"""Short-lived access JWTs and revocable, rotating refresh credentials."""

import hashlib
import secrets
import uuid
from datetime import timedelta

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework.authentication import BaseAuthentication, SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import AuthSession


ACCESS_LIFETIME = timedelta(minutes=10)
REFRESH_LIFETIME = timedelta(days=30)
ISSUER = "bydoc"
AUDIENCE = "bydoc-api"
User = get_user_model()


def signing_key():
    return salted_hmac("bydoc-jwt-access-v1", "signing", secret=settings.SECRET_KEY).hexdigest()


def refresh_digest(raw):
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def access_token(user, session):
    now = timezone.now()
    return jwt.encode({
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": str(user.pk),
        "sid": str(session.pk),
        "iat": now,
        "nbf": now,
        "exp": now + ACCESS_LIFETIME,
        "auth_hash": user.get_session_auth_hash(),
    }, signing_key(), algorithm="HS256")


def new_credentials(user):
    secret = secrets.token_urlsafe(48)
    session = AuthSession.objects.create(
        user=user,
        refresh_hash=refresh_digest(secret),
        auth_hash=user.get_session_auth_hash(),
        expires_at=timezone.now() + REFRESH_LIFETIME,
    )
    return access_token(user, session), f"{session.pk}.{secret}", session


def rotate_credentials(raw):
    try:
        session_id, secret = raw.split(".", 1)
        session_id = uuid.UUID(session_id)
    except (ValueError, AttributeError):
        raise AuthenticationFailed("Refresh credential is invalid.")
    from django.db import transaction

    with transaction.atomic():
        session = AuthSession.objects.select_for_update().select_related("user").filter(pk=session_id).first()
        if session is None or session.revoked_at is not None:
            raise AuthenticationFailed("Refresh credential is invalid.")
        valid_secret = constant_time_compare(session.refresh_hash, refresh_digest(secret))
        valid_account = (
            session.expires_at > timezone.now() and session.user.is_active
            and constant_time_compare(session.auth_hash, session.user.get_session_auth_hash())
        )
        if not valid_secret or not valid_account:
            session.revoked_at = timezone.now()
            session.save(update_fields=["revoked_at"])
        else:
            new_secret = secrets.token_urlsafe(48)
            session.refresh_hash = refresh_digest(new_secret)
            session.last_used_at = timezone.now()
            session.save(update_fields=["refresh_hash", "last_used_at"])
            return access_token(session.user, session), f"{session.pk}.{new_secret}", session
    raise AuthenticationFailed("Refresh credential is invalid.")


def set_auth_cookies(response, access, refresh):
    options = {"httponly": True, "secure": settings.SESSION_COOKIE_SECURE, "samesite": "Lax", "path": "/"}
    response.set_cookie(settings.AUTH_ACCESS_COOKIE_NAME, access, max_age=int(ACCESS_LIFETIME.total_seconds()), **options)
    response.set_cookie(settings.AUTH_REFRESH_COOKIE_NAME, refresh, max_age=int(REFRESH_LIFETIME.total_seconds()), **options)


def clear_auth_cookies(response):
    response.delete_cookie(settings.AUTH_ACCESS_COOKIE_NAME, path="/", samesite="Lax")
    response.delete_cookie(settings.AUTH_REFRESH_COOKIE_NAME, path="/", samesite="Lax")


class JWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        header = request.headers.get("Authorization", "")
        cookie_token = request.COOKIES.get(settings.AUTH_ACCESS_COOKIE_NAME)
        if header:
            kind, _, token = header.partition(" ")
            if kind.lower() != "bearer" or not token:
                raise AuthenticationFailed("Invalid authorization header.")
        elif cookie_token:
            token = cookie_token
            # Cookies are ambient credentials, so unsafe methods require CSRF.
            SessionAuthentication().enforce_csrf(request)
        else:
            return None
        try:
            claims = jwt.decode(
                token, signing_key(), algorithms=["HS256"], audience=AUDIENCE, issuer=ISSUER,
                options={"require": ["iss", "aud", "sub", "sid", "iat", "nbf", "exp", "auth_hash"]},
            )
            user_id = uuid.UUID(claims["sub"])
            session_id = uuid.UUID(claims["sid"])
        except (jwt.PyJWTError, ValueError, KeyError, TypeError):
            raise AuthenticationFailed("Access credential is invalid or expired.")
        session = AuthSession.objects.select_related("user").filter(pk=session_id, user_id=user_id).first()
        if (session is None or session.revoked_at is not None or session.expires_at <= timezone.now()
                or not session.user.is_active
                or not constant_time_compare(claims["auth_hash"], session.user.get_session_auth_hash())):
            raise AuthenticationFailed("Access credential is invalid or expired.")
        return session.user, session

    def authenticate_header(self, request):
        return "Bearer"


class LegacySessionAuthentication(SessionAuthentication):
    """Keep old test fixtures working; production API accepts JWT only."""

    def authenticate(self, request):
        if not settings.API_LEGACY_SESSION_AUTH:
            return None
        return super().authenticate(request)
