from datetime import date

from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.clinics.models import Clinic
from apps.doctors.models import DoctorClinicAffiliation
from apps.operations.models import OperationsEvent
from apps.organizations.permissions import can_access_clinic

from .models import AvailabilityRule


class AvailabilityRuleInputSerializer(serializers.Serializer):
    affiliation_id = serializers.UUIDField()
    weekday = serializers.IntegerField(min_value=0, max_value=6)
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    valid_from = serializers.DateField()
    valid_until = serializers.DateField(required=False, allow_null=True)
    reason = serializers.CharField(max_length=250, allow_blank=False, trim_whitespace=True)

    def validate(self, attrs):
        if attrs["end_time"] <= attrs["start_time"]:
            raise serializers.ValidationError({"end_time": "End time must follow start time."})
        end_date = attrs.get("valid_until")
        if end_date and end_date < attrs["valid_from"]:
            raise serializers.ValidationError({"valid_until": "End date must follow start date."})
        return attrs


class AvailabilityRuleOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvailabilityRule
        fields = (
            "id", "affiliation", "weekday", "start_time", "end_time",
            "valid_from", "valid_until", "is_active", "updated_at",
        )


class ClinicScheduleRulesView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = AvailabilityRuleInputSerializer

    def _clinic(self, request, clinic_id):
        if not can_access_clinic(request.user, clinic_id):
            raise Http404("Clinic not found.")
        return get_object_or_404(Clinic, pk=clinic_id)

    def get(self, request, clinic_id):
        clinic = self._clinic(request, clinic_id)
        rules = AvailabilityRule.objects.filter(
            affiliation__clinic=clinic,
        ).select_related("affiliation").order_by("weekday", "start_time", "id")
        return Response(AvailabilityRuleOutputSerializer(rules, many=True).data)

    @transaction.atomic
    def post(self, request, clinic_id):
        clinic = self._clinic(request, clinic_id)
        clinic = Clinic.objects.select_for_update().get(pk=clinic.pk)
        if clinic.status != Clinic.Status.ACTIVE:
            raise ValidationError({"clinic_id": "The clinic is not active."})
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        affiliation = DoctorClinicAffiliation.objects.filter(
            pk=data["affiliation_id"],
            clinic=clinic,
            status=DoctorClinicAffiliation.Status.ACTIVE,
        ).first()
        if affiliation is None:
            raise ValidationError({"affiliation_id": "An active doctor at this clinic is required."})
        start_date = data["valid_from"]
        end_date = data.get("valid_until") or date.max
        overlap = AvailabilityRule.objects.filter(
            affiliation=affiliation,
            weekday=data["weekday"],
            is_active=True,
            start_time__lt=data["end_time"],
            end_time__gt=data["start_time"],
            valid_from__lte=end_date,
        ).filter(Q(valid_until__isnull=True) | Q(valid_until__gte=start_date))
        if overlap.exists():
            raise ValidationError({"start_time": "This availability overlaps another active rule."})
        rule = AvailabilityRule.objects.create(
            affiliation=affiliation,
            weekday=data["weekday"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            valid_from=start_date,
            valid_until=data.get("valid_until"),
        )
        clinic.schedule_updated_at = timezone.now()
        clinic.save(update_fields=["schedule_updated_at", "updated_at"])
        OperationsEvent.objects.create(
            actor=request.user,
            action="schedule.rule.created",
            subject_type="availability_rule",
            subject_id=str(rule.pk),
            note=data["reason"],
            metadata={"clinic_id": str(clinic.pk)},
        )
        return Response(
            AvailabilityRuleOutputSerializer(rule).data,
            status=status.HTTP_201_CREATED,
        )
