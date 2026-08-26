from django.contrib import admin

from .models import (
    Appointment,
    AppointmentSlot,
    AvailabilityRule,
    ScheduleException,
)


@admin.register(AvailabilityRule)
class AvailabilityRuleAdmin(admin.ModelAdmin):
    list_display = (
        "affiliation",
        "weekday",
        "start_time",
        "end_time",
        "valid_from",
        "valid_until",
        "is_active",
    )
    list_filter = (
        "weekday",
        "is_active",
    )
    search_fields = (
        "affiliation__doctor__display_name",
        "affiliation__clinic__name",
        "affiliation__clinic__organization__name",
    )
    autocomplete_fields = ("affiliation",)
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )
    list_select_related = (
        "affiliation",
        "affiliation__doctor",
        "affiliation__clinic",
    )
    ordering = (
        "affiliation",
        "weekday",
        "start_time",
    )


@admin.register(ScheduleException)
class ScheduleExceptionAdmin(admin.ModelAdmin):
    list_display = (
        "affiliation",
        "exception_date",
        "exception_type",
        "start_time",
        "end_time",
    )
    list_filter = (
        "exception_type",
        "exception_date",
    )
    search_fields = (
        "affiliation__doctor__display_name",
        "affiliation__clinic__name",
        "public_note",
    )
    autocomplete_fields = ("affiliation",)
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )
    list_select_related = (
        "affiliation",
        "affiliation__doctor",
        "affiliation__clinic",
    )
    ordering = (
        "-exception_date",
        "start_time",
    )


@admin.register(AppointmentSlot)
class AppointmentSlotAdmin(admin.ModelAdmin):
    list_display = (
        "starts_at",
        "ends_at",
        "affiliation",
        "status",
        "held_by",
        "hold_expires_at",
    )
    list_filter = (
        "status",
        "starts_at",
    )
    search_fields = (
        "=id",
        "affiliation__doctor__display_name",
        "affiliation__clinic__name",
        "held_by__username",
        "held_by__email",
        "held_by__phone_number",
    )
    readonly_fields = (
        "id",
        "status",
        "held_by",
        "hold_token",
        "hold_expires_at",
        "created_at",
        "updated_at",
    )
    autocomplete_fields = ("affiliation",)
    list_select_related = (
        "affiliation",
        "affiliation__doctor",
        "affiliation__clinic",
        "held_by",
    )
    ordering = ("-starts_at",)

    fieldsets = (
        (
            "Slot",
            {
                "fields": (
                    "id",
                    "affiliation",
                    "starts_at",
                    "ends_at",
                    "status",
                )
            },
        ),
        (
            "Temporary hold",
            {
                "fields": (
                    "held_by",
                    "hold_token",
                    "hold_expires_at",
                )
            },
        ),
        (
            "Audit",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "booking_reference",
        "patient",
        "slot",
        "status",
        "booked_by",
        "created_at",
    )
    list_filter = (
        "status",
        "created_at",
    )
    search_fields = (
        "=booking_reference",
        "patient__username",
        "patient__email",
        "patient__phone_number",
        "booked_by__username",
        "slot__affiliation__doctor__display_name",
        "slot__affiliation__clinic__name",
    )
    readonly_fields = (
        "id",
        "booking_reference",
        "slot",
        "patient",
        "booked_by",
        "status",
        "cancelled_at",
        "cancelled_by",
        "created_at",
        "updated_at",
    )
    list_select_related = (
        "slot",
        "slot__affiliation",
        "slot__affiliation__doctor",
        "slot__affiliation__clinic",
        "patient",
        "booked_by",
        "cancelled_by",
    )
    ordering = ("-created_at",)

    fieldsets = (
        (
            "Booking",
            {
                "fields": (
                    "id",
                    "booking_reference",
                    "slot",
                    "patient",
                    "booked_by",
                    "status",
                )
            },
        ),
        (
            "Cancellation",
            {
                "fields": (
                    "cancelled_at",
                    "cancelled_by",
                    "cancellation_note",
                )
            },
        ),
        (
            "Audit",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def has_add_permission(self, request):
        # Appointments must only be created by the atomic
        # booking service.
        return False

    def has_delete_permission(self, request, obj=None):
        # Preserve booking history for safety and auditing.
        return False