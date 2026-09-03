from django.contrib import admin

from .models import SupportCase, SupportCaseEvent


class SupportCaseEventInline(admin.TabularInline):
    model = SupportCaseEvent
    extra = 0
    can_delete = False
    show_change_link = False

    fields = (
        "event_type",
        "actor",
        "previous_status",
        "new_status",
        "message",
        "created_at",
    )

    readonly_fields = fields

    ordering = (
        "created_at",
        "id",
    )

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False


@admin.register(SupportCase)
class SupportCaseAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "subject",
        "category",
        "priority",
        "status",
        "requester",
        "assigned_to",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "status",
        "priority",
        "category",
        "created_at",
    )

    search_fields = (
        "reference",
        "subject",
        "requester__username",
        "requester__email",
        "assigned_to__username",
    )

    ordering = (
        "-created_at",
    )

    list_select_related = (
        "requester",
        "assigned_to",
        "organization",
        "clinic",
        "appointment",
    )

    readonly_fields = (
        "id",
        "reference",
        "requester",
        "assigned_to",
        "organization",
        "clinic",
        "appointment",
        "category",
        "priority",
        "status",
        "subject",
        "description",
        "resolution_summary",
        "resolved_at",
        "closed_at",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Case",
            {
                "fields": (
                    "id",
                    "reference",
                    "status",
                    "priority",
                    "category",
                    "subject",
                    "description",
                )
            },
        ),
        (
            "Ownership",
            {
                "fields": (
                    "requester",
                    "assigned_to",
                )
            },
        ),
        (
            "Related records",
            {
                "fields": (
                    "organization",
                    "clinic",
                    "appointment",
                )
            },
        ),
        (
            "Resolution",
            {
                "fields": (
                    "resolution_summary",
                    "resolved_at",
                    "closed_at",
                )
            },
        ),
        (
            "Audit timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    inlines = (
        SupportCaseEventInline,
    )

    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False


@admin.register(SupportCaseEvent)
class SupportCaseEventAdmin(admin.ModelAdmin):
    list_display = (
        "case",
        "event_type",
        "actor",
        "previous_status",
        "new_status",
        "created_at",
    )

    list_filter = (
        "event_type",
        "created_at",
    )

    search_fields = (
        "case__reference",
        "case__subject",
        "actor__username",
        "message",
    )

    ordering = (
        "-created_at",
    )

    list_select_related = (
        "case",
        "actor",
    )

    readonly_fields = (
        "id",
        "case",
        "actor",
        "event_type",
        "previous_status",
        "new_status",
        "message",
        "metadata",
        "created_at",
    )

    fields = readonly_fields
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False