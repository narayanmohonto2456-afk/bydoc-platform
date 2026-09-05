from datetime import datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.clinics.models import Clinic

from .models import Appointment, AppointmentSlot
from .serializers import (
    AppointmentSerializer,
    BookAppointmentSerializer,
    CancelAppointmentSerializer,
    PublicAppointmentSlotSerializer,
    SlotHoldSerializer,
)
from .services import (
    AppointmentAuthorizationError,
    AppointmentBookingError,
    InvalidAppointmentStateError,
    InvalidSlotHoldError,
    SlotUnavailableError,
    book_held_slot,
    cancel_appointment,
    hold_slot,
)
from drf_spectacular.utils import extend_schema

def parse_uuid_parameter(value, parameter_name):
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValidationError(
            {
                parameter_name: (
                    f"{parameter_name} must be a valid UUID."
                )
            }
        ) from error


class PublicSlotListView(generics.ListAPIView):
    """
    List genuinely available slots for one active clinic and date.

    Query parameters:
    - clinic_id: required
    - date: required, YYYY-MM-DD
    - doctor_id: optional
    """

    serializer_class = PublicAppointmentSlotSerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        clinic_value = self.request.query_params.get(
            "clinic_id"
        )
        date_value = self.request.query_params.get("date")
        doctor_value = self.request.query_params.get(
            "doctor_id"
        )

        errors = {}

        if not clinic_value:
            errors["clinic_id"] = "clinic_id is required."

        if not date_value:
            errors["date"] = "date is required."

        if errors:
            raise ValidationError(errors)

        clinic_id = parse_uuid_parameter(
            clinic_value,
            "clinic_id",
        )
        target_date = parse_date(date_value)

        if target_date is None:
            raise ValidationError(
                {
                    "date": (
                        "Enter a valid date in YYYY-MM-DD format."
                    )
                }
            )

        clinic = get_object_or_404(
            Clinic.objects.active(),
            pk=clinic_id,
        )

        try:
            clinic_timezone = ZoneInfo(clinic.timezone)
        except ZoneInfoNotFoundError as error:
            raise ValidationError(
                {
                    "clinic_id": (
                        "The clinic timezone is invalid."
                    )
                }
            ) from error

        today = timezone.localdate(
            timezone=clinic_timezone
        )

        if target_date < today:
            raise ValidationError(
                {
                    "date": (
                        "Past appointment dates are not allowed."
                    )
                }
            )

        if target_date > today + timedelta(days=90):
            raise ValidationError(
                {
                    "date": (
                        "Appointments can only be viewed "
                        "up to 90 days ahead."
                    )
                }
            )

        local_day_start = datetime.combine(
            target_date,
            time.min,
            tzinfo=clinic_timezone,
        )
        local_next_day = local_day_start + timedelta(days=1)

        queryset = (
            AppointmentSlot.objects
            .available()
            .filter(
                affiliation__clinic=clinic,
                starts_at__gte=max(
                    local_day_start,
                    timezone.now(),
                ),
                starts_at__lt=local_next_day,
            )
            .select_related(
                "affiliation",
                "affiliation__doctor",
                "affiliation__clinic",
            )
            .order_by("starts_at")
        )

        if doctor_value:
            doctor_id = parse_uuid_parameter(
                doctor_value,
                "doctor_id",
            )
            queryset = queryset.filter(
                affiliation__doctor_id=doctor_id,
            )

        return queryset


class HoldSlotView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = SlotHoldSerializer

    @extend_schema(
        request=None,
        responses=SlotHoldSerializer,
    )
    def post(self, request, slot_id):
        try:
            slot = hold_slot(
                slot_id=slot_id,
                held_by=request.user,
            )
        except AppointmentSlot.DoesNotExist:
            return Response(
                {"detail": "Appointment slot not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except SlotUnavailableError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_409_CONFLICT,
            )
        except AppointmentBookingError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            SlotHoldSerializer(slot).data,
            status=status.HTTP_200_OK,
        )


class BookSlotView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = BookAppointmentSerializer

    @extend_schema(
        request=BookAppointmentSerializer,
        responses=AppointmentSerializer,
    )
    def post(self, request, slot_id):
        serializer = BookAppointmentSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        try:
            appointment = book_held_slot(
                slot_id=slot_id,
                hold_token=(
                    serializer.validated_data["hold_token"]
                ),
                booking_request_id=(
                    serializer.validated_data[
                        "booking_request_id"
                    ]
                ),
                patient=request.user,
                booked_by=request.user,
            )
        except AppointmentSlot.DoesNotExist:
            return Response(
                {"detail": "Appointment slot not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except (
            InvalidSlotHoldError,
            SlotUnavailableError,
        ) as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_409_CONFLICT,
            )
        except AppointmentBookingError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # HTTP 200 supports idempotent retries: a repeated request
        # returns the original appointment representation.
        return Response(
            AppointmentSerializer(appointment).data,
            status=status.HTTP_200_OK,
        )


class MyAppointmentListView(generics.ListAPIView):
    serializer_class = AppointmentSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return (
            Appointment.objects
            .filter(
                Q(patient=self.request.user)
                | Q(booked_by=self.request.user)
            )
            .select_related(
                "slot",
                "slot__affiliation",
                "slot__affiliation__doctor",
                "slot__affiliation__clinic",
                "patient",
                "booked_by",
            )
            .distinct()
            .order_by("-slot__starts_at")
        )


class CancelAppointmentView(
    generics.GenericAPIView
):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = CancelAppointmentSerializer

    @extend_schema(
        request=CancelAppointmentSerializer,
        responses=AppointmentSerializer,
    )
    def post(self, request, appointment_id):
        serializer = CancelAppointmentSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        try:
            appointment = cancel_appointment(
                appointment_id=appointment_id,
                cancelled_by=request.user,
                cancellation_note=(
                    serializer.validated_data[
                        "cancellation_note"
                    ]
                ),
            )
        except Appointment.DoesNotExist:
            return Response(
                {"detail": "Appointment not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except AppointmentAuthorizationError:
            # Return 404 so unrelated users cannot confirm that
            # another patient's appointment exists.
            return Response(
                {"detail": "Appointment not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except InvalidAppointmentStateError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_409_CONFLICT,
            )
        except AppointmentBookingError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            AppointmentSerializer(appointment).data,
            status=status.HTTP_200_OK,
        )