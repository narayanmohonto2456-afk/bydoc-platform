from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers

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
