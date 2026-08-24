from django.contrib import admin

from .models import Clinic


@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organization",
        "status",
        "district",
        "state",
        "phone_number",
        "schedule_updated_at",
    )

    list_filter = (
        "status",
        "state",
        "wheelchair_accessible",
        "has_accessible_restroom",
        "has_waiting_area",
        "accepts_walk_ins",
    )

    search_fields = (
        "name",
        "slug",
        "organization__name",
        "phone_number",
        "email",
        "locality",
        "district",
        "state",
        "postal_code",
    )

    autocomplete_fields = (
        "organization",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Clinic identity",
            {
                "fields": (
                    "id",
                    "organization",
                    "name",
                    "slug",
                    "status",
                )
            },
        ),
        (
            "Contact",
            {
                "fields": (
                    "phone_number",
                    "email",
                )
            },
        ),
        (
            "Address",
            {
                "fields": (
                    "address_line_1",
                    "address_line_2",
                    "locality",
                    "district",
                    "state",
                    "postal_code",
                    "country_code",
                    "latitude",
                    "longitude",
                    "timezone",
                )
            },
        ),
        (
            "Accessibility and service",
            {
                "fields": (
                    "wheelchair_accessible",
                    "has_accessible_restroom",
                    "has_waiting_area",
                    "accepts_walk_ins",
                    "schedule_updated_at",
                )
            },
        ),
        (
            "Audit information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    ordering = (
        "organization__name",
        "name",
    )

    list_select_related = (
        "organization",
    )