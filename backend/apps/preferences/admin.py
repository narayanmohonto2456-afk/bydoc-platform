from django.contrib import admin

from .models import UserPreference


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "preferred_language",
        "low_data_mode",
        "large_text",
        "high_contrast",
        "reduce_motion",
        "updated_at",
    )

    list_filter = (
        "preferred_language",
        "low_data_mode",
        "large_text",
        "high_contrast",
        "reduce_motion",
    )

    search_fields = (
        "user__username",
        "user__email",
    )

    ordering = (
        "-updated_at",
    )

    list_select_related = (
        "user",
    )

    readonly_fields = (
        "id",
        "user",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "User",
            {
                "fields": (
                    "id",
                    "user",
                )
            },
        ),
        (
            "Language",
            {
                "fields": (
                    "preferred_language",
                )
            },
        ),
        (
            "Accessibility and data usage",
            {
                "fields": (
                    "low_data_mode",
                    "large_text",
                    "high_contrast",
                    "reduce_motion",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    actions = None

    def has_add_permission(self, request):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False