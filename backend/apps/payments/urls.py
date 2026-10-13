from django.urls import path

from .views import (
    AppointmentPaymentStatusView,
    CreateOrderView,
    RazorpayWebhookView,
    VerifyPaymentView,
)

app_name = "payments"

urlpatterns = [
    path("webhook/razorpay/", RazorpayWebhookView.as_view(), name="razorpay-webhook"),
    path("appointments/<uuid:appointment_id>/", AppointmentPaymentStatusView.as_view(), name="status"),
    path("appointments/<uuid:appointment_id>/order/", CreateOrderView.as_view(), name="order"),
    path("appointments/<uuid:appointment_id>/verify/", VerifyPaymentView.as_view(), name="verify"),
]
