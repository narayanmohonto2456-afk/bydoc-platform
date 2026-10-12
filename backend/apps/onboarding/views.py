from django.db import IntegrityError
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ClinicApplication, DoctorApplication
from .serializers import (
    ApplicationStatusOutput,
    ClinicApplicationInput,
    DoctorApplicationInput,
)
from .services import ApplicationError, submit_clinic, submit_doctor


def applicant_status(application):
    if application is None:
        return {"id": None, "status": "not_submitted", "submitted_at": None,
                "reviewed_at": None, "detail": "No application submitted."}
    messages = {
        "pending": "Your details are awaiting independent review.",
        "approved": "Approved. Your account now has the corresponding provider role.",
        "rejected": "This application was not approved. Contact support before resubmitting corrected details.",
    }
    return {
        "id": application.id,
        "status": application.status,
        "submitted_at": application.submitted_at,
        "reviewed_at": application.reviewed_at,
        "detail": messages[application.status],
    }


class DoctorApplicationView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(responses=ApplicationStatusOutput)
    def get(self, request):
        application = DoctorApplication.objects.filter(applicant=request.user).first()
        return Response(applicant_status(application))

    @extend_schema(request=DoctorApplicationInput, responses=ApplicationStatusOutput)
    def post(self, request):
        serializer = DoctorApplicationInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        details = {key: value for key, value in serializer.validated_data.items() if key != "attestation"}
        try:
            application = submit_doctor(request.user, details)
        except (ApplicationError, IntegrityError) as error:
            message = str(error) if isinstance(error, ApplicationError) else "A matching application is already pending."
            return Response({"detail": message}, status=409)
        return Response(applicant_status(application), status=status.HTTP_201_CREATED)


class ClinicApplicationView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(responses=ApplicationStatusOutput)
    def get(self, request):
        application = ClinicApplication.objects.filter(applicant=request.user).first()
        return Response(applicant_status(application))

    @extend_schema(request=ClinicApplicationInput, responses=ApplicationStatusOutput)
    def post(self, request):
        serializer = ClinicApplicationInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        details = {key: value for key, value in serializer.validated_data.items() if key != "attestation"}
        try:
            application = submit_clinic(request.user, details)
        except (ApplicationError, IntegrityError) as error:
            message = str(error) if isinstance(error, ApplicationError) else "An application is already pending."
            return Response({"detail": message}, status=409)
        return Response(applicant_status(application), status=status.HTTP_201_CREATED)
