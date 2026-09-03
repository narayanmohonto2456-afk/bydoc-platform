from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import (
    generics,
    permissions,
    status,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.appointments.models import Appointment
from apps.clinics.models import Clinic

from .models import SupportCase
from .serializers import (
    AddSupportCaseCommentSerializer,
    CreateSupportCaseSerializer,
    StaffAssignSupportCaseSerializer,
    StaffChangeSupportCaseStatusSerializer,
    SupportCaseDetailSerializer,
    SupportCaseListSerializer,
)
from .services import (
    InvalidSupportCaseDataError,
    InvalidSupportCaseStateError,
    SupportCaseAuthorizationError,
    add_support_case_comment,
    assign_support_case,
    change_support_case_status,
    create_support_case,
)


User = get_user_model()


def support_error_response(error):
    if isinstance(error, SupportCaseAuthorizationError):
        return Response(
            {"detail": "Support case not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if isinstance(error, InvalidSupportCaseStateError):
        return Response(
            {"detail": str(error)},
            status=status.HTTP_409_CONFLICT,
        )

    return Response(
        {"detail": str(error)},
        status=status.HTTP_400_BAD_REQUEST,
    )


class SupportCaseListCreateView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        queryset = (
            SupportCase.objects
            .visible_to(request.user)
            .select_related(
                "clinic",
                "appointment",
            )
            .order_by("-created_at")
        )

        serializer = SupportCaseListSerializer(
            queryset,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = CreateSupportCaseSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        clinic = None
        appointment = None
        organization = None

        clinic_id = serializer.validated_data.get(
            "clinic_id"
        )
        appointment_id = serializer.validated_data.get(
            "appointment_id"
        )

        if appointment_id is not None:
            appointment = get_object_or_404(
                Appointment.objects
                .filter(
                    Q(patient=request.user)
                    | Q(booked_by=request.user)
                )
                .select_related(
                    "slot",
                    "slot__affiliation",
                    "slot__affiliation__clinic",
                    (
                        "slot__affiliation__clinic__"
                        "organization"
                    ),
                ),
                pk=appointment_id,
            )

            appointment_clinic = (
                appointment.slot.affiliation.clinic
            )

            if clinic_id is None:
                clinic = appointment_clinic
            else:
                clinic = get_object_or_404(
                    Clinic.objects.active(),
                    pk=clinic_id,
                )

            organization = clinic.organization

        elif clinic_id is not None:
            clinic = get_object_or_404(
                Clinic.objects.active()
                .select_related("organization"),
                pk=clinic_id,
            )
            organization = clinic.organization

        try:
            support_case = create_support_case(
                requester=request.user,
                category=(
                    serializer.validated_data["category"]
                ),
                subject=(
                    serializer.validated_data["subject"]
                ),
                description=(
                    serializer.validated_data["description"]
                ),
                clinic=clinic,
                organization=organization,
                appointment=appointment,
            )
        except (
            InvalidSupportCaseDataError,
            InvalidSupportCaseStateError,
            SupportCaseAuthorizationError,
        ) as error:
            return support_error_response(error)

        support_case = (
            SupportCase.objects
            .select_related(
                "clinic",
                "appointment",
            )
            .prefetch_related(
                "events",
                "events__actor",
            )
            .get(pk=support_case.pk)
        )

        return Response(
            SupportCaseDetailSerializer(
                support_case
            ).data,
            status=status.HTTP_201_CREATED,
        )


class SupportCaseDetailView(
    generics.RetrieveAPIView
):
    serializer_class = SupportCaseDetailSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_url_kwarg = "case_id"

    def get_queryset(self):
        return (
            SupportCase.objects
            .visible_to(self.request.user)
            .select_related(
                "clinic",
                "appointment",
            )
            .prefetch_related(
                "events",
                "events__actor",
            )
        )


class SupportCaseCommentView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, case_id):
        serializer = AddSupportCaseCommentSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        try:
            add_support_case_comment(
                case_id=case_id,
                actor=request.user,
                message=(
                    serializer.validated_data["message"]
                ),
            )
        except SupportCase.DoesNotExist:
            return Response(
                {"detail": "Support case not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except (
            InvalidSupportCaseDataError,
            InvalidSupportCaseStateError,
            SupportCaseAuthorizationError,
        ) as error:
            return support_error_response(error)

        support_case = (
            SupportCase.objects
            .visible_to(request.user)
            .select_related(
                "clinic",
                "appointment",
            )
            .prefetch_related(
                "events",
                "events__actor",
            )
            .get(pk=case_id)
        )

        return Response(
            SupportCaseDetailSerializer(
                support_case
            ).data,
            status=status.HTTP_200_OK,
        )


class StaffSupportCaseAssignView(APIView):
    permission_classes = (permissions.IsAdminUser,)

    def post(self, request, case_id):
        serializer = StaffAssignSupportCaseSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        assigned_to = get_object_or_404(
            User.objects.filter(
                is_active=True,
                is_staff=True,
            ),
            pk=(
                serializer.validated_data[
                    "assigned_to_id"
                ]
            ),
        )

        try:
            support_case = assign_support_case(
                case_id=case_id,
                assigned_to=assigned_to,
                assigned_by=request.user,
            )
        except SupportCase.DoesNotExist:
            return Response(
                {"detail": "Support case not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except (
            InvalidSupportCaseDataError,
            InvalidSupportCaseStateError,
            SupportCaseAuthorizationError,
        ) as error:
            return support_error_response(error)

        support_case = (
            SupportCase.objects
            .select_related(
                "clinic",
                "appointment",
            )
            .prefetch_related(
                "events",
                "events__actor",
            )
            .get(pk=support_case.pk)
        )

        return Response(
            SupportCaseDetailSerializer(
                support_case
            ).data,
            status=status.HTTP_200_OK,
        )


class StaffSupportCaseStatusView(APIView):
    permission_classes = (permissions.IsAdminUser,)

    def post(self, request, case_id):
        serializer = (
            StaffChangeSupportCaseStatusSerializer(
                data=request.data
            )
        )
        serializer.is_valid(raise_exception=True)

        try:
            support_case = change_support_case_status(
                case_id=case_id,
                changed_by=request.user,
                new_status=(
                    serializer.validated_data[
                        "new_status"
                    ]
                ),
                message=(
                    serializer.validated_data["message"]
                ),
                resolution_summary=(
                    serializer.validated_data[
                        "resolution_summary"
                    ]
                ),
            )
        except SupportCase.DoesNotExist:
            return Response(
                {"detail": "Support case not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except (
            InvalidSupportCaseDataError,
            InvalidSupportCaseStateError,
            SupportCaseAuthorizationError,
        ) as error:
            return support_error_response(error)

        support_case = (
            SupportCase.objects
            .select_related(
                "clinic",
                "appointment",
            )
            .prefetch_related(
                "events",
                "events__actor",
            )
            .get(pk=support_case.pk)
        )

        return Response(
            SupportCaseDetailSerializer(
                support_case
            ).data,
            status=status.HTTP_200_OK,
        )