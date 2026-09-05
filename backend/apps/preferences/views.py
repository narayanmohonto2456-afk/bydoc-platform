from django.conf import settings
from django.db import transaction
from django.utils import translation
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response

from .models import UserPreference
from .serializers import (
    SupportedLanguageSerializer,
    UserPreferenceSerializer,
)


class SupportedLanguageListView(
    generics.GenericAPIView
):
    """
    Public read-only list of interface languages.
    """

    permission_classes = (permissions.AllowAny,)
    serializer_class = SupportedLanguageSerializer

    @extend_schema(
        responses=SupportedLanguageSerializer(many=True),
    )
    def get(self, request):
        languages = [
            {
                "code": code,
                "name": str(name),
            }
            for code, name in settings.LANGUAGES
        ]

        serializer = self.get_serializer(
            languages,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class MyPreferenceView(generics.GenericAPIView):
    """
    Retrieve or partially update the authenticated user's interface
    and accessibility preferences.
    """

    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UserPreferenceSerializer

    def get_preference(self, request, *, lock=False):
        queryset = UserPreference.objects

        if lock:
            queryset = queryset.select_for_update()

        preference, _created = queryset.get_or_create(
            user=request.user,
        )

        return preference

    @extend_schema(
        responses=UserPreferenceSerializer,
    )
    def get(self, request):
        preference = self.get_preference(request)
        serializer = self.get_serializer(preference)

        response = Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

        response["Content-Language"] = (
            preference.preferred_language
        )

        return response

    @extend_schema(
        request=UserPreferenceSerializer,
        responses=UserPreferenceSerializer,
    )
    @transaction.atomic
    def patch(self, request):
        preference = self.get_preference(
            request,
            lock=True,
        )

        serializer = self.get_serializer(
            preference,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        preference = serializer.save()

        language_code = preference.preferred_language
        translation.activate(language_code)

        response = Response(
            self.get_serializer(preference).data,
            status=status.HTTP_200_OK,
        )

        response["Content-Language"] = language_code

        response.set_cookie(
            key=settings.LANGUAGE_COOKIE_NAME,
            value=language_code,
            max_age=getattr(
                settings,
                "LANGUAGE_COOKIE_AGE",
                60 * 60 * 24 * 365,
            ),
            path=getattr(
                settings,
                "LANGUAGE_COOKIE_PATH",
                "/",
            ),
            domain=getattr(
                settings,
                "LANGUAGE_COOKIE_DOMAIN",
                None,
            ),
            secure=getattr(
                settings,
                "LANGUAGE_COOKIE_SECURE",
                False,
            ),
            httponly=getattr(
                settings,
                "LANGUAGE_COOKIE_HTTPONLY",
                False,
            ),
            samesite=getattr(
                settings,
                "LANGUAGE_COOKIE_SAMESITE",
                "Lax",
            ),
        )

        return response