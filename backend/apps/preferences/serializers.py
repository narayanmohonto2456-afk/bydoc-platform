from django.conf import settings
from rest_framework import serializers

from .models import UserPreference


class UserPreferenceSerializer(
    serializers.ModelSerializer
):
    language_name = serializers.SerializerMethodField()

    class Meta:
        model = UserPreference
        fields = (
            "preferred_language",
            "language_name",
            "low_data_mode",
            "large_text",
            "high_contrast",
            "reduce_motion",
            "updated_at",
        )

        read_only_fields = (
            "language_name",
            "updated_at",
        )

    def get_language_name(self, preference) -> str:
        language_names = dict(settings.LANGUAGES)

        return language_names.get(
            preference.preferred_language,
            preference.preferred_language,
        )

    def validate_preferred_language(self, value):
        supported_languages = {
            language_code
            for language_code, _language_name
            in settings.LANGUAGES
        }

        if value not in supported_languages:
            raise serializers.ValidationError(
                "This language is not supported."
            )

        return value


class SupportedLanguageSerializer(
    serializers.Serializer
):
    code = serializers.CharField(
        read_only=True,
    )

    name = serializers.CharField(
        read_only=True,
    )