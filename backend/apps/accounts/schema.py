"""OpenAPI security schemes for the production JWT and test-only session auth."""

from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class JWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "apps.accounts.jwt_auth.JWTAuthentication"
    name = ["jwtCookie", "jwtBearer"]

    def get_security_requirement(self, auto_schema):
        return [{"jwtCookie": []}, {"jwtBearer": []}]

    def get_security_definition(self, auto_schema):
        return [
            {
                "type": "apiKey", "in": "cookie", "name": settings.AUTH_ACCESS_COOKIE_NAME,
                "description": "Short-lived HttpOnly JWT cookie. Unsafe requests also require a CSRF token.",
            },
            {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
        ]


class LegacySessionScheme(OpenApiAuthenticationExtension):
    target_class = "apps.accounts.jwt_auth.LegacySessionAuthentication"
    name = "legacySession"

    def get_security_requirement(self, auto_schema):
        return {self.name: []} if settings.API_LEGACY_SESSION_AUTH else None

    def get_security_definition(self, auto_schema):
        return {"type": "apiKey", "in": "cookie", "name": settings.SESSION_COOKIE_NAME}
