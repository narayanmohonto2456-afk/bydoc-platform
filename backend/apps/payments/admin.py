from django.contrib import admin

from .models import ClinicPaymentAccount, PaymentIntent, PaymentWebhookEvent


@admin.register(ClinicPaymentAccount)
class ClinicPaymentAccountAdmin(admin.ModelAdmin):
    list_display = ("clinic", "razorpay_linked_account_id", "enabled")
    search_fields = ("clinic__name", "razorpay_linked_account_id")

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(PaymentIntent)
class PaymentIntentAdmin(admin.ModelAdmin):
    list_display = ("appointment", "amount_paise", "status", "created_at")
    search_fields = ("razorpay_order_id", "razorpay_payment_id", "appointment__booking_reference")
    readonly_fields = tuple(field.name for field in PaymentIntent._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PaymentWebhookEvent)
class PaymentWebhookEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "event_type", "received_at")
    readonly_fields = tuple(field.name for field in PaymentWebhookEvent._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
