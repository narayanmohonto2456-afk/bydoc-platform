from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.appointments.models import Appointment

from . import gateway
from .models import ClinicPaymentAccount, PaymentIntent


class PaymentError(Exception):
    pass


def amount_in_paise(appointment):
    affiliation = appointment.slot.affiliation
    if affiliation.currency_code != "INR" or affiliation.consultation_fee is None:
        raise PaymentError("Online payment is unavailable for this consultation.")
    amount = affiliation.consultation_fee * Decimal(100)
    if amount <= 0 or amount > 2_147_483_647 or amount != amount.to_integral_value():
        raise PaymentError("Online payment is unavailable for this consultation.")
    return int(amount)


def payment_available(appointment):
    if not gateway.configured():
        return False
    try:
        amount_in_paise(appointment)
        account = ClinicPaymentAccount.objects.get(clinic_id=appointment.slot.affiliation.clinic_id)
        return account.enabled and account.razorpay_linked_account_id.startswith("acc_")
    except (PaymentError, ClinicPaymentAccount.DoesNotExist):
        return False


@transaction.atomic
def create_or_get_order(appointment_id, user):
    appointment = (
        Appointment.objects.select_for_update()
        .select_related("slot__affiliation")
        .get(pk=appointment_id)
    )
    if user.pk not in {appointment.patient_id, appointment.booked_by_id}:
        raise Appointment.DoesNotExist
    if appointment.status != Appointment.Status.CONFIRMED:
        raise PaymentError("Only confirmed appointments can be paid online.")
    if not payment_available(appointment):
        raise PaymentError("Online payment is unavailable for this clinic.")
    existing = PaymentIntent.objects.filter(appointment=appointment).first()
    if existing:
        if existing.status != PaymentIntent.Status.PENDING:
            raise PaymentError("This appointment is already paid or being refunded.")
        return existing

    amount = amount_in_paise(appointment)
    linked_account = appointment.slot.affiliation.clinic.payment_account.razorpay_linked_account_id
    try:
        order = gateway.create_order(amount, linked_account, str(appointment.booking_reference))
    except gateway.GatewayError as error:
        raise PaymentError(str(error)) from error
    if (
        not isinstance(order.get("id"), str)
        or not order["id"].startswith("order_")
        or order.get("amount") != amount
        or order.get("currency") != "INR"
    ):
        raise PaymentError("Payment provider returned an invalid order.")
    return PaymentIntent.objects.create(
        appointment=appointment,
        amount_paise=amount,
        linked_account_id=linked_account,
        razorpay_order_id=order["id"],
    )


@transaction.atomic
def record_capture(order_id, payment_id, amount_paise, currency):
    try:
        intent = PaymentIntent.objects.select_for_update().select_related("appointment").get(
            razorpay_order_id=order_id
        )
    except PaymentIntent.DoesNotExist as error:
        raise PaymentError("Unknown payment order.") from error
    if amount_paise != intent.amount_paise or currency != intent.currency:
        raise PaymentError("Payment amount does not match the order.")
    if intent.razorpay_payment_id and intent.razorpay_payment_id != payment_id:
        intent.status = PaymentIntent.Status.REVIEW
        intent.last_error = "More than one payment was captured for this order."
        intent.save(update_fields=["status", "last_error", "updated_at"])
        return intent
    if not intent.razorpay_payment_id:
        intent.razorpay_payment_id = payment_id
        intent.status = (
            PaymentIntent.Status.REFUND_DUE
            if intent.appointment.status == Appointment.Status.CANCELLED
            else PaymentIntent.Status.CAPTURED
        )
        intent.save(update_fields=["razorpay_payment_id", "status", "updated_at"])
    return intent


def verify_checkout(intent, payment_id, signature):
    if not gateway.checkout_signature_valid(intent.razorpay_order_id, payment_id, signature):
        raise PaymentError("Invalid payment signature.")
    try:
        payment = gateway.fetch_payment(payment_id)
    except gateway.GatewayError as error:
        raise PaymentError(str(error)) from error
    if payment.get("status") != "captured" or payment.get("order_id") != intent.razorpay_order_id:
        raise PaymentError("Payment has not been captured yet.")
    return record_capture(
        intent.razorpay_order_id, payment_id, payment.get("amount"), payment.get("currency")
    )


def mark_cancelled_for_refund(appointment):
    """Called in the appointment cancellation transaction."""
    intent = PaymentIntent.objects.select_for_update().filter(appointment=appointment).first()
    if intent and intent.status == PaymentIntent.Status.CAPTURED:
        intent.status = PaymentIntent.Status.REFUND_DUE
        intent.save(update_fields=["status", "updated_at"])


def refund_one(intent_id):
    """Retry safely: inspect provider refunds before asking for a new refund."""
    with transaction.atomic():
        intent = PaymentIntent.objects.select_for_update().get(pk=intent_id)
        if intent.status != PaymentIntent.Status.REFUND_DUE or not intent.razorpay_payment_id:
            return
        try:
            existing = gateway.fetch_refunds(intent.razorpay_payment_id)
            refunds = existing.get("items", [])
            matching = next((item for item in refunds if item.get("amount") == intent.amount_paise
                             and item.get("payment_id") == intent.razorpay_payment_id
                             and item.get("status") not in {"failed", "rejected"}), None)
            refund = matching or gateway.create_full_refund(
                intent.razorpay_payment_id, intent.amount_paise, str(intent.appointment.booking_reference)
            )
            if not isinstance(refund.get("id"), str) or not refund["id"].startswith("rfnd_"):
                raise PaymentError("Payment provider returned an invalid refund.")
            intent.razorpay_refund_id = refund["id"]
            intent.refund_requested_at = timezone.now()
            intent.status = (
                PaymentIntent.Status.REFUNDED if refund.get("status") == "processed"
                else PaymentIntent.Status.REFUND_PENDING
            )
            intent.last_error = ""
        except (gateway.GatewayError, PaymentError) as error:
            intent.last_error = str(error)[:500]
        intent.save()


def record_refund(refund_id, payment_id, amount, status):
    with transaction.atomic():
        intent = PaymentIntent.objects.select_for_update().filter(razorpay_payment_id=payment_id).first()
        if not intent or amount != intent.amount_paise:
            raise PaymentError("Unknown refund.")
        if intent.razorpay_refund_id and intent.razorpay_refund_id != refund_id:
            raise PaymentError("Refund ID does not match.")
        intent.razorpay_refund_id = refund_id
        if status == "processed":
            intent.status = PaymentIntent.Status.REFUNDED
        elif status in {"failed", "rejected"}:
            intent.status = PaymentIntent.Status.REVIEW
            intent.last_error = f"Refund {status}; manual review required."
        intent.save()
        return intent
