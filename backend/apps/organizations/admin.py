from django import forms
from django.contrib import admin

from .models import ClinicStaffAssignment, Organization, OrganizationMembership


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

class ClinicStaffAssignmentForm(forms.ModelForm):
    reason = forms.CharField(max_length=250)

    class Meta:
        model = ClinicStaffAssignment
        fields = ("membership", "clinic", "is_active", "reason")


@admin.register(ClinicStaffAssignment)
class ClinicStaffAssignmentAdmin(admin.ModelAdmin):
    form = ClinicStaffAssignmentForm
    list_display = ("membership", "clinic", "is_active", "assigned_by", "updated_at")
    list_filter = ("is_active", "clinic")
    search_fields = (
        "membership__user__username", "membership__user__email", "clinic__name",
    )
    autocomplete_fields = ("membership", "clinic")
    readonly_fields = ("id", "assigned_by", "created_at", "updated_at")

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.assigned_by = request.user
        super().save_model(request, obj, form, change)
