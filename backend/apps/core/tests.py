from unittest.mock import patch

import pytest
from redis.exceptions import RedisError


def test_liveness_returns_ok(client):
    response = client.get("/health/live/")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "sehatsaathi-api",
    }


@pytest.mark.django_db
@patch("apps.core.views.Redis.from_url")
def test_readiness_returns_ready(
    mocked_redis_from_url,
    client,
):
    mocked_redis_from_url.return_value.ping.return_value = True

    response = client.get("/health/ready/")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {
            "database": "ok",
            "redis": "ok",
        },
    }


@pytest.mark.django_db
@patch("apps.core.views.Redis.from_url")
def test_readiness_fails_safely_when_redis_is_unavailable(
    mocked_redis_from_url,
    client,
):
    mocked_redis_from_url.side_effect = RedisError(
        "Redis unavailable"
    )

    response = client.get("/health/ready/")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "checks": {
            "database": "ok",
            "redis": "unavailable",
        },
    }