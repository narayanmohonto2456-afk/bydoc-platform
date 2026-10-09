"""Fail-closed settings for a TLS-terminating, trusted production deployment."""

import os
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from django.core.exceptions import ImproperlyConfigured

from .base import *


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ImproperlyConfigured(f"{name} is required in production.")
    return value


def required_list(name):
    values = [item.strip() for item in required(name).split(",")]
    if any(not item for item in values):
        raise ImproperlyConfigured(f"{name} contains an empty value.")
    return values


def https_origin(value, name):
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or "*" in parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ImproperlyConfigured(f"{name} must contain HTTPS origins only.")
    if parsed.hostname in {"localhost", "127.0.0.1"}:
        raise ImproperlyConfigured(f"{name} cannot use a local host in production.")


DEBUG = False
SECRET_KEY = required("DJANGO_SECRET_KEY")
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith("unsafe-"):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be a strong production-only secret.")

ALLOWED_HOSTS = required_list("APP_ALLOWED_HOSTS")
if any("*" in host or "://" in host or "/" in host or ":" in host or host.startswith(".") or host in {"localhost", "127.0.0.1"} for host in ALLOWED_HOSTS):
    raise ImproperlyConfigured("APP_ALLOWED_HOSTS must list exact production hostnames.")

CORS_ALLOWED_ORIGINS = required_list("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = required_list("CSRF_TRUSTED_ORIGINS")
for name, origins in (("CORS_ALLOWED_ORIGINS", CORS_ALLOWED_ORIGINS), ("CSRF_TRUSTED_ORIGINS", CSRF_TRUSTED_ORIGINS)):
    for origin in origins:
        https_origin(origin, name)

ACCOUNT_LINK_BASE_URL = required("ACCOUNT_LINK_BASE_URL").rstrip("/")
https_origin(ACCOUNT_LINK_BASE_URL, "ACCOUNT_LINK_BASE_URL")
if ACCOUNT_LINK_BASE_URL not in CORS_ALLOWED_ORIGINS or ACCOUNT_LINK_BASE_URL not in CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured("ACCOUNT_LINK_BASE_URL must be a trusted frontend origin.")

database_ca_bundle = required("POSTGRES_SSLROOTCERT")
if not Path(database_ca_bundle).is_file():
    raise ImproperlyConfigured("POSTGRES_SSLROOTCERT must point to an existing CA bundle.")

DATABASES["default"].update({
    "NAME": required("POSTGRES_DB"),
    "USER": required("POSTGRES_USER"),
    "PASSWORD": required("POSTGRES_PASSWORD"),
    "HOST": required("POSTGRES_HOST"),
    "PORT": required("POSTGRES_PORT"),
    "CONN_HEALTH_CHECKS": True,
    "OPTIONS": {"sslmode": "verify-full", "sslrootcert": database_ca_bundle, "connect_timeout": 3},
})

REDIS_URL = required("REDIS_URL")
redis_url = urlsplit(REDIS_URL)
if redis_url.scheme != "rediss" or not redis_url.hostname or not redis_url.password or parse_qs(redis_url.query).get("ssl_cert_reqs") != ["required"]:
    raise ImproperlyConfigured("REDIS_URL must use authenticated TLS with ssl_cert_reqs=required.")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CACHES["authentication"]["LOCATION"] = REDIS_URL

EMAIL_BACKEND = required("EMAIL_BACKEND")
if EMAIL_BACKEND != "django.core.mail.backends.smtp.EmailBackend":
    raise ImproperlyConfigured("Production email requires the Django SMTP backend.")
EMAIL_HOST = required("EMAIL_HOST")
try:
    EMAIL_PORT = int(required("EMAIL_PORT"))
except ValueError as error:
    raise ImproperlyConfigured("EMAIL_PORT must be an integer.") from error
if not 1 <= EMAIL_PORT <= 65535:
    raise ImproperlyConfigured("EMAIL_PORT is out of range.")
EMAIL_HOST_USER = required("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = required("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "False").lower() == "true"
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "False").lower() == "true"
if EMAIL_USE_TLS == EMAIL_USE_SSL:
    raise ImproperlyConfigured("Choose exactly one of EMAIL_USE_TLS or EMAIL_USE_SSL.")
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = required("DEFAULT_FROM_EMAIL")

if OTP_SMS_ENABLED:
    AWS_SMS_REGION = required("AWS_SMS_REGION")
    AWS_SMS_ORIGINATION_ID = required("AWS_SMS_ORIGINATION_ID")
    AWS_SMS_ENTITY_ID = required("AWS_SMS_ENTITY_ID")
    AWS_SMS_LOGIN_TEMPLATE_ID = required("AWS_SMS_LOGIN_TEMPLATE_ID")
    AWS_SMS_VERIFY_TEMPLATE_ID = required("AWS_SMS_VERIFY_TEMPLATE_ID")

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_NAME = "__Host-bydoc-session"
AUTH_ACCESS_COOKIE_NAME = "__Host-bydoc-access"
AUTH_REFRESH_COOKIE_NAME = "__Host-bydoc-refresh"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_NAME = "__Host-bydoc-csrf"
X_FRAME_OPTIONS = "DENY"
MIDDLEWARE.insert(0, "apps.core.middleware.PrivateHealthCheckMiddleware")
MIDDLEWARE.insert(2, "whitenoise.middleware.WhiteNoiseMiddleware")
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Enable only when the edge strips client-supplied X-Forwarded-Proto and sets it
# from the actual TLS connection. Otherwise forwarded headers are untrusted.
if os.environ.get("TRUSTED_PROXY_SSL_HEADER", "False").lower() == "true":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if AI_CHAT_ENABLED:
    OLLAMA_BASE_URL = required("OLLAMA_BASE_URL").rstrip("/")
    model_url = urlsplit(OLLAMA_BASE_URL)
    if model_url.scheme not in {"http", "https"} or not model_url.hostname or model_url.username or model_url.password or model_url.path or model_url.query or model_url.fragment:
        raise ImproperlyConfigured("OLLAMA_BASE_URL must be a private Ollama origin.")
    try:
        address = ip_address(model_url.hostname)
        private_model_host = address.is_private and not address.is_loopback and not address.is_link_local
    except ValueError:
        private_model_host = model_url.hostname.endswith((".internal", ".local")) or (
            model_url.hostname.startswith("internal-") and model_url.hostname.endswith(".elb.amazonaws.com")
        )
    if not private_model_host:
        raise ImproperlyConfigured("Production Ollama must run on a separate private service.")
    OLLAMA_MODEL = required("OLLAMA_MODEL")
