from django.conf import settings
from django.utils import translation

from .models import UserPreference


class UserPreferenceLocaleMiddleware:
    """
    Activate an authenticated session user's stored language.

    This middleware must run after Django's
    AuthenticationMiddleware.

    Token-authenticated API requests continue using the language
    cookie or Accept-Language header because DRF authenticates those
    users inside the view.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        previous_language = translation.get_language()
        selected_language = None

        user = getattr(request, "user", None)

        if (
            user is not None
            and user.is_authenticated
            and user.pk is not None
        ):
            preference, _created = (
                UserPreference.objects.get_or_create(
                    user=user
                )
            )

            language_code = (
                preference.preferred_language
            )

            supported_languages = {
                code
                for code, _name in settings.LANGUAGES
            }

            if language_code in supported_languages:
                selected_language = language_code
                translation.activate(language_code)
                request.LANGUAGE_CODE = language_code

        try:
            response = self.get_response(request)

            if selected_language is not None:
                response.setdefault(
                    "Content-Language",
                    selected_language,
                )

            return response
        finally:
            if previous_language:
                translation.activate(previous_language)
            else:
                translation.deactivate()