import json

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.appointments.models import Appointment
from apps.operations.models import WebhookFailure

from . import gateway
from .models import PaymentIntent, PaymentWebhookEvent
from .serializers import (
    PaymentOrderSerializer,
    PaymentStatusSerializer,
    VerifyPaymentSerializer,
)
from .services import (
    PaymentError,
    create_or_get_order,
    payment_available,
    record_capture,
    record_refund,
    verify_checkout,
)


def owned_appointment(request, appointment_id):
    return get_object_or_404(
        Appointment.objects.select_related("slot__affiliation"),
        pk=appointment_id,
        patient=request.user,
    )


def status_payload(appointment):
    intent = PaymentIntent.objects.filter(appointment=appointment).first()
    return {
        "available": payment_available(appointment) and appointment.status == Appointment.Status.CONFIRMED,
        "status": intent.status if intent else "pay_at_clinic",
        "amount_paise": intent.amount_paise if intent else None,
        "currency": "INR",
        "refund_id": intent.razorpay_refund_id if intent else None,
    }


class AppointmentPaymentStatusView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(responses=PaymentStatusSerializer)
    def get(self, request, appointment_id):
        return Response(status_payload(owned_appointment(request, appointment_id)))


class CreateOrderView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(request=None, responses=PaymentOrderSerializer)
    def post(self, request, appointment_id):
        owned_appointment(request, appointment_id)
        try:
            intent = create_or_get_order(appointment_id, request.user)
        except PaymentError as error:
            return Response({"detail": str(error)}, status=status.HTTP_409_CONFLICT)
        return Response({
            "key_id": settings.RAZORPAY_KEY_ID,
            "order_id": intent.razorpay_order_id,
            "amount_paise": intent.amount_paise,
            "currency": intent.currency,
        })


class VerifyPaymentView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(request=VerifyPaymentSerializer, responses=PaymentStatusSerializer)
    def post(self, request, appointment_id):
        appointment = owned_appointment(request, appointment_id)
        serializer = VerifyPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        intent = get_object_or_404(PaymentIntent, appointment=appointment)
        if data["razorpay_order_id"] != intent.razorpay_order_id:
            return Response({"detail": "Order does not match this appointment."}, status=400)
        try:
            verify_checkout(intent, data["razorpay_payment_id"], data["razorpay_signature"])
        except PaymentError as error:
            return Response({"detail": str(error)}, status=409)
        return Response(status_payload(appointment))


class RazorpayWebhookView(APIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)

    @extend_schema(exclude=True)
    def post(self, request):
        if not gateway.configured():
            return Response(status=503)
        signature = request.headers.get("X-Razorpay-Signature", "")
        event_id = request.headers.get("X-Razorpay-Event-Id", "")
        if not signature or not event_id or len(event_id) > 128 or not gateway.webhook_signature_valid(request.body, signature):
            return Response(status=400)
        try:
            with transaction.atomic():
                event = json.loads(request.body)
                event_type = event["event"]
                _, created = PaymentWebhookEvent.objects.get_or_create(
                    event_id=event_id, defaults={"event_type": event_type[:80]}
                )
                if not created:
                    return Response(status=200)
                if event_type == "payment.captured":
                    payment = event["payload"]["payment"]["entity"]
                    if payment["status"] != "captured":
                        raise ValueError("Uncaptured payment")
                    record_capture(payment["order_id"], payment["id"], payment["amount"], payment["currency"])
                elif event_type in {"refund.processed", "refund.failed"}:
                    refund = event["payload"]["refund"]["entity"]
                    record_refund(refund["id"], refund["payment_id"], refund["amount"], refund["status"])
        except (KeyError, TypeError, ValueError, PaymentError) as error:
            failure, created = WebhookFailure.objects.get_or_create(
                event_id=event_id, defaults={"event_type": str(locals().get("event_type", ""))[:80],
                                             "error_code": type(error).__name__},
            )
            if not created:
                failure.error_code = type(error).__name__
                failure.failed_count += 1
                failure.resolved = False
                failure.save(update_fields=["error_code", "failed_count", "resolved", "last_seen_at"])
            return Response(status=400)
        WebhookFailure.objects.filter(event_id=event_id, resolved=False).update(resolved=True)
        return Response(status=200)
