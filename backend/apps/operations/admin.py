from django.contrib import admin

from .models import OperationsEvent, PaymentInvestigation, StaffGrant


@admin.register(StaffGrant)
class StaffGrantAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "active", "granted_by", "updated_at")
    list_filter = ("role", "active")
    search_fields = ("user__username", "user__email")
    readonly_fields = tuple(field.name for field in StaffGrant._meta.fields)

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(OperationsEvent)
class OperationsEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "subject_type", "subject_id")
    list_filter = ("action", "subject_type")
    search_fields = ("subject_id", "actor__username")
    readonly_fields = tuple(field.name for field in OperationsEvent._meta.fields)

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PaymentInvestigation)
class PaymentInvestigationAdmin(admin.ModelAdmin):
    list_display = ("intent", "resolved", "updated_by", "updated_at")
    readonly_fields = tuple(field.name for field in PaymentInvestigation._meta.fields)

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
