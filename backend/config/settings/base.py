import os
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = BASE_DIR.parent

env = environ.Env(
    APP_DEBUG=(bool, False),
)

environment_file = PROJECT_ROOT / ".env"

if environment_file.exists() and os.environ.get("DJANGO_SETTINGS_MODULE") != "config.settings.production":
    environ.Env.read_env(environment_file)


SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="unsafe-development-key-change-before-production",
)

DEBUG = env("APP_DEBUG")

ALLOWED_HOSTS = env.list(
    "APP_ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1"],
)


DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
]

LOCAL_APPS = [
    "apps.accounts.apps.AccountsConfig",
    "apps.core.apps.CoreConfig",
    "apps.organizations.apps.OrganizationsConfig",
    "apps.clinics",
    "apps.doctors",
    "apps.appointments",
    "apps.payments.apps.PaymentsConfig",
    "apps.onboarding.apps.OnboardingConfig",
    "apps.notifications",
    "apps.support.apps.SupportConfig",
    "apps.preferences.apps.PreferencesConfig",
    "apps.chatbot.apps.ChatbotConfig",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    (
        "apps.preferences.middleware."
        "UserPreferenceLocaleMiddleware"
    ),
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", default="bydoc"),
        "USER": env("POSTGRES_USER", default="bydoc"),
        "PASSWORD": env(
            "POSTGRES_PASSWORD",
            default="local-development-password",
        ),
        "HOST": env("POSTGRES_HOST", default="localhost"),
        "PORT": env("POSTGRES_PORT", default="5432"),
        "CONN_MAX_AGE": 60,
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


LANGUAGE_CODE = "en"

LANGUAGES = (
    ("en", "English"),
    ("bn", "বাংলা"),
    ("hi", "हिन्दी"),
)

TIME_ZONE = "UTC"

USE_I18N = True
USE_TZ = True

LOCALE_PATHS = [
    BASE_DIR / "locale",
]


STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.jwt_auth.JWTAuthentication",
        "apps.accounts.jwt_auth.LegacySessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": (
        "drf_spectacular.openapi.AutoSchema"
    ),
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

API_LEGACY_SESSION_AUTH = False
AUTH_ACCESS_COOKIE_NAME = "bydoc-access"
AUTH_REFRESH_COOKIE_NAME = "bydoc-refresh"

SPECTACULAR_SETTINGS = {
    "TITLE": "BYdoc API",
    "DESCRIPTION": "BYdoc platform API",
    "VERSION": "1.0.0",
    "ENUM_NAME_OVERRIDES": {
        "AppointmentStatusEnum": [
            ("confirmed", "Confirmed"),
            ("checked_in", "Checked in"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
            ("no_show", "No show"),
        ],
        "SupportCaseStatusEnum": [
            ("open", "Open"),
            ("in_progress", "In progress"),
            ("waiting_for_user", "Waiting for user"),
            ("resolved", "Resolved"),
            ("closed", "Closed"),
        ],
    },
}


CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:3000"],
)

CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=["http://localhost:3000"],
)


REDIS_URL = env(
    "REDIS_URL",
    default="redis://localhost:6379/0",
)

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"

CELERY_BEAT_SCHEDULE = {
    "reconcile-payments-every-minute": {
        "task": "payments.reconcile", "schedule": 60.0,
    },
    "dispatch-otp-every-ten-seconds": {
        "task": "accounts.dispatch_otp", "schedule": 10.0,
    },
    "recover-stale-otp-every-minute": {
        "task": "accounts.recover_stale_otp", "schedule": 60.0,
    },
    "dispatch-recovery-email-every-minute": {
        "task": "accounts.dispatch_recovery_email", "schedule": 60.0,
    },
    "recover-stale-recovery-email-every-five-minutes": {
        "task": "accounts.recover_stale_recovery_email", "schedule": 300.0,
    },
    "dispatch-due-notifications-every-minute": {
        "task": (
            "notifications.dispatch_due_notifications"
        ),
        "schedule": 60.0,
        "args": (100,),
    },
    "recover-stale-notifications-every-five-minutes": {
        "task": (
            "notifications.recover_stale_notifications"
        ),
        "schedule": 300.0,
        "args": (100, 15),
    },
}


APPOINTMENT_HOLD_MINUTES = 5

# Razorpay Route requires an approved platform account and linked clinic accounts.
RAZORPAY_KEY_ID = env("RAZORPAY_KEY_ID", default="")
RAZORPAY_KEY_SECRET = env("RAZORPAY_KEY_SECRET", default="")
RAZORPAY_WEBHOOK_SECRET = env("RAZORPAY_WEBHOOK_SECRET", default="")
RAZORPAY_PAYMENTS_ENABLED = env.bool("RAZORPAY_PAYMENTS_ENABLED", default=False)

# Django sessions remain available for the admin site; API clients use JWT.
CORS_ALLOW_CREDENTIALS = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 12 * 60 * 60

# Shared counters across Django workers. Redis outages fail closed for auth.
CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "authentication": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": "authentication",
        "OPTIONS": {"socket_connect_timeout": 2, "socket_timeout": 2},
    },
}
AUTH_RATE_LIMITS = {
    "login_ip": (30, 60),
    "login_account": (10, 300),
    "register_ip": (5, 3600),
    "verify_ip": (10, 3600),
    "verify_user": (5, 3600),
    "reset_ip": (10, 3600),
    "reset_address": (5, 3600),
    "confirm_ip": (30, 3600),
    "otp_request_ip": (10, 3600),
    "otp_destination": (3, 900),
    "otp_confirm_ip": (20, 900),
    "otp_confirm_destination": (10, 900),
}

ACCOUNT_LINK_BASE_URL = env("ACCOUNT_LINK_BASE_URL", default="http://localhost:3000")
GOOGLE_OAUTH_CLIENT_ID = env("GOOGLE_OAUTH_CLIENT_ID", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="BYdoc <noreply@localhost>")
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.filebased.EmailBackend")
EMAIL_FILE_PATH = env("EMAIL_FILE_PATH", default=str(BASE_DIR / "local-email"))

# Product guidance remains available when the optional local classifier is off.
# The model never receives account, appointment, or profile records automatically.
ASSISTANT_ENABLED = env.bool("ASSISTANT_ENABLED", default=True)
AI_CHAT_ENABLED = env.bool("AI_CHAT_ENABLED", default=False)
OLLAMA_BASE_URL = env("OLLAMA_BASE_URL", default="http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = env("OLLAMA_MODEL", default="llama3.2:3b")

OTP_SMS_ENABLED = env.bool("OTP_SMS_ENABLED", default=False)
AWS_SMS_REGION = env("AWS_SMS_REGION", default="")
AWS_SMS_ORIGINATION_ID = env("AWS_SMS_ORIGINATION_ID", default="")
AWS_SMS_ENTITY_ID = env("AWS_SMS_ENTITY_ID", default="")
AWS_SMS_LOGIN_TEMPLATE_ID = env("AWS_SMS_LOGIN_TEMPLATE_ID", default="")
AWS_SMS_VERIFY_TEMPLATE_ID = env("AWS_SMS_VERIFY_TEMPLATE_ID", default="")
