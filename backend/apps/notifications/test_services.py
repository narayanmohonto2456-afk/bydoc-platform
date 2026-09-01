from datetime import timedelta
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.appointments.models import AppointmentSlot
from apps.appointments.services import (
    book_held_slot,
    cancel_appointment,
    hold_slot,
)
from apps.clinics.models import Clinic
from apps.doctors.models import (
    DoctorClinicAffiliation,
    DoctorProfile,
)
from apps.organizations.models import Organization

from .models import NotificationOutbox
from .services import (
    NotificationSchedulingError,
    enqueue_appointment_cancellation,
    enqueue_appointment_confirmation,
    enqueue_appointment_created_notifications,
    enqueue_appointment_reminder,
)


pytestmark = pytest.mark.django_db

User = get_user_model()


def create_user(username):
    return User.objects.create_user(
        username=username,
        password="test-password",
    )


def create_confirmed_appointment(
    *,
    hours_from_now=48,
    patient_username="notification-patient",
):
    organization = Organization.objects.create(
        name="Notification Test Organization",
        slug=f"notification-org-{uuid4().hex[:8]}",
        status=Organization.Status.ACTIVE,
    )

    clinic = Clinic.objects.create(
        organization=organization,
        name="Notification Test Clinic",
        slug=f"notification-clinic-{uuid4().hex[:8]}",
        status=Clinic.Status.ACTIVE,
        address_line_1="12 Health Road",
        locality="Salt Lake",
        district="Kolkata",
        state="West Bengal",
        postal_code="700091",
        timezone="Asia/Kolkata",
    )

    doctor_user = create_user(
        f"notification-doctor-{uuid4().hex[:8]}"
    )

    doctor = DoctorProfile.objects.create(
        user=doctor_user,
        display_name="Dr Notification Test",
        status=DoctorProfile.Status.ACTIVE,
    )

    affiliation = DoctorClinicAffiliation.objects.create(
        doctor=doctor,
        clinic=clinic,
        status=DoctorClinicAffiliation.Status.ACTIVE,
        joined_at=timezone.now(),
        accepts_online_bookings=True,
        consultation_fee="500.00",
        currency_code="INR",
        appointment_duration_minutes=15,
    )

    starts_at = timezone.now() + timedelta(
        hours=hours_from_now
    )

    slot = AppointmentSlot.objects.create(
        affiliation=affiliation,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=15),
        status=AppointmentSlot.Status.OPEN,
    )

    patient = create_user(patient_username)

    held_slot = hold_slot(
        slot_id=slot.pk,
        held_by=patient,
    )

    appointment = book_held_slot(
        slot_id=slot.pk,
        hold_token=held_slot.hold_token,
        booking_request_id=uuid4(),
        patient=patient,
        booked_by=patient,
    )

    return appointment


def test_created_notifications_are_idempotent():
    appointment = create_confirmed_appointment()

    first_confirmation, first_reminder = (
        enqueue_appointment_created_notifications(
            appointment
        )
    )

    second_confirmation, second_reminder = (
        enqueue_appointment_created_notifications(
            appointment
        )
    )

    assert first_confirmation.pk == second_confirmation.pk
    assert first_reminder.pk == second_reminder.pk

    assert (
        NotificationOutbox.objects
        .filter(appointment=appointment)
        .count()
        == 2
    )


def test_confirmation_contains_only_minimal_operational_data():
    appointment = create_confirmed_appointment(
        patient_username="minimal-payload-patient"
    )

    notification = enqueue_appointment_confirmation(
        appointment
    )

    assert set(notification.payload) == {
        "booking_reference",
        "appointment_starts_at",
        "appointment_ends_at",
        "doctor_name",
        "clinic_name",
    }

    forbidden_keys = {
        "diagnosis",
        "symptoms",
        "prescription",
        "medical_record",
        "medical_history",
    }

    assert forbidden_keys.isdisjoint(
        notification.payload.keys()
    )


def test_reminder_is_scheduled_24_hours_before_appointment():
    appointment = create_confirmed_appointment(
        hours_from_now=48,
        patient_username="reminder-patient",
    )

    reminder = enqueue_appointment_reminder(
        appointment
    )

    expected_time = (
        appointment.slot.starts_at - timedelta(hours=24)
    )

    assert reminder.scheduled_for == expected_time
    assert (
        reminder.category
        == NotificationOutbox.Category.APPOINTMENT_REMINDER
    )


def test_short_notice_reminder_is_scheduled_immediately():
    appointment = create_confirmed_appointment(
        hours_from_now=2,
        patient_username="short-notice-patient",
    )

    before = timezone.now()

    reminder = enqueue_appointment_reminder(
        appointment
    )

    after = timezone.now()

    assert before <= reminder.scheduled_for <= after


def test_cancellation_cancels_pending_reminder():
    appointment = create_confirmed_appointment(
        patient_username="cancel-notification-patient"
    )

    confirmation, reminder = (
        enqueue_appointment_created_notifications(
            appointment
        )
    )

    appointment = cancel_appointment(
        appointment_id=appointment.pk,
        cancelled_by=appointment.patient,
        cancellation_note="Unable to attend",
    )

    cancellation = enqueue_appointment_cancellation(
        appointment
    )

    reminder.refresh_from_db()
    confirmation.refresh_from_db()

    assert (
        reminder.status
        == NotificationOutbox.Status.CANCELLED
    )
    assert (
        confirmation.status
        == NotificationOutbox.Status.PENDING
    )
    assert (
        cancellation.category
        == NotificationOutbox.Category.APPOINTMENT_CANCELLED
    )
    assert cancellation.recipient == appointment.patient


def test_cancelled_appointment_cannot_receive_confirmation():
    appointment = create_confirmed_appointment(
        patient_username="invalid-confirmation-patient"
    )

    appointment = cancel_appointment(
        appointment_id=appointment.pk,
        cancelled_by=appointment.patient,
        cancellation_note="Cancelled",
    )

    with pytest.raises(
        NotificationSchedulingError,
        match="Only confirmed appointments",
    ):
        enqueue_appointment_confirmation(appointment)


def test_non_positive_reminder_lead_time_is_rejected():
    appointment = create_confirmed_appointment(
        patient_username="invalid-lead-time-patient"
    )

    with pytest.raises(
        NotificationSchedulingError,
        match="greater than zero",
    ):
        enqueue_appointment_reminder(
            appointment,
            lead_time=timedelta(0),
        )