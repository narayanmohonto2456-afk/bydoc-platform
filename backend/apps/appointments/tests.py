import uuid
from datetime import time, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.clinics.models import Clinic
from apps.doctors.models import (
    DoctorClinicAffiliation,
    DoctorProfile,
    DoctorRegistration,
)
from apps.organizations.models import (
    Organization,
    OrganizationMembership,
)

from .models import (
    Appointment,
    AppointmentSlot,
    AvailabilityRule,
    ScheduleException,
)
from .services import (
    AppointmentAuthorizationError,
    AppointmentBookingError,
    InvalidAppointmentStateError,
    InvalidSlotHoldError,
    ScheduleGenerationError,
    SlotUnavailableError,
    book_held_slot,
    cancel_appointment,
    generate_slots_for_date,
    hold_slot,
    release_expired_holds,
)


pytestmark = pytest.mark.django_db

User = get_user_model()


def create_user(username):
    return User.objects.create_user(
        username=username,
        password="test-password",
    )


def create_affiliation():
    organization = Organization.objects.create(
        name="Appointment Group",
        slug="appointment-group",
        status=Organization.Status.ACTIVE,
    )

    clinic = Clinic.objects.create(
        organization=organization,
        name="Appointment Clinic",
        slug="appointment-clinic",
        status=Clinic.Status.ACTIVE,
        address_line_1="12 Health Road",
        locality="Salt Lake",
        district="Kolkata",
        state="West Bengal",
        postal_code="700091",
    )

    doctor_user = create_user("appointment-doctor")
    doctor = DoctorProfile.objects.create(
        user=doctor_user,
        display_name="Dr Appointment",
        status=DoctorProfile.Status.ACTIVE,
    )
    DoctorRegistration.objects.create(
        doctor=doctor,
        council_name="Test Council",
        registration_number="appointment-doctor",
        registered_name=doctor.display_name,
        verification_status=DoctorRegistration.VerificationStatus.VERIFIED,
        verified_at=timezone.now(),
        verified_by=doctor_user,
    )

    return DoctorClinicAffiliation.objects.create(
        doctor=doctor,
        clinic=clinic,
        status=DoctorClinicAffiliation.Status.ACTIVE,
        joined_at=timezone.now(),
        accepts_online_bookings=True,
    )


def create_slot(affiliation, hours_from_now=24):
    starts_at = timezone.now() + timedelta(
        hours=hours_from_now
    )

    return AppointmentSlot.objects.create(
        affiliation=affiliation,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=15),
    )


def test_nearby_clinics_only_shows_active_bookable_locations(client):
    affiliation = create_affiliation()
    clinic = affiliation.clinic
    clinic.latitude = 22.572645
    clinic.longitude = 88.363892
    clinic.save(update_fields=["latitude", "longitude"])

    response = client.get(
        "/api/v1/appointments/nearby-clinics/",
        {"latitude": "22.5726", "longitude": "88.3639", "radius_km": "10"},
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [str(clinic.pk)]
    assert response.json()[0]["distance_km"] < 1

    affiliation.accepts_online_bookings = False
    affiliation.save(update_fields=["accepts_online_bookings"])
    assert client.get(
        "/api/v1/appointments/nearby-clinics/",
        {"latitude": "22.5726", "longitude": "88.3639"},
    ).json() == []


def test_nearby_clinic_parameters_are_bounded(client):
    response = client.get(
        "/api/v1/appointments/nearby-clinics/",
        {"latitude": "91", "longitude": "88", "radius_km": "1000"},
    )
    assert response.status_code == 400


def test_user_can_hold_an_open_slot():
    user = create_user("holding-user")
    slot = create_slot(create_affiliation())

    held_slot = hold_slot(slot.pk, user)

    assert held_slot.status == AppointmentSlot.Status.HELD
    assert held_slot.held_by == user
    assert held_slot.hold_token is not None
    assert held_slot.hold_expires_at > timezone.now()


def test_another_user_cannot_take_active_hold():
    first_user = create_user("first-holding-user")
    second_user = create_user("second-holding-user")
    slot = create_slot(create_affiliation())

    hold_slot(slot.pk, first_user)

    with pytest.raises(SlotUnavailableError):
        hold_slot(slot.pk, second_user)

    slot.refresh_from_db()

    assert slot.held_by == first_user


def test_expired_hold_can_be_reclaimed():
    first_user = create_user("expired-hold-user")
    second_user = create_user("replacement-user")
    slot = create_slot(create_affiliation())

    hold_slot(slot.pk, first_user)

    AppointmentSlot.objects.filter(pk=slot.pk).update(
        hold_expires_at=timezone.now() - timedelta(seconds=1)
    )

    reclaimed_slot = hold_slot(slot.pk, second_user)

    assert reclaimed_slot.held_by == second_user
    assert reclaimed_slot.hold_expires_at > timezone.now()


def test_valid_hold_creates_one_confirmed_appointment():
    user = create_user("booking-user")
    slot = create_slot(create_affiliation())
    held_slot = hold_slot(slot.pk, user)

    appointment = book_held_slot(
        slot_id=slot.pk,
        hold_token=held_slot.hold_token,
        patient=user,
        booked_by=user,
    )

    slot.refresh_from_db()

    assert appointment.status == Appointment.Status.CONFIRMED
    assert appointment.patient == user
    assert appointment.booked_by == user
    assert slot.status == AppointmentSlot.Status.BOOKED
    assert slot.held_by is None
    assert slot.hold_token is None
    assert slot.hold_expires_at is None
    assert Appointment.objects.count() == 1


def test_incorrect_hold_token_is_rejected():
    user = create_user("invalid-token-user")
    slot = create_slot(create_affiliation())
    hold_slot(slot.pk, user)

    with pytest.raises(InvalidSlotHoldError):
        book_held_slot(
            slot_id=slot.pk,
            hold_token=uuid.uuid4(),
            patient=user,
            booked_by=user,
        )

    assert not Appointment.objects.exists()


def test_expired_hold_cannot_be_booked():
    user = create_user("expired-booking-user")
    slot = create_slot(create_affiliation())
    held_slot = hold_slot(slot.pk, user)

    AppointmentSlot.objects.filter(pk=slot.pk).update(
        hold_expires_at=timezone.now() - timedelta(seconds=1)
    )

    with pytest.raises(InvalidSlotHoldError):
        book_held_slot(
            slot_id=slot.pk,
            hold_token=held_slot.hold_token,
            patient=user,
            booked_by=user,
        )

    assert not Appointment.objects.exists()


def test_booked_slot_cannot_create_second_appointment():
    user = create_user("duplicate-booking-user")
    slot = create_slot(create_affiliation())
    held_slot = hold_slot(slot.pk, user)

    book_held_slot(
        slot_id=slot.pk,
        hold_token=held_slot.hold_token,
        patient=user,
        booked_by=user,
    )

    with pytest.raises(InvalidSlotHoldError):
        book_held_slot(
            slot_id=slot.pk,
            hold_token=held_slot.hold_token,
            patient=user,
            booked_by=user,
        )

    assert Appointment.objects.count() == 1


def test_expired_holds_are_released():
    user = create_user("release-hold-user")
    slot = create_slot(create_affiliation())
    hold_slot(slot.pk, user)

    AppointmentSlot.objects.filter(pk=slot.pk).update(
        hold_expires_at=timezone.now() - timedelta(seconds=1)
    )

    released_count = release_expired_holds()

    slot.refresh_from_db()

    assert released_count == 1
    assert slot.status == AppointmentSlot.Status.OPEN
    assert slot.held_by is None
    assert slot.hold_token is None
    assert slot.hold_expires_at is None


def test_blocked_slot_cannot_be_held():
    user = create_user("blocked-slot-user")
    slot = create_slot(create_affiliation())

    slot.status = AppointmentSlot.Status.BLOCKED
    slot.save(update_fields=["status", "updated_at"])

    with pytest.raises(SlotUnavailableError):
        hold_slot(slot.pk, user)

def future_clinic_date():
    clinic_timezone = ZoneInfo("Asia/Kolkata")

    return (
        timezone.localdate(timezone=clinic_timezone)
        + timedelta(days=7)
    )


def create_availability_rule(
    affiliation,
    target_date,
    start=time(10, 0),
    end=time(11, 0),
):
    return AvailabilityRule.objects.create(
        affiliation=affiliation,
        weekday=target_date.weekday(),
        start_time=start,
        end_time=end,
        valid_from=target_date,
        is_active=True,
    )


def local_start_times(slots):
    clinic_timezone = ZoneInfo("Asia/Kolkata")

    return [
        (
            slot.starts_at
            .astimezone(clinic_timezone)
            .hour,
            slot.starts_at
            .astimezone(clinic_timezone)
            .minute,
        )
        for slot in slots
    ]


def test_availability_rule_generates_expected_slots():
    affiliation = create_affiliation()
    target_date = future_clinic_date()

    create_availability_rule(
        affiliation=affiliation,
        target_date=target_date,
    )

    slots = list(
        generate_slots_for_date(
            affiliation,
            target_date,
        )
    )

    assert len(slots) == 4
    assert local_start_times(slots) == [
        (10, 0),
        (10, 15),
        (10, 30),
        (10, 45),
    ]


def test_slot_generation_is_duplicate_safe():
    affiliation = create_affiliation()
    target_date = future_clinic_date()

    create_availability_rule(
        affiliation=affiliation,
        target_date=target_date,
    )

    generate_slots_for_date(
        affiliation,
        target_date,
    )
    generate_slots_for_date(
        affiliation,
        target_date,
    )

    assert AppointmentSlot.objects.filter(
        affiliation=affiliation,
    ).count() == 4


def test_closed_day_generates_no_slots():
    affiliation = create_affiliation()
    target_date = future_clinic_date()

    create_availability_rule(
        affiliation=affiliation,
        target_date=target_date,
    )

    ScheduleException.objects.create(
        affiliation=affiliation,
        exception_date=target_date,
        exception_type=ScheduleException.Type.CLOSED,
        public_note="Clinic closed",
    )

    slots = generate_slots_for_date(
        affiliation,
        target_date,
    )

    assert not slots.exists()
    assert not AppointmentSlot.objects.filter(
        affiliation=affiliation,
    ).exists()


def test_unavailable_period_removes_overlapping_slots():
    affiliation = create_affiliation()
    target_date = future_clinic_date()

    create_availability_rule(
        affiliation=affiliation,
        target_date=target_date,
    )

    ScheduleException.objects.create(
        affiliation=affiliation,
        exception_date=target_date,
        exception_type=(
            ScheduleException.Type.UNAVAILABLE
        ),
        start_time=time(10, 15),
        end_time=time(10, 45),
        public_note="Doctor unavailable",
    )

    slots = list(
        generate_slots_for_date(
            affiliation,
            target_date,
        )
    )

    assert local_start_times(slots) == [
        (10, 0),
        (10, 45),
    ]


def test_custom_hours_replace_normal_availability():
    affiliation = create_affiliation()
    target_date = future_clinic_date()

    create_availability_rule(
        affiliation=affiliation,
        target_date=target_date,
        start=time(10, 0),
        end=time(11, 0),
    )

    ScheduleException.objects.create(
        affiliation=affiliation,
        exception_date=target_date,
        exception_type=(
            ScheduleException.Type.CUSTOM_HOURS
        ),
        start_time=time(14, 0),
        end_time=time(14, 30),
        public_note="Afternoon schedule",
    )

    slots = list(
        generate_slots_for_date(
            affiliation,
            target_date,
        )
    )

    assert local_start_times(slots) == [
        (14, 0),
        (14, 15),
    ]


def test_inactive_affiliation_cannot_generate_slots():
    affiliation = create_affiliation()
    target_date = future_clinic_date()

    affiliation.status = (
        DoctorClinicAffiliation.Status.SUSPENDED
    )
    affiliation.save(
        update_fields=["status", "updated_at"]
    )

    with pytest.raises(ScheduleGenerationError):
        generate_slots_for_date(
            affiliation,
            target_date,
        )


def create_confirmed_appointment(
    username="cancellation-patient",
):
    patient = create_user(username)
    slot = create_slot(create_affiliation())
    held_slot = hold_slot(slot.pk, patient)

    appointment = book_held_slot(
        slot_id=slot.pk,
        hold_token=held_slot.hold_token,
        patient=patient,
        booked_by=patient,
    )

    return appointment, slot, patient


def test_patient_can_cancel_confirmed_appointment():
    appointment, slot, patient = (
        create_confirmed_appointment()
    )

    cancelled = cancel_appointment(
        appointment_id=appointment.pk,
        cancelled_by=patient,
        cancellation_note="Unable to attend",
    )

    slot.refresh_from_db()

    assert cancelled.status == Appointment.Status.CANCELLED
    assert cancelled.cancelled_by == patient
    assert cancelled.cancelled_at is not None
    assert cancelled.cancellation_note == "Unable to attend"
    assert slot.status == AppointmentSlot.Status.OPEN


def test_repeated_cancellation_is_idempotent():
    appointment, slot, patient = (
        create_confirmed_appointment(
            username="idempotent-cancellation-user",
        )
    )

    first_result = cancel_appointment(
        appointment_id=appointment.pk,
        cancelled_by=patient,
        cancellation_note="First cancellation",
    )
    first_cancelled_at = first_result.cancelled_at

    second_result = cancel_appointment(
        appointment_id=appointment.pk,
        cancelled_by=patient,
        cancellation_note="Repeated request",
    )

    slot.refresh_from_db()

    assert second_result.status == Appointment.Status.CANCELLED
    assert second_result.cancelled_at == first_cancelled_at
    assert (
        second_result.cancellation_note
        == "First cancellation"
    )
    assert slot.status == AppointmentSlot.Status.OPEN


def test_unrelated_user_cannot_cancel_appointment():
    appointment, slot, _patient = (
        create_confirmed_appointment(
            username="protected-appointment-patient",
        )
    )
    unrelated_user = create_user("unrelated-user")

    with pytest.raises(AppointmentAuthorizationError):
        cancel_appointment(
            appointment_id=appointment.pk,
            cancelled_by=unrelated_user,
        )

    appointment.refresh_from_db()
    slot.refresh_from_db()

    assert appointment.status == Appointment.Status.CONFIRMED
    assert slot.status == AppointmentSlot.Status.BOOKED


def test_active_clinic_staff_can_cancel_appointment():
    appointment, slot, _patient = (
        create_confirmed_appointment(
            username="staff-cancellation-patient",
        )
    )
    staff_user = create_user("appointment-staff")

    organization = (
        slot
        .affiliation
        .clinic
        .organization
    )

    OrganizationMembership.objects.create(
        organization=organization,
        user=staff_user,
        role=OrganizationMembership.Role.RECEPTIONIST,
        status=OrganizationMembership.Status.ACTIVE,
        joined_at=timezone.now(),
    )

    cancelled = cancel_appointment(
        appointment_id=appointment.pk,
        cancelled_by=staff_user,
        cancellation_note="Cancelled by clinic",
    )

    assert cancelled.status == Appointment.Status.CANCELLED
    assert cancelled.cancelled_by == staff_user


def test_completed_appointment_cannot_be_cancelled():
    appointment, slot, patient = (
        create_confirmed_appointment(
            username="completed-appointment-patient",
        )
    )

    appointment.status = Appointment.Status.COMPLETED
    appointment.save(
        update_fields=["status", "updated_at"]
    )

    with pytest.raises(InvalidAppointmentStateError):
        cancel_appointment(
            appointment_id=appointment.pk,
            cancelled_by=patient,
        )

    slot.refresh_from_db()

    assert slot.status == AppointmentSlot.Status.BOOKED


def test_cancellation_blocks_slot_when_clinic_is_inactive():
    appointment, slot, patient = (
        create_confirmed_appointment(
            username="inactive-clinic-patient",
        )
    )

    clinic = slot.affiliation.clinic
    clinic.status = Clinic.Status.SUSPENDED
    clinic.save(
        update_fields=["status", "updated_at"]
    )

    cancel_appointment(
        appointment_id=appointment.pk,
        cancelled_by=patient,
    )

    slot.refresh_from_db()

    assert slot.status == AppointmentSlot.Status.BLOCKED


def test_overlong_cancellation_note_is_rejected_atomically():
    appointment, slot, patient = (
        create_confirmed_appointment(
            username="long-note-patient",
        )
    )

    with pytest.raises(AppointmentBookingError):
        cancel_appointment(
            appointment_id=appointment.pk,
            cancelled_by=patient,
            cancellation_note="x" * 251,
        )

    appointment.refresh_from_db()
    slot.refresh_from_db()

    assert appointment.status == Appointment.Status.CONFIRMED
    assert appointment.cancelled_at is None
    assert slot.status == AppointmentSlot.Status.BOOKED
