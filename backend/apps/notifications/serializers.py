from rest_framework import serializers

from .models import InAppNotification


class InAppNotificationSerializer(
    serializers.ModelSerializer
):
    category = serializers.CharField(
        source="outbox.category",
        read_only=True,
    )

    template_key = serializers.CharField(
        source="outbox.template_key",
        read_only=True,
    )

    locale = serializers.CharField(
        source="outbox.locale",
        read_only=True,
    )

    payload = serializers.JSONField(
        source="outbox.payload",
        read_only=True,
    )

    appointment_id = serializers.UUIDField(
        source="outbox.appointment_id",
        read_only=True,
        allow_null=True,
    )

    is_read = serializers.SerializerMethodField()

    class Meta:
        model = InAppNotification
        fields = (
            "id",
            "category",
            "template_key",
            "locale",
            "payload",
            "appointment_id",
            "is_read",
            "read_at",
            "created_at",
        )
        read_only_fields = fields

    def get_is_read(self, obj):
        return obj.read_at is not None

class UnreadCountSerializer(serializers.Serializer):
    unread_count = serializers.IntegerField(
        read_only=True,
        min_value=0,
    )


class MarkAllReadResultSerializer(
    serializers.Serializer
):
    updated_count = serializers.IntegerField(
        read_only=True,
        min_value=0,
    )