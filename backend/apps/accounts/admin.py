from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import GoogleIdentity, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "username",
        "email",
        "phone_number",
        "is_staff",
        "is_active",
    )

    list_filter = (
        "is_staff",
        "is_superuser",
        "is_active",
    )

    search_fields = (
        "username",
        "email",
        "phone_number",
        "first_name",
        "last_name",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "date_joined",
        "last_login",
    )

    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "BYdoc identity",
            {
                "fields": (
                    "phone_number",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        (
            "Contact information",
            {
                "fields": (
                    "email",
                    "phone_number",
                ),
            },
        ),
    )


@admin.register(GoogleIdentity)
class GoogleIdentityAdmin(admin.ModelAdmin):
    list_display = ("user", "subject", "created_at")
    search_fields = ("user__username", "subject")
    readonly_fields = ("user", "subject", "created_at")

    def has_add_permission(self, request):
        return False
