import uuid

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError


User = get_user_model()


@pytest.mark.django_db
def test_custom_user_is_saved_with_uuid_primary_key():
    user = User.objects.create_user(
        username="test_patient",
        password="safe-test-password-123",
        phone_number="+919876543210",
    )

    saved_user = User.objects.get(pk=user.pk)

    assert isinstance(saved_user.pk, uuid.UUID)
    assert saved_user.username == "test_patient"
    assert saved_user.phone_number == "+919876543210"
    assert saved_user.check_password("safe-test-password-123")


@pytest.mark.django_db
def test_phone_number_rejects_invalid_format():
    user = User(
        username="invalid_phone_user",
        phone_number="9876543210",
    )

    with pytest.raises(ValidationError):
        user.full_clean()


def test_custom_user_is_registered_in_admin():
    assert admin.site.is_registered(User)