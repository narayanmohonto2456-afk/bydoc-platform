"""Bounded one-time codes for verified contacts."""

from datetime import timedelta

import boto3
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework.exceptions import APIException, ValidationError

from .models import OtpChallenge, User, VerifiedPhone


OTP_LIFETIME = timedelta(minutes=10)


class SmsUnavailable(APIException):
    status_code = 503
    default_detail = "SMS sign-in is not configured yet. Please use email or password."
    default_code = "sms_unavailable"


def sms_ready():
    return all((
        settings.OTP_SMS_ENABLED,
        settings.AWS_SMS_REGION,
        settings.AWS_SMS_ORIGINATION_ID,
        settings.AWS_SMS_ENTITY_ID,
        settings.AWS_SMS_LOGIN_TEMPLATE_ID,
        settings.AWS_SMS_VERIFY_TEMPLATE_ID,
    ))


def code_for(challenge):
    digest = salted_hmac("bydoc-otp-v1", str(challenge.pk), secret=settings.SECRET_KEY).hexdigest()
    return f"{int(digest, 16) % 1_000_000:06d}"


def create_challenge(user, purpose, channel, destination):
    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.pk)
        OtpChallenge.objects.filter(
            user=user, purpose=purpose, channel=channel, used_at__isnull=True,
        ).update(used_at=timezone.now())
        return OtpChallenge.objects.create(
            user=user, purpose=purpose, channel=channel, destination=destination,
            expires_at=timezone.now() + OTP_LIFETIME,
        )


def consume_challenge(user, purpose, channel, destination, code):
    valid = False
    with transaction.atomic():
        # Match recovery and issuance lock ordering so reset cannot race consumption.
        User.objects.select_for_update().get(pk=user.pk)
        challenge = OtpChallenge.objects.select_for_update().filter(
            user=user, purpose=purpose, channel=channel, destination=destination,
            used_at__isnull=True,
        ).order_by("-created_at").first()
        if (challenge is None or challenge.expires_at <= timezone.now()
                or challenge.attempts >= 5 or challenge.state != OtpChallenge.State.SENT):
            raise ValidationError({"code": "The code is invalid or expired."})
        challenge.attempts += 1
        valid = constant_time_compare(code_for(challenge), code)
        if valid:
            challenge.used_at = timezone.now()
        challenge.save(update_fields=["attempts", "used_at"] if valid else ["attempts"])
    if not valid:
        raise ValidationError({"code": "The code is invalid or expired."})
    return challenge


def deliver_otp(challenge):
    if challenge.expires_at <= timezone.now() or challenge.used_at:
        return
    code = code_for(challenge)
    if challenge.channel == OtpChallenge.Channel.EMAIL:
        send_mail(
            "Your BYdoc sign-in code",
            f"Your BYdoc code is {code}. It expires in 10 minutes. Never share this code.",
            settings.DEFAULT_FROM_EMAIL,
            [challenge.destination],
        )
        return
    if not sms_ready():
        raise SmsUnavailable()
    template = (settings.AWS_SMS_LOGIN_TEMPLATE_ID if challenge.purpose == OtpChallenge.Purpose.LOGIN
                else settings.AWS_SMS_VERIFY_TEMPLATE_ID)
    options = {
        "DestinationPhoneNumber": challenge.destination,
        "OriginationIdentity": settings.AWS_SMS_ORIGINATION_ID,
        "MessageBody": f"BYdoc code: {code}. Expires in 10 minutes. Do not share it.",
        "MessageType": "TRANSACTIONAL",
    }
    if challenge.destination.startswith("+91"):
        options["DestinationCountryParameters"] = {
            "IN_ENTITY_ID": settings.AWS_SMS_ENTITY_ID,
            "IN_TEMPLATE_ID": template,
        }
    boto3.client("pinpoint-sms-voice-v2", region_name=settings.AWS_SMS_REGION).send_text_message(**options)


@transaction.atomic
def confirm_phone(user, code, current_password):
    user = User.objects.select_for_update().get(pk=user.pk)
    if not user.check_password(current_password):
        raise ValidationError({"current_password": "Current password is incorrect."})
    number = user.phone_number
    if not number:
        raise ValidationError({"phone_number": "Add a phone number to your profile first."})
    consume_challenge(
        user, OtpChallenge.Purpose.VERIFY_PHONE,
        OtpChallenge.Channel.SMS, number, code,
    )
    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        if locked_user.phone_number != number:
            raise ValidationError({"phone_number": "The phone number changed. Request a new code."})
        VerifiedPhone.objects.update_or_create(
            user=locked_user, defaults={"number": number, "verified_at": timezone.now()},
        )
