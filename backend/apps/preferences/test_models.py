import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from .models import UserPreference


pytestmark = pytest.mark.django_db

User = get_user_model()


def create_user(username):
    return User.objects.create_user(
        username=username,
        password="test-password",
    )


def test_new_user_receives_default_preferences():
    user = create_user("preference-user")

    preferences = UserPreference.objects.get(
        user=user
    )

    assert (
        preferences.preferred_language
        == UserPreference.Language.ENGLISH
    )
    assert preferences.low_data_mode is False
    assert preferences.large_text is False
    assert preferences.high_contrast is False
    assert preferences.reduce_motion is False
    assert preferences.created_at is not None
    assert preferences.updated_at is not None


def test_updating_user_does_not_create_duplicate_preferences():
    user = create_user("updated-preference-user")

    original_preference_id = user.preferences.pk

    user.first_name = "Updated"
    user.save(update_fields=["first_name"])

    assert UserPreference.objects.filter(
        user=user
    ).count() == 1

    user.refresh_from_db()

    assert user.preferences.pk == original_preference_id


def test_user_can_select_bengali():
    user = create_user("bengali-preference-user")
    preferences = user.preferences

    preferences.preferred_language = (
        UserPreference.Language.BENGALI
    )
    preferences.save(
        update_fields=[
            "preferred_language",
            "updated_at",
        ]
    )

    preferences.refresh_from_db()

    assert preferences.preferred_language == "bn"


def test_user_can_select_hindi():
    user = create_user("hindi-preference-user")
    preferences = user.preferences

    preferences.preferred_language = (
        UserPreference.Language.HINDI
    )
    preferences.save(
        update_fields=[
            "preferred_language",
            "updated_at",
        ]
    )

    preferences.refresh_from_db()

    assert preferences.preferred_language == "hi"


def test_supported_languages_match_django_settings():
    model_language_codes = {
        value
        for value, _label in UserPreference.Language.choices
    }

    setting_language_codes = {
        value
        for value, _label in settings.LANGUAGES
    }

    assert model_language_codes == setting_language_codes


def test_accessibility_preferences_can_be_enabled():
    user = create_user("accessibility-preference-user")
    preferences = user.preferences

    preferences.low_data_mode = True
    preferences.large_text = True
    preferences.high_contrast = True
    preferences.reduce_motion = True

    preferences.save(
        update_fields=[
            "low_data_mode",
            "large_text",
            "high_contrast",
            "reduce_motion",
            "updated_at",
        ]
    )

    preferences.refresh_from_db()

    assert preferences.low_data_mode is True
    assert preferences.large_text is True
    assert preferences.high_contrast is True
    assert preferences.reduce_motion is True


def test_only_one_preference_record_is_allowed_per_user():
    user = create_user("unique-preference-user")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            UserPreference.objects.create(
                user=user,
            )

    assert UserPreference.objects.filter(
        user=user
    ).count() == 1


def test_database_rejects_unsupported_language():
    user = create_user("invalid-language-user")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            UserPreference.objects.filter(
                user=user
            ).update(
                preferred_language="fr"
            )

    user.preferences.refresh_from_db()

    assert (
        user.preferences.preferred_language
        == UserPreference.Language.ENGLISH
    )


def test_deleting_user_deletes_preferences():
    user = create_user("deleted-preference-user")
    preference_id = user.preferences.pk

    user.delete()

    assert not UserPreference.objects.filter(
        pk=preference_id
    ).exists()