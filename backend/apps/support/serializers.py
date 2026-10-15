from rest_framework import serializers

from .models import SupportCase, SupportCaseEvent


class CreateSupportCaseSerializer(serializers.Serializer):
    """
    Validate patient-submitted operational support information.

    The requester, organization and priority are not accepted from the
    client. They are determined by authentication and related records.
    """

    category = serializers.ChoiceField(
        choices=SupportCase.Category.choices,
    )

    subject = serializers.CharField(
        max_length=160,
        trim_whitespace=True,
    )

    description = serializers.CharField(
        max_length=3000,
        trim_whitespace=True,
    )

    clinic_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )

    appointment_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )

    def validate_subject(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Subject is required."
            )

        return value

    def validate_description(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Description is required."
            )

        return value


class AddSupportCaseCommentSerializer(
    serializers.Serializer
):
    message = serializers.CharField(
        max_length=3000,
        trim_whitespace=True,
    )

    def validate_message(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Comment is required."
            )

        return value


class SupportCaseEventSerializer(
    serializers.ModelSerializer
):
    actor_role = serializers.SerializerMethodField()

    class Meta:
        model = SupportCaseEvent
        fields = (
            "id",
            "event_type",
            "actor_role",
            "previous_status",
            "new_status",
            "message",
            "created_at",
        )
        read_only_fields = fields

    def get_actor_role(self, event) -> str:
        if event.actor_id is None:
            return "system"

        if event.actor_id == event.case.requester_id:
            return "requester"

        return "support"


class SupportCaseListSerializer(
    serializers.ModelSerializer
):
    clinic_id = serializers.UUIDField(
        read_only=True,
        allow_null=True,
    )

    appointment_id = serializers.UUIDField(
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = SupportCase
        fields = (
            "id",
            "reference",
            "category",
            "priority",
            "status",
            "subject",
            "clinic_id",
            "appointment_id",
            "resolved_at",
            "closed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class SupportCaseDetailSerializer(
    serializers.ModelSerializer
):
    clinic_id = serializers.UUIDField(
        read_only=True,
        allow_null=True,
    )

    appointment_id = serializers.UUIDField(
        read_only=True,
        allow_null=True,
    )

    events = SupportCaseEventSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = SupportCase
        fields = (
            "id",
            "reference",
            "category",
            "priority",
            "status",
            "subject",
            "description",
            "clinic_id",
            "appointment_id",
            "resolution_summary",
            "resolved_at",
            "closed_at",
            "created_at",
            "updated_at",
            "events",
        )
        read_only_fields = fields


class StaffAssignSupportCaseSerializer(
    serializers.Serializer
):
    assigned_to_id = serializers.UUIDField()
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class StaffChangeSupportCaseStatusSerializer(
    serializers.Serializer
):
    new_status = serializers.ChoiceField(
        choices=SupportCase.Status.choices,
    )

    message = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=3000,
        trim_whitespace=True,
    )

    resolution_summary = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=3000,
        trim_whitespace=True,
    )
