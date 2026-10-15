import logging

from celery import shared_task

from . import gateway
from .models import PaymentIntent
from .services import PaymentError, record_capture, record_refund, refund_one

logger = logging.getLogger(__name__)


def reconcile_one(intent_id):
    """Inspect the provider for one intent; never accept a staff-supplied status."""
    if not gateway.configured():
        raise PaymentError("Payment provider is not configured.")
    intent = PaymentIntent.objects.get(pk=intent_id)
    if intent.status == PaymentIntent.Status.PENDING:
        payments = gateway.request("GET", f"orders/{intent.razorpay_order_id}/payments")
        for payment in payments.get("items", []):
            if payment.get("status") == "captured":
                record_capture(intent.razorpay_order_id, payment["id"], payment["amount"], payment["currency"])
    elif intent.status == PaymentIntent.Status.REFUND_DUE:
        refund_one(intent.pk)
    elif intent.status == PaymentIntent.Status.REFUND_PENDING:
        refunds = gateway.request("GET", f"payments/{intent.razorpay_payment_id}/refunds")
        for item in refunds.get("items", []):
            if item.get("id") == intent.razorpay_refund_id:
                record_refund(item["id"], item["payment_id"], item["amount"], item["status"])
                break
    else:
        raise PaymentError("This payment is not awaiting reconciliation.")
    return PaymentIntent.objects.get(pk=intent_id)


@shared_task(name="payments.reconcile")
def reconcile_payments():
    if not gateway.configured():
        return
    for intent in PaymentIntent.objects.filter(status=PaymentIntent.Status.PENDING).order_by("created_at")[:100]:
        try:
            payments = gateway.request("GET", f"orders/{intent.razorpay_order_id}/payments")
            for payment in payments.get("items", []):
                if payment.get("status") == "captured":
                    record_capture(intent.razorpay_order_id, payment["id"], payment["amount"], payment["currency"])
        except (gateway.GatewayError, PaymentError, KeyError) as error:
            logger.warning("Payment reconciliation failed for %s: %s", intent.pk, error)
    for intent in PaymentIntent.objects.filter(status=PaymentIntent.Status.REFUND_DUE).order_by("created_at")[:100]:
        refund_one(intent.pk)
    for intent in PaymentIntent.objects.filter(status=PaymentIntent.Status.REFUND_PENDING).order_by("created_at")[:100]:
        try:
            refund = gateway.request("GET", f"payments/{intent.razorpay_payment_id}/refunds")
            for item in refund.get("items", []):
                if item.get("id") == intent.razorpay_refund_id:
                    record_refund(item["id"], item["payment_id"], item["amount"], item["status"])
                    break
        except (gateway.GatewayError, PaymentError, KeyError) as error:
            logger.warning("Refund reconciliation failed for %s: %s", intent.pk, error)
