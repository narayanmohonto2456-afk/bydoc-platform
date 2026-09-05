from django.conf import settings
from django.db import migrations


BATCH_SIZE = 500


def create_existing_user_preferences(
    apps,
    schema_editor,
):
    """
    Create default preferences for users who existed before the
    preferences application was introduced.

    Existing preference records are preserved.
    """
    user_app_label, user_model_name = (
        settings.AUTH_USER_MODEL.split(".")
    )

    User = apps.get_model(
        user_app_label,
        user_model_name,
    )
    UserPreference = apps.get_model(
        "preferences",
        "UserPreference",
    )

    database_alias = schema_editor.connection.alias

    existing_user_ids = set(
        UserPreference.objects
        .using(database_alias)
        .values_list("user_id", flat=True)
    )

    pending_preferences = []

    users = (
        User.objects
        .using(database_alias)
        .exclude(pk__in=existing_user_ids)
        .only("pk")
        .iterator(chunk_size=BATCH_SIZE)
    )

    for user in users:
        pending_preferences.append(
            UserPreference(
                user_id=user.pk,
                preferred_language="en",
                low_data_mode=False,
                large_text=False,
                high_contrast=False,
                reduce_motion=False,
            )
        )

        if len(pending_preferences) >= BATCH_SIZE:
            UserPreference.objects.using(
                database_alias
            ).bulk_create(
                pending_preferences,
                ignore_conflicts=True,
            )
            pending_preferences = []

    if pending_preferences:
        UserPreference.objects.using(
            database_alias
        ).bulk_create(
            pending_preferences,
            ignore_conflicts=True,
        )


def preserve_user_preferences(
    apps,
    schema_editor,
):
    """
    Reversing this migration must not delete user preferences because
    they may contain choices changed after the migration ran.
    """


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(
            settings.AUTH_USER_MODEL
        ),
        (
            "preferences",
            "0001_initial",
        ),
    ]

    operations = [
        migrations.RunPython(
            create_existing_user_preferences,
            preserve_user_preferences,
        ),
    ]