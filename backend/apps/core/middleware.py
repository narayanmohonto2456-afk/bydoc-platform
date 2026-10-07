"""Minimal health responses for private AWS load balancer target checks."""

from django.http import JsonResponse

from .views import liveness, readiness


class PrivateHealthCheckMiddleware:
    """Answer health checks before host and HTTPS validation.

    AWS ALB sends the target's private IP as Host over HTTP. Only these
    exact, data-free GET endpoints bypass the normal security middleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "GET" and request.path == "/health/live/":
            return liveness(request)
        if request.method == "GET" and request.path == "/health/ready/":
            response = readiness(request)
            return JsonResponse(
                {"status": "ready" if response.status_code == 200 else "unavailable"},
                status=response.status_code,
            )
        return self.get_response(request)
