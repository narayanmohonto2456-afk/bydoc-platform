"""Small Razorpay adapter. Only this module handles merchant credentials."""

import hashlib
import hmac

import requests
from django.conf import settings


class GatewayError(Exception):
    pass


def configured():
    return all((
        settings.RAZORPAY_PAYMENTS_ENABLED,
        settings.RAZORPAY_KEY_ID,
        settings.RAZORPAY_KEY_SECRET,
        settings.RAZORPAY_WEBHOOK_SECRET,
    ))


def request(method, path, payload=None):
    if not configured():
        raise GatewayError("Online payments are unavailable.")
    try:
        response = requests.request(
            method,
            f"https://api.razorpay.com/v1/{path}",
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise TypeError("Unexpected gateway response")
        return data
    except (requests.RequestException, ValueError, TypeError) as error:
        raise GatewayError("Payment provider is temporarily unavailable.") from error


def create_order(amount_paise, linked_account_id, receipt):
    return request("POST", "orders", {
        "amount": amount_paise,
        "currency": "INR",
        "payment_capture": 1,
        "receipt": receipt,
        "transfers": [{
            "account": linked_account_id,
            "amount": amount_paise,
            "currency": "INR",
        }],
    })


def fetch_payment(payment_id):
    return request("GET", f"payments/{payment_id}")


def fetch_refunds(payment_id):
    return request("GET", f"payments/{payment_id}/refunds")


def create_full_refund(payment_id, amount_paise, receipt):
    return request("POST", f"payments/{payment_id}/refund", {
        "amount": amount_paise,
        "reverse_all": 1,
        "receipt": receipt,
    })


def checkout_signature_valid(order_id, payment_id, signature):
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def webhook_signature_valid(body, signature):
    expected = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
