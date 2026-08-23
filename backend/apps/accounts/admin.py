from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


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
            "SehatSaathi identity",
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