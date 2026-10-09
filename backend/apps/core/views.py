from django.conf import settings
from django.db import connections
from django.db.utils import OperationalError
from django.http import JsonResponse
from redis import Redis
from redis.exceptions import RedisError


def liveness(request):
    """
    Confirms that the Django process is running.

    It intentionally does not query PostgreSQL or Redis.
    """

    return JsonResponse(
        {
            "status": "ok",
            "service": "bydoc-api",
        }
    )


def readiness(request):
    """
    Confirms that the API can reach its critical dependencies.
    """

    checks = {
        "database": "unavailable",
        "redis": "unavailable",
    }

    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
    except OperationalError:
        pass

    try:
        redis_client = Redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=1,
            socket_timeout=1,
        )

        if redis_client.ping():
            checks["redis"] = "ok"
    except RedisError:
        pass

    is_ready = all(
        result == "ok"
        for result in checks.values()
    )

    return JsonResponse(
        {
            "status": "ready" if is_ready else "unavailable",
            "checks": checks,
        },
        status=200 if is_ready else 503,
    )