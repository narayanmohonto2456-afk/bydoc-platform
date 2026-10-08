"""Shared submission limit for patient support requests."""

from time import time

from django.core.cache import caches
from django.utils.crypto import salted_hmac
from rest_framework.exceptions import APIException, Throttled


class SupportUnavailable(APIException):
    status_code = 503
    default_detail = "Support requests are temporarily unavailable. Please try again later."
    default_code = "support_unavailable"


def limit_support_submission(user_id):
    seconds = 3600
    limit = 5
    now = time()
    bucket = int(now // seconds)
    digest = salted_hmac("support-submission-limit", str(user_id)).hexdigest()
    key = f"support-submission:{bucket}:{digest}"
    try:
        cache = caches["authentication"]
        cache.add(key, 0, timeout=seconds * 2)
        count = cache.incr(key)
    except Exception as error:
        raise SupportUnavailable() from error
    if count > limit:
        raise Throttled(wait=max(1, (bucket + 1) * seconds - now))
