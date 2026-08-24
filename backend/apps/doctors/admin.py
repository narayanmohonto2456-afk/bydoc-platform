from django.contrib import admin
from django.utils import timezone

from .models import (
    DoctorClinicAffiliation,
    DoctorProfile,
    DoctorQualification,
    DoctorRegistration,
    Language,
    Specialty,
)


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "is_active",
    )
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {
        "slug": ("name",),
    }
    ordering = ("name",)


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "native_name",
        "code",
        "is_active",
    )
    list_filter = ("is_active",)
    search_fields = (
        "name",
        "native_name",
        "code",
    )
    ordering = ("name",)


class DoctorRegistrationInline(admin.TabularInline):
    model = DoctorRegistration
    extra = 0
    fields = (
        "council_name",
        "registration_number",
        "registered_name",
        "verification_status",
        "valid_until",
    )
    show_change_link = True


class DoctorQualificationInline(admin.TabularInline):
    model = DoctorQualification
    extra = 0
    fields = (
        "degree_name",
        "institution_name",
        "completion_year",
        "verification_status",
    )
    show_change_link = True


class DoctorClinicAffiliationInline(admin.TabularInline):
    model = DoctorClinicAffiliation
    extra = 0
    fields = (
        "clinic",
        "status",
        "consultation_fee",
        "currency_code",
        "accepts_online_bookings",
    )
    autocomplete_fields = ("clinic",)
    show_change_link = True


@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "user",
        "primary_specialty",
        "status",
        "updated_at",
    )
    list_filter = (
        "status",
        "primary_specialty",
    )
    search_fields = (
        "display_name",
        "user__username",
        "user__email",
        "user__phone_number",
        "professional_summary",
    )
    autocomplete_fields = (
        "user",
        "primary_specialty",
    )
    filter_horizontal = (
        "specialties",
        "languages",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )
    inlines = (
        DoctorRegistrationInline,
        DoctorQualificationInline,
        DoctorClinicAffiliationInline,
    )
    ordering = ("display_name",)
    list_select_related = (
        "user",
        "primary_specialty",
    )


@admin.register(DoctorRegistration)
class DoctorRegistrationAdmin(admin.ModelAdmin):
    list_display = (
        "registration_number",
        "council_name",
        "doctor",
        "verification_status",
        "verified_at",
    )
    list_filter = (
        "verification_status",
        "council_name",
    )
    search_fields = (
        "registration_number",
        "registered_name",
        "council_name",
        "doctor__display_name",
    )
    autocomplete_fields = (
        "doctor",
        "verified_by",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )
    list_select_related = (
        "doctor",
        "verified_by",
    )

    def save_model(self, request, obj, form, change):
        if (
            obj.verification_status
            == DoctorRegistration.VerificationStatus.VERIFIED
        ):
            if obj.verified_by_id is None:
                obj.verified_by = request.user

            if obj.verified_at is None:
                obj.verified_at = timezone.now()

        super().save_model(request, obj, form, change)


@admin.register(DoctorQualification)
class DoctorQualificationAdmin(admin.ModelAdmin):
    list_display = (
        "degree_name",
        "doctor",
        "institution_name",
        "completion_year",
        "verification_status",
    )
    list_filter = (
        "verification_status",
        "completion_year",
        "country_code",
    )
    search_fields = (
        "degree_name",
        "institution_name",
        "awarding_body",
        "doctor__display_name",
    )
    autocomplete_fields = ("doctor",)
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )
    list_select_related = ("doctor",)


@admin.register(DoctorClinicAffiliation)
class DoctorClinicAffiliationAdmin(admin.ModelAdmin):
    list_display = (
        "doctor",
        "clinic",
        "status",
        "consultation_fee",
        "currency_code",
        "accepts_online_bookings",
    )
    list_filter = (
        "status",
        "currency_code",
        "accepts_online_bookings",
    )
    search_fields = (
        "doctor__display_name",
        "clinic__name",
        "clinic__organization__name",
    )
    autocomplete_fields = (
        "doctor",
        "clinic",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )
    list_select_related = (
        "doctor",
        "clinic",
        "clinic__organization",
    )