from .base import *  # noqa: F403


DEBUG = True

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
]

# Both loopback addresses are supported by the local frontend. Production keeps
# its exact, explicitly configured origin lists in production.py.
LOCAL_FRONTEND_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
CORS_ALLOWED_ORIGINS = list(dict.fromkeys([*CORS_ALLOWED_ORIGINS, *LOCAL_FRONTEND_ORIGINS]))  # noqa: F405
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys([*CSRF_TRUSTED_ORIGINS, *LOCAL_FRONTEND_ORIGINS]))  # noqa: F405
