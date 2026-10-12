from rest_framework import serializers


class VerifyPaymentSerializer(serializers.Serializer):
    razorpay_order_id = serializers.CharField(max_length=64)
    razorpay_payment_id = serializers.CharField(max_length=64)
    razorpay_signature = serializers.CharField(max_length=128)


class PaymentStatusSerializer(serializers.Serializer):
    available = serializers.BooleanField()
    status = serializers.CharField()
    amount_paise = serializers.IntegerField(allow_null=True)
    currency = serializers.CharField()
    refund_id = serializers.CharField(allow_null=True)


class PaymentOrderSerializer(serializers.Serializer):
    key_id = serializers.CharField()
    order_id = serializers.CharField()
    amount_paise = serializers.IntegerField()
    currency = serializers.CharField()
