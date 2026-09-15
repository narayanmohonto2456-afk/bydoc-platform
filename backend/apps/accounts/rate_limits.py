"""Shared fixed-window authentication limits, with atomic Redis counters."""
from time import time

from django.conf import settings
from django.core.cache import caches
from django.utils.crypto import salted_hmac
from rest_framework.exceptions import APIException, Throttled


class AuthenticationTemporarilyUnavailable(APIException):
    status_code = 503
    default_detail = "Sign-in and registration are temporarily unavailable. Please try again later."
    default_code = "authentication_temporarily_unavailable"


def consume_limit(scope, identity):
    limit, seconds = settings.AUTH_RATE_LIMITS[scope]
    now = time()
    bucket = int(now // seconds)
    digest = salted_hmac("authentication-rate-limit", str(identity)).hexdigest()
    key = f"{scope}:{bucket}:{digest}"
    try:
        cache = caches["authentication"]
        # RedisCache.incr is atomic. Keep the bucket past its active window.
        cache.add(key, 0, timeout=seconds * 2)
        count = cache.incr(key)
    except Exception as error:
        raise AuthenticationTemporarilyUnavailable() from error
    if count > limit:
        raise Throttled(wait=max(1, (bucket + 1) * seconds - now))


def client_address(request):
    # Ignore spoofable forwarded headers until a trusted proxy is configured.
    return request.META.get("REMOTE_ADDR") or "unknown"
