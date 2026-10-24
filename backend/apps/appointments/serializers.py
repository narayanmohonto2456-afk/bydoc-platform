from rest_framework import serializers

from apps.doctors.models import DoctorClinicAffiliation

from .models import Appointment, AppointmentSlot


class PublicProviderSerializer(serializers.ModelSerializer):
    doctor_id = serializers.UUIDField(read_only=True)
    doctor_name = serializers.CharField(source="doctor.display_name", read_only=True)
    specialty = serializers.CharField(source="doctor.primary_specialty.name", read_only=True, allow_null=True)
    languages = serializers.SerializerMethodField()
    clinic_id = serializers.UUIDField(read_only=True)
    clinic_name = serializers.CharField(source="clinic.name", read_only=True)
    locality = serializers.CharField(source="clinic.locality", read_only=True)
    district = serializers.CharField(source="clinic.district", read_only=True)
    state = serializers.CharField(source="clinic.state", read_only=True)
    address = serializers.CharField(source="clinic.address_line_1", read_only=True)
    timezone = serializers.CharField(source="clinic.timezone", read_only=True)
    fee_updated_at = serializers.DateTimeField(read_only=True)
    schedule_updated_at = serializers.DateTimeField(source="clinic.schedule_updated_at", read_only=True, allow_null=True)

    def get_languages(self, obj) -> list[str]:
        return [language.name for language in obj.doctor.languages.all()]

    class Meta:
        model = DoctorClinicAffiliation
        fields = (
            "id", "doctor_id", "doctor_name", "specialty", "languages",
            "clinic_id", "clinic_name", "locality", "district", "state",
            "address", "timezone", "consultation_fee", "currency_code",
            "fee_updated_at", "schedule_updated_at",
        )
        read_only_fields = fields


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
        max_digits=10,
        decimal_places=2,
        read_only=True,
        allow_null=True,
    )
    currency_code = serializers.CharField(read_only=True)

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
