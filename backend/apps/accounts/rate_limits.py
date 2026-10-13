"""Shared fixed-window authentication limits, with atomic Redis counters."""
from ipaddress import ip_address
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
    if settings.AUTH_TRUST_FORWARDED_CLIENT_IP:
        # Only enable when the edge replaces the first entry with the actual
        # client address. Invalid/missing headers fall back to the proxy IP.
        candidate = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",", 1)[0].strip()
        try:
            return str(ip_address(candidate))
        except ValueError:
            pass
    return request.META.get("REMOTE_ADDR") or "unknown"
