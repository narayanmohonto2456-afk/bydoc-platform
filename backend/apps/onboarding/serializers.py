from django.utils import timezone
from rest_framework import serializers

from .models import ClinicApplication, DoctorApplication


class DoctorApplicationInput(serializers.ModelSerializer):
    attestation = serializers.BooleanField(write_only=True)

    class Meta:
        model = DoctorApplication
        fields = (
            "display_name", "registered_name", "council_name", "registration_number",
            "registration_year", "specialty_name", "attestation",
        )

    def validate_attestation(self, value):
        if not value:
            raise serializers.ValidationError("Confirm that the details are accurate and yours.")
        return value

    def validate_registration_year(self, value):
        if value is not None and not 1900 <= value <= timezone.localdate().year:
            raise serializers.ValidationError("Enter a valid registration year.")
        return value


class ClinicApplicationInput(serializers.ModelSerializer):
    attestation = serializers.BooleanField(write_only=True)

    class Meta:
        model = ClinicApplication
        fields = (
            "clinic_name", "manager_name", "registration_authority", "registration_number",
            "phone_number", "email", "address_line_1", "locality", "district", "state",
            "postal_code", "attestation",
        )

    def validate_attestation(self, value):
        if not value:
            raise serializers.ValidationError("Confirm that you are authorized to represent this clinic.")
        return value


class ApplicationStatusOutput(serializers.Serializer):
    id = serializers.UUIDField(allow_null=True)
    status = serializers.CharField()
    submitted_at = serializers.DateTimeField(allow_null=True)
    reviewed_at = serializers.DateTimeField(allow_null=True)
    detail = serializers.CharField()
