from pathlib import Path

import environ


BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = BASE_DIR.parent

env = environ.Env(
    APP_DEBUG=(bool, False),
)

environment_file = PROJECT_ROOT / ".env"

if environment_file.exists():
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
    "apps.notifications",
    "apps.support.apps.SupportConfig",
    "apps.preferences.apps.PreferencesConfig",
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
        "NAME": env("POSTGRES_DB", default="sehatsaathi"),
        "USER": env("POSTGRES_USER", default="sehatsaathi"),
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
        "rest_framework.authentication.SessionAuthentication",
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

SPECTACULAR_SETTINGS = {
    "TITLE": "SehatSaathi API",
    "DESCRIPTION": "SehatSaathi platform API",
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

# Browser sessions for the patient-facing API.
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
}
