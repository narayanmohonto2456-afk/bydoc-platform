from django.contrib import admin, messages

from .models import ApplicationStatus, ClinicApplication, DoctorApplication
from .services import ApplicationError, review_clinic, review_doctor


class ApplicationAdmin(admin.ModelAdmin):
    list_filter = ("status", "submitted_at")
    search_fields = ("applicant__username", "applicant__email")
    readonly_fields = (
        "id", "applicant", "status", "attested_at", "submitted_at",
        "reviewed_by", "reviewed_at",
    )
    actions = ("approve_applications", "reject_applications")
    review_service = None

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and (obj is None or obj.status == ApplicationStatus.PENDING)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        return fields + (("review_note",) if obj and obj.status != ApplicationStatus.PENDING else ())

    def _review(self, request, queryset, approve):
        completed = 0
        for application in queryset:
            try:
                self.review_service(application.pk, request.user, approve, application.review_note)
                completed += 1
            except ApplicationError as error:
                self.message_user(request, f"{application}: {error}", level=messages.ERROR)
        if completed:
            self.message_user(request, f"Reviewed {completed} application(s).", level=messages.SUCCESS)

    @admin.action(description="Approve selected after saving review notes")
    def approve_applications(self, request, queryset):
        self._review(request, queryset, True)

    @admin.action(description="Reject selected after saving review notes")
    def reject_applications(self, request, queryset):
        self._review(request, queryset, False)


@admin.register(DoctorApplication)
class DoctorApplicationAdmin(ApplicationAdmin):
    list_display = ("display_name", "council_name", "registration_number", "applicant", "status", "submitted_at")
    search_fields = ApplicationAdmin.search_fields + ("display_name", "council_name", "registration_number")
    readonly_fields = ApplicationAdmin.readonly_fields + (
        "display_name", "registered_name", "council_name", "registration_number",
        "registration_year", "specialty_name", "profile",
    )
    review_service = staticmethod(review_doctor)


@admin.register(ClinicApplication)
class ClinicApplicationAdmin(ApplicationAdmin):
    list_display = ("clinic_name", "manager_name", "district", "applicant", "status", "submitted_at")
    search_fields = ApplicationAdmin.search_fields + ("clinic_name", "manager_name", "registration_number")
    readonly_fields = ApplicationAdmin.readonly_fields + (
        "clinic_name", "manager_name", "registration_authority", "registration_number",
        "phone_number", "email", "address_line_1", "locality", "district", "state",
        "postal_code", "clinic",
    )
    review_service = staticmethod(review_clinic)
