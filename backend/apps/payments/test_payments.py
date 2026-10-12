import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.appointments.models import Appointment
from apps.appointments.test_api import (
    create_affiliation,
    create_future_slot,
    create_user,
)
from apps.appointments.test_rebooking import book_via_api

from .models import ClinicPaymentAccount, PaymentIntent, PaymentWebhookEvent
from .services import record_capture, refund_one

pytestmark = pytest.mark.django_db

PAYMENT_SETTINGS = {
    "RAZORPAY_PAYMENTS_ENABLED": True,
    "RAZORPAY_KEY_ID": "rzp_test_example",
    "RAZORPAY_KEY_SECRET": "test-secret",
    "RAZORPAY_WEBHOOK_SECRET": "webhook-secret",
}


def booked_appointment():
    affiliation = create_affiliation()
    ClinicPaymentAccount.objects.create(
        clinic=affiliation.clinic,
        razorpay_linked_account_id="acc_clinic123",
        enabled=True,
    )
    slot = create_future_slot(affiliation)
    patient = create_user("payment-patient")
    client = APIClient()
    client.force_authenticate(user=patient)
    appointment_id, _ = book_via_api(client, slot)
    return client, Appointment.objects.get(pk=appointment_id), affiliation


def order_response(amount=50000):
    return {"id": "order_123", "amount": amount, "currency": "INR"}


@override_settings(**PAYMENT_SETTINGS)
def test_order_is_patient_scoped_idempotent_and_uses_clinic_route():
    client, appointment, affiliation = booked_appointment()
    url = reverse("payments:order", kwargs={"appointment_id": appointment.pk})
    other = APIClient()
    other.force_authenticate(user=create_user("payment-other"))
    assert other.post(url, {}, format="json").status_code == 404
    with patch("apps.payments.gateway.create_order", return_value=order_response()) as create:
        first = client.post(url, {}, format="json")
        second = client.post(url, {}, format="json")
    assert first.status_code == second.status_code == 200
    assert first.data["order_id"] == second.data["order_id"] == "order_123"
    create.assert_called_once_with(50000, "acc_clinic123", str(appointment.booking_reference))
    assert PaymentIntent.objects.count() == 1
    affiliation.consultation_fee = "600.00"
    affiliation.save(update_fields=["consultation_fee"])
    intent = PaymentIntent.objects.get(appointment=appointment)
    assert intent.amount_paise == 50000


@override_settings(**PAYMENT_SETTINGS)
def test_verified_capture_and_full_refund_on_cancellation():
    client, appointment, _ = booked_appointment()
    with patch("apps.payments.gateway.create_order", return_value=order_response()):
        assert client.post(reverse("payments:order", kwargs={"appointment_id": appointment.pk}), {}).status_code == 200
    verify_url = reverse("payments:verify", kwargs={"appointment_id": appointment.pk})
    signature = hmac.new(b"test-secret", b"order_123|pay_123", hashlib.sha256).hexdigest()
    with patch("apps.payments.gateway.fetch_payment", return_value={
        "status": "captured", "order_id": "order_123", "amount": 50000, "currency": "INR"
    }) as fetch:
        assert client.post(verify_url, {
            "razorpay_order_id": "order_123", "razorpay_payment_id": "pay_123",
            "razorpay_signature": "forged",
        }, format="json").status_code == 409
        assert not fetch.called
        verified = client.post(verify_url, {
            "razorpay_order_id": "order_123", "razorpay_payment_id": "pay_123",
            "razorpay_signature": signature,
        }, format="json")
    assert verified.status_code == 200
    assert verified.data["status"] == "captured"
    cancelled = client.post(reverse("appointments:appointment-cancel", kwargs={"appointment_id": appointment.pk}), {}, format="json")
    assert cancelled.status_code == 200
    intent = PaymentIntent.objects.get(appointment=appointment)
    assert intent.status == PaymentIntent.Status.REFUND_DUE
    with patch("apps.payments.gateway.fetch_refunds", return_value={"items": []}), patch(
        "apps.payments.gateway.create_full_refund",
        return_value={"id": "rfnd_123", "status": "pending"},
    ) as refund:
        refund_one(intent.pk)
        refund_one(intent.pk)
    refund.assert_called_once_with("pay_123", 50000, str(appointment.booking_reference))
    intent.refresh_from_db()
    assert intent.status == PaymentIntent.Status.REFUND_PENDING
    assert intent.razorpay_refund_id == "rfnd_123"
    body = json.dumps({"event": "refund.processed", "payload": {"refund": {"entity": {
        "id": "rfnd_123", "payment_id": "pay_123", "amount": 50000, "status": "processed",
    }}}}).encode()
    webhook_signature = hmac.new(b"webhook-secret", body, hashlib.sha256).hexdigest()
    webhook = APIClient().post(
        reverse("payments:razorpay-webhook"), body, content_type="application/json",
        HTTP_X_RAZORPAY_EVENT_ID="evt_refund_123", HTTP_X_RAZORPAY_SIGNATURE=webhook_signature,
    )
    assert webhook.status_code == 200
    assert PaymentIntent.objects.get(pk=intent.pk).status == PaymentIntent.Status.REFUNDED


@override_settings(**PAYMENT_SETTINGS)
def test_webhook_signature_replay_and_capture_after_cancellation():
    client, appointment, _ = booked_appointment()
    with patch("apps.payments.gateway.create_order", return_value=order_response()):
        client.post(reverse("payments:order", kwargs={"appointment_id": appointment.pk}), {})
    client.post(reverse("appointments:appointment-cancel", kwargs={"appointment_id": appointment.pk}), {}, format="json")
    body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {
        "id": "pay_123", "order_id": "order_123", "amount": 50000,
        "currency": "INR", "status": "captured",
    }}}}).encode()
    url = reverse("payments:razorpay-webhook")
    assert APIClient().post(url, body, content_type="application/json", HTTP_X_RAZORPAY_EVENT_ID="evt_123", HTTP_X_RAZORPAY_SIGNATURE="forged").status_code == 400
    signature = hmac.new(b"webhook-secret", body, hashlib.sha256).hexdigest()
    for _ in range(2):
        assert APIClient().post(url, body, content_type="application/json", HTTP_X_RAZORPAY_EVENT_ID="evt_123", HTTP_X_RAZORPAY_SIGNATURE=signature).status_code == 200
    assert PaymentWebhookEvent.objects.count() == 1
    assert PaymentIntent.objects.get(appointment=appointment).status == PaymentIntent.Status.REFUND_DUE


@override_settings(**PAYMENT_SETTINGS)
def test_capture_rejects_wrong_amount():
    client, appointment, _ = booked_appointment()
    with patch("apps.payments.gateway.create_order", return_value=order_response()):
        client.post(reverse("payments:order", kwargs={"appointment_id": appointment.pk}), {})
    with pytest.raises(Exception, match="amount"):
        record_capture("order_123", "pay_wrong", 1, "INR")
    assert PaymentIntent.objects.get(appointment=appointment).status == PaymentIntent.Status.PENDING


@override_settings(RAZORPAY_PAYMENTS_ENABLED=False)
def test_payment_stays_disabled_without_provider_configuration():
    client, appointment, _ = booked_appointment()
    status_url = reverse("payments:status", kwargs={"appointment_id": appointment.pk})
    assert client.get(status_url).data == {
        "available": False, "status": "pay_at_clinic", "amount_paise": None,
        "currency": "INR", "refund_id": None,
    }
    with patch("apps.payments.gateway.create_order") as create:
        result = client.post(reverse("payments:order", kwargs={"appointment_id": appointment.pk}), {})
    assert result.status_code == 409
    create.assert_not_called()
