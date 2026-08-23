from django.contrib import admin

from .models import Organization, OrganizationMembership


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organization_type",
        "status",
        "created_at",
    )

    list_filter = (
        "organization_type",
        "status",
    )

    search_fields = (
        "name",
        "slug",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )

    ordering = ("name",)


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "organization",
        "role",
        "status",
        "joined_at",
    )

    list_filter = (
        "role",
        "status",
        "organization",
    )

    search_fields = (
        "user__username",
        "user__email",
        "user__phone_number",
        "organization__name",
    )

    autocomplete_fields = (
        "organization",
        "user",
        "invited_by",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )