import uuid

from django.db import models


class ClinicPaymentAccount(models.Model):
    clinic = models.OneToOneField(
        "clinics.Clinic", on_delete=models.PROTECT, related_name="payment_account"
    )
    razorpay_linked_account_id = models.CharField(max_length=64, unique=True)
    enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.clinic}: {self.razorpay_linked_account_id}"


class PaymentIntent(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for payment"
        CAPTURED = "captured", "Paid"
        REFUND_DUE = "refund_due", "Refund due"
        REFUND_PENDING = "refund_pending", "Refund requested"
        REFUNDED = "refunded", "Refunded"
        REVIEW = "review", "Needs review"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.OneToOneField(
        "appointments.Appointment", on_delete=models.PROTECT, related_name="payment_intent"
    )
    amount_paise = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="INR")
    linked_account_id = models.CharField(max_length=64)
    razorpay_order_id = models.CharField(max_length=64, unique=True)
    razorpay_payment_id = models.CharField(max_length=64, unique=True, null=True, blank=True)
    razorpay_refund_id = models.CharField(max_length=64, unique=True, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    last_error = models.CharField(max_length=500, blank=True)
    refund_requested_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class PaymentWebhookEvent(models.Model):
    event_id = models.CharField(max_length=128, primary_key=True)
    event_type = models.CharField(max_length=80)
    received_at = models.DateTimeField(auto_now_add=True)
