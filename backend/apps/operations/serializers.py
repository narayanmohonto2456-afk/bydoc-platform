from rest_framework import serializers

from apps.support.models import SupportCase

from .models import StaffGrant


class DecisionSerializer(serializers.Serializer):
    approve = serializers.BooleanField()
    note = serializers.CharField(max_length=500)
    checks = serializers.DictField(child=serializers.BooleanField())


class ReasonSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=250)


class InvestigationSerializer(serializers.Serializer):
    resolved = serializers.BooleanField()
    note = serializers.CharField(max_length=500)


class StatusSerializer(ReasonSerializer):
    suspend = serializers.BooleanField()
    checks = serializers.DictField(child=serializers.BooleanField(), required=False, default=dict)


class GrantSerializer(ReasonSerializer):
    role = serializers.ChoiceField(choices=StaffGrant.Role.choices)
    active = serializers.BooleanField()


class EscalationSerializer(ReasonSerializer):
    priority = serializers.ChoiceField(choices=SupportCase.Priority.choices)
