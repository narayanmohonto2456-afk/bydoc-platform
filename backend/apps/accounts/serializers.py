from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers
from django.utils import timezone

from .models import AccountRecoveryRequest, PatientProfile, VerifiedEmail, VerifiedPhone, phone_validator
from .recovery import request_link

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
    email = serializers.EmailField(write_only=True, required=False, max_length=254)
    password = serializers.CharField(
        write_only=True, trim_whitespace=False, max_length=128,
        style={"input_type": "password"},
    )

    class Meta:
        model = User
        fields = ("username", "email", "password", "first_name", "last_name")

    def validate_email(self, value):
        value = value.strip().casefold()
        if (VerifiedEmail.objects.filter(address__iexact=value).exists()
                or User.objects.filter(email__iexact=value).exists()):
            raise serializers.ValidationError("This email address is unavailable.")
        return value

    def validate_username(self, value):
        value = User.normalize_username(value)
        if "@" in value:
            raise serializers.ValidationError("Choose a username without @; use the email field for your address.")
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
        address = validated_data.pop("email", None)
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    **validated_data, is_staff=False, is_superuser=False,
                )
                if address:
                    request_link(user, AccountRecoveryRequest.Purpose.VERIFY, address)
                return user
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
        value = User.normalize_username(value)
        return value.casefold() if "@" in value else value


class OtpLoginSerializer(StrictFieldsMixin, serializers.Serializer):
    channel = serializers.ChoiceField(choices=("email", "sms"))
    identifier = serializers.CharField(max_length=254)

    def validate(self, attrs):
        identifier = attrs["identifier"].strip()
        if attrs["channel"] == "email":
            field = serializers.EmailField(max_length=254)
            identifier = field.run_validation(identifier).casefold()
        else:
            try:
                phone_validator(identifier)
            except DjangoValidationError as error:
                raise serializers.ValidationError({"identifier": error.messages}) from error
        attrs["identifier"] = identifier
        return attrs


class OtpConfirmSerializer(OtpLoginSerializer):
    code = serializers.RegexField(regex=r"^[0-9]{6}$", trim_whitespace=False)


class PhoneCodeSerializer(StrictFieldsMixin, serializers.Serializer):
    code = serializers.RegexField(regex=r"^[0-9]{6}$", trim_whitespace=False)


class PhoneStatusSerializer(serializers.Serializer):
    verified = serializers.BooleanField(read_only=True)
    sms_available = serializers.BooleanField(read_only=True)


class OtpAvailabilitySerializer(serializers.Serializer):
    email = serializers.BooleanField(read_only=True)
    sms = serializers.BooleanField(read_only=True)


class GoogleCredentialSerializer(StrictFieldsMixin, serializers.Serializer):
    credential = serializers.CharField(trim_whitespace=False, max_length=4096)


class GoogleStatusSerializer(serializers.Serializer):
    connected = serializers.BooleanField(read_only=True)
    verified_email = serializers.EmailField(read_only=True, allow_null=True)
    has_password = serializers.BooleanField(read_only=True)


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
            previous_phone = user.phone_number

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
            if user.phone_number != previous_phone:
                VerifiedPhone.objects.filter(user=user).delete()

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
