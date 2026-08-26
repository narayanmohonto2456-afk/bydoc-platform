from rest_framework import serializers

from .models import Appointment, AppointmentSlot


class PublicAppointmentSlotSerializer(
    serializers.ModelSerializer
):
    doctor_id = serializers.UUIDField(
        source="affiliation.doctor_id",
        read_only=True,
    )
    doctor_name = serializers.CharField(
        source="affiliation.doctor.display_name",
        read_only=True,
    )
    clinic_id = serializers.UUIDField(
        source="affiliation.clinic_id",
        read_only=True,
    )
    clinic_name = serializers.CharField(
        source="affiliation.clinic.name",
        read_only=True,
    )
    consultation_fee = serializers.DecimalField(
        source="affiliation.consultation_fee",
        max_digits=10,
        decimal_places=2,
        read_only=True,
        allow_null=True,
    )
    currency_code = serializers.CharField(
        source="affiliation.currency_code",
        read_only=True,
    )

    class Meta:
        model = AppointmentSlot
        fields = (
            "id",
            "doctor_id",
            "doctor_name",
            "clinic_id",
            "clinic_name",
            "starts_at",
            "ends_at",
            "consultation_fee",
            "currency_code",
        )
        read_only_fields = fields


class SlotHoldSerializer(serializers.ModelSerializer):
    slot_id = serializers.UUIDField(
        source="id",
        read_only=True,
    )

    class Meta:
        model = AppointmentSlot
        fields = (
            "slot_id",
            "hold_token",
            "hold_expires_at",
        )
        read_only_fields = fields


class BookAppointmentSerializer(serializers.Serializer):
    hold_token = serializers.UUIDField()
    booking_request_id = serializers.UUIDField()


class CancelAppointmentSerializer(serializers.Serializer):
    cancellation_note = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=250,
        trim_whitespace=True,
    )


class AppointmentSerializer(serializers.ModelSerializer):
    slot_id = serializers.UUIDField(
        source="slot.id",
        read_only=True,
    )
    starts_at = serializers.DateTimeField(
        source="slot.starts_at",
        read_only=True,
    )
    ends_at = serializers.DateTimeField(
        source="slot.ends_at",
        read_only=True,
    )
    doctor_id = serializers.UUIDField(
        source="slot.affiliation.doctor_id",
        read_only=True,
    )
    doctor_name = serializers.CharField(
        source=(
            "slot.affiliation.doctor.display_name"
        ),
        read_only=True,
    )
    clinic_id = serializers.UUIDField(
        source="slot.affiliation.clinic_id",
        read_only=True,
    )
    clinic_name = serializers.CharField(
        source="slot.affiliation.clinic.name",
        read_only=True,
    )
    consultation_fee = serializers.DecimalField(
        source=(
            "slot.affiliation.consultation_fee"
        ),
        max_digits=10,
        decimal_places=2,
        read_only=True,
        allow_null=True,
    )
    currency_code = serializers.CharField(
        source="slot.affiliation.currency_code",
        read_only=True,
    )

    class Meta:
        model = Appointment
        fields = (
            "id",
            "booking_reference",
            "status",
            "slot_id",
            "starts_at",
            "ends_at",
            "doctor_id",
            "doctor_name",
            "clinic_id",
            "clinic_name",
            "consultation_fee",
            "currency_code",
            "cancelled_at",
            "cancellation_note",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields