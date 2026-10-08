from rest_framework import serializers


class DashboardRolesSerializer(serializers.Serializer):
    roles = serializers.ListField(child=serializers.CharField())
    preferred = serializers.CharField()


class DashboardAppointmentSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    booking_reference = serializers.UUIDField()
    starts_at = serializers.DateTimeField()
    status = serializers.CharField()
    doctor_name = serializers.CharField()
    clinic_name = serializers.CharField()


class PatientDashboardSerializer(serializers.Serializer):
    upcoming_count = serializers.IntegerField()
    open_support_count = serializers.IntegerField()
    appointments = DashboardAppointmentSerializer(many=True)
    updated_at = serializers.DateTimeField()


class DoctorAffiliationSerializer(serializers.Serializer):
    clinic_name = serializers.CharField()
    status = serializers.CharField()
    accepts_online_bookings = serializers.BooleanField()


class DoctorDashboardSerializer(serializers.Serializer):
    display_name = serializers.CharField()
    profile_status = serializers.CharField()
    registration_status = serializers.CharField()
    upcoming_appointments_count = serializers.IntegerField()
    affiliations = DoctorAffiliationSerializer(many=True)
    updated_at = serializers.DateTimeField()


class ClinicOptionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    status = serializers.CharField()
    role = serializers.CharField()


class ClinicAppointmentSerializer(DashboardAppointmentSerializer):
    patient_name = serializers.CharField()


class ClinicDashboardSerializer(serializers.Serializer):
    clinics = ClinicOptionSerializer(many=True)
    selected_clinic_id = serializers.UUIDField()
    local_date = serializers.DateField()
    timezone = serializers.CharField()
    today_count = serializers.IntegerField()
    confirmed_count = serializers.IntegerField()
    checked_in_count = serializers.IntegerField()
    completed_count = serializers.IntegerField()
    cancelled_count = serializers.IntegerField()
    no_show_count = serializers.IntegerField()
    appointments = ClinicAppointmentSerializer(many=True)
    updated_at = serializers.DateTimeField()


class AdminDashboardSerializer(serializers.Serializer):
    account_count = serializers.IntegerField()
    doctor_count = serializers.IntegerField()
    clinic_count = serializers.IntegerField()
    pending_registrations_count = serializers.IntegerField()
    open_support_count = serializers.IntegerField()
    updated_at = serializers.DateTimeField()
