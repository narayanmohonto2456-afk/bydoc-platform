from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers
from django.utils import timezone

from .models import PatientProfile, phone_validator

User = get_user_model()


class StrictFieldsMixin:
    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise serializers.ValidationError({
                "non_field_errors": ["Unsupported fields were supplied."],
            })
        return super().to_internal_value(data)


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "first_name", "last_name")
        read_only_fields = fields


class RegistrationSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, trim_whitespace=False, max_length=128,
        style={"input_type": "password"},
    )

    class Meta:
        model = User
        fields = ("username", "password", "first_name", "last_name")

    def validate_username(self, value):
        value = User.normalize_username(value)
        try:
            User._meta.get_field("username").run_validators(value)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("This username is unavailable.")
        return value

    def validate(self, attrs):
        candidate = User(**{key: value for key, value in attrs.items() if key != "password"})
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": error.messages}) from error
        return attrs

    def create(self, validated_data):
        try:
            with transaction.atomic():
                return User.objects.create_user(
                    **validated_data, is_staff=False, is_superuser=False,
                )
        except IntegrityError as error:
            if User.objects.filter(username=validated_data["username"]).exists():
                raise serializers.ValidationError({
                    "username": ["This username is unavailable."],
                }) from error
            raise


class LoginSerializer(StrictFieldsMixin, serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(
        write_only=True, trim_whitespace=False, max_length=128,
        style={"input_type": "password"},
    )

    def validate_username(self, value):
        return User.normalize_username(value)


class CsrfTokenSerializer(serializers.Serializer):
    csrf_token = serializers.CharField(read_only=True)


class LoginResponseSerializer(serializers.Serializer):
    user = AccountSerializer(read_only=True)
    csrf_token = serializers.CharField(read_only=True)


class AuthErrorSerializer(serializers.Serializer):
    detail = serializers.CharField(read_only=True)


class VerifyRequestSerializer(StrictFieldsMixin, serializers.Serializer):
    address = serializers.EmailField(max_length=254)
    current_password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)


class ResetRequestSerializer(StrictFieldsMixin, serializers.Serializer):
    address = serializers.EmailField(max_length=254)


class TokenSerializer(StrictFieldsMixin, serializers.Serializer):
    token = serializers.CharField(trim_whitespace=False, max_length=2048)


class ResetConfirmSerializer(TokenSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)

class PatientProfileSerializer(
    StrictFieldsMixin,
    serializers.Serializer,
):
    first_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=150,
    )
    last_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=150,
    )
    phone_number = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=16,
    )
    date_of_birth = serializers.DateField(
        required=False,
        allow_null=True,
    )
    gender = serializers.ChoiceField(
        choices=PatientProfile.Gender.choices,
        required=False,
        allow_blank=True,
    )
    emergency_contact_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=150,
    )
    emergency_contact_phone = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=16,
    )

    def validate_phone_number(self, value):
        if not value:
            return None

        try:
            phone_validator(value)
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                error.messages
            ) from error

        user = self.instance.user if self.instance else None

        if (
            User.objects.filter(phone_number=value)
            .exclude(pk=user.pk if user else None)
            .exists()
        ):
            raise serializers.ValidationError(
                "This phone number is already in use."
            )

        return value

    def validate_emergency_contact_phone(self, value):
        if not value:
            return ""

        try:
            phone_validator(value)
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                error.messages
            ) from error

        return value

    def validate_date_of_birth(self, value):
        if value is not None and value > timezone.localdate():
            raise serializers.ValidationError(
                "Date of birth cannot be in the future."
            )

        return value

    def validate(self, attrs):
        profile = self.instance

        emergency_name = attrs.get(
            "emergency_contact_name",
            profile.emergency_contact_name if profile else "",
        )
        emergency_phone = attrs.get(
            "emergency_contact_phone",
            profile.emergency_contact_phone if profile else "",
        )

        if bool(emergency_name) != bool(emergency_phone):
            raise serializers.ValidationError(
                {
                    "emergency_contact_name": (
                        "Emergency contact name and phone "
                        "must be provided together."
                    ),
                    "emergency_contact_phone": (
                        "Emergency contact name and phone "
                        "must be provided together."
                    ),
                }
            )

        return attrs

    def update(self, instance, validated_data):
        user_fields = {
            "first_name",
            "last_name",
            "phone_number",
        }

        with transaction.atomic():
            user = instance.user

            for field_name in user_fields:
                if field_name in validated_data:
                    setattr(
                        user,
                        field_name,
                        validated_data.pop(field_name),
                    )

            user.save(
                update_fields=[
                    "first_name",
                    "last_name",
                    "phone_number",
                    "updated_at",
                ]
            )

            for field_name, value in validated_data.items():
                setattr(instance, field_name, value)

            instance.full_clean()
            instance.save()

        return instance

    def to_representation(self, instance):
        return {
            "first_name": instance.user.first_name,
            "last_name": instance.user.last_name,
            "phone_number": instance.user.phone_number,
            "date_of_birth": (
    instance.date_of_birth.isoformat()
    if instance.date_of_birth
    else None
),
            "gender": instance.gender,
            "emergency_contact_name": (
                instance.emergency_contact_name
            ),
            "emergency_contact_phone": (
                instance.emergency_contact_phone
            ),
        }