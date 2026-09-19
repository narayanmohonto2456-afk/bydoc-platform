from .development import *  # noqa: F403


PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

DATABASES["default"].update(  # noqa: F405
    {
        "HOST": "127.0.0.1",
        "CONN_MAX_AGE": 0,
        "CONN_HEALTH_CHECKS": False,
    }
)

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Tests isolate auth counters without requiring a running Redis service.
CACHES["authentication"] = {  # noqa: F405
    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    "LOCATION": "authentication-tests",
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
