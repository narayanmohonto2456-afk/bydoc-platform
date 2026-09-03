from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import SupportCase, SupportCaseEvent


class SupportCaseError(Exception):
    """Base exception for support-case operations."""


class SupportCaseAuthorizationError(SupportCaseError):
    """Raised when a user cannot perform an operation."""


class InvalidSupportCaseStateError(SupportCaseError):
    """Raised when a status transition is invalid."""


class InvalidSupportCaseDataError(SupportCaseError):
    """Raised when submitted support data is invalid."""


def _validate_authenticated_user(user, label="user"):
    if (
        user is None
        or not user.is_authenticated
        or user.pk is None
    ):
        raise SupportCaseAuthorizationError(
            f"The {label} must be authenticated."
        )


def _validate_staff_user(user):
    _validate_authenticated_user(user)

    if not user.is_staff and not user.is_superuser:
        raise SupportCaseAuthorizationError(
            "Support staff permission is required."
        )


def _normalize_required_text(value, field_name):
    value = str(value or "").strip()

    if not value:
        raise InvalidSupportCaseDataError(
            f"{field_name} is required."
        )

    return value


def _validate_case_access(support_case, user):
    _validate_authenticated_user(user)

    if user.is_staff or user.is_superuser:
        return

    if support_case.requester_id != user.pk:
        raise SupportCaseAuthorizationError(
            "Support case not found."
        )


def _validate_appointment_access(appointment, requester):
    if appointment is None:
        return

    can_access = (
        appointment.patient_id == requester.pk
        or appointment.booked_by_id == requester.pk
    )

    if not can_access:
        raise SupportCaseAuthorizationError(
            "The appointment is not available."
        )


def _validate_related_objects(
    *,
    appointment=None,
    clinic=None,
    organization=None,
):
    if (
        clinic is not None
        and organization is not None
        and clinic.organization_id != organization.pk
    ):
        raise InvalidSupportCaseDataError(
            "The clinic does not belong to the organization."
        )

    if appointment is None:
        return

    appointment_clinic = (
        appointment.slot.affiliation.clinic
    )
    appointment_organization = (
        appointment_clinic.organization
    )

    if (
        clinic is not None
        and appointment_clinic.pk != clinic.pk
    ):
        raise InvalidSupportCaseDataError(
            "The appointment does not belong to the clinic."
        )

    if (
        organization is not None
        and appointment_organization.pk
        != organization.pk
    ):
        raise InvalidSupportCaseDataError(
            "The appointment does not belong to the organization."
        )


@transaction.atomic
def create_support_case(
    *,
    requester,
    category,
    subject,
    description,
    priority=SupportCase.Priority.NORMAL,
    organization=None,
    clinic=None,
    appointment=None,
):
    """
    Create a support case and its first audit event atomically.
    """
    _validate_authenticated_user(requester, "requester")

    subject = _normalize_required_text(
        subject,
        "Subject",
    )
    description = _normalize_required_text(
        description,
        "Description",
    )

    _validate_appointment_access(
        appointment,
        requester,
    )
    _validate_related_objects(
        appointment=appointment,
        clinic=clinic,
        organization=organization,
    )

    support_case = SupportCase(
        requester=requester,
        organization=organization,
        clinic=clinic,
        appointment=appointment,
        category=category,
        priority=priority,
        subject=subject,
        description=description,
        status=SupportCase.Status.OPEN,
    )

    try:
        support_case.full_clean()
    except ValidationError as error:
        raise InvalidSupportCaseDataError(
            "The support case data is invalid."
        ) from error

    support_case.save()

    SupportCaseEvent.objects.create(
        case=support_case,
        actor=requester,
        event_type=SupportCaseEvent.EventType.CREATED,
        new_status=SupportCase.Status.OPEN,
        message="Support case created.",
    )

    return support_case


@transaction.atomic
def assign_support_case(
    *,
    case_id,
    assigned_to,
    assigned_by,
):
    """
    Assign an active case to an authenticated staff member.
    """
    _validate_staff_user(assigned_by)
    _validate_staff_user(assigned_to)

    support_case = (
        SupportCase.objects
        .select_for_update()
        .get(pk=case_id)
    )

    if support_case.status == SupportCase.Status.CLOSED:
        raise InvalidSupportCaseStateError(
            "A closed support case cannot be assigned."
        )

    previous_assignee_id = support_case.assigned_to_id

    if previous_assignee_id == assigned_to.pk:
        return support_case

    support_case.assigned_to = assigned_to
    support_case.save(
        update_fields=[
            "assigned_to",
            "updated_at",
        ]
    )

    SupportCaseEvent.objects.create(
        case=support_case,
        actor=assigned_by,
        event_type=SupportCaseEvent.EventType.ASSIGNED,
        message="Support case assigned.",
        metadata={
            "previous_assignee_id": (
                str(previous_assignee_id)
                if previous_assignee_id
                else None
            ),
            "new_assignee_id": str(assigned_to.pk),
        },
    )

    return support_case


@transaction.atomic
def add_support_case_comment(
    *,
    case_id,
    actor,
    message,
):
    """
    Add an immutable operational comment to a visible case.
    """
    _validate_authenticated_user(actor)

    message = _normalize_required_text(
        message,
        "Comment",
    )

    support_case = (
        SupportCase.objects
        .select_for_update()
        .get(pk=case_id)
    )

    _validate_case_access(support_case, actor)

    if support_case.status == SupportCase.Status.CLOSED:
        raise InvalidSupportCaseStateError(
            "Comments cannot be added to a closed case."
        )

    event = SupportCaseEvent.objects.create(
        case=support_case,
        actor=actor,
        event_type=SupportCaseEvent.EventType.COMMENTED,
        message=message,
    )

    return event


ALLOWED_STATUS_TRANSITIONS = {
    SupportCase.Status.OPEN: {
        SupportCase.Status.IN_PROGRESS,
    },
    SupportCase.Status.IN_PROGRESS: {
        SupportCase.Status.WAITING_FOR_USER,
        SupportCase.Status.RESOLVED,
    },
    SupportCase.Status.WAITING_FOR_USER: {
        SupportCase.Status.IN_PROGRESS,
        SupportCase.Status.RESOLVED,
    },
    SupportCase.Status.RESOLVED: {
        SupportCase.Status.IN_PROGRESS,
        SupportCase.Status.CLOSED,
    },
    SupportCase.Status.CLOSED: set(),
}


@transaction.atomic
def change_support_case_status(
    *,
    case_id,
    changed_by,
    new_status,
    message="",
    resolution_summary="",
):
    """
    Perform an authorized status transition and append an audit event.
    """
    _validate_staff_user(changed_by)

    support_case = (
        SupportCase.objects
        .select_for_update()
        .get(pk=case_id)
    )

    previous_status = support_case.status

    if new_status == previous_status:
        return support_case

    allowed_statuses = ALLOWED_STATUS_TRANSITIONS.get(
        previous_status,
        set(),
    )

    if new_status not in allowed_statuses:
        raise InvalidSupportCaseStateError(
            "This support case status transition "
            "is not allowed."
        )

    message = str(message or "").strip()
    resolution_summary = str(
        resolution_summary or ""
    ).strip()

    event_type = (
        SupportCaseEvent.EventType.STATUS_CHANGED
    )
    now = timezone.now()

    if new_status == SupportCase.Status.RESOLVED:
        if not resolution_summary:
            raise InvalidSupportCaseDataError(
                "A resolution summary is required."
            )

        support_case.resolution_summary = (
            resolution_summary
        )
        support_case.resolved_at = now
        support_case.closed_at = None
        event_type = SupportCaseEvent.EventType.RESOLVED

    elif (
        previous_status == SupportCase.Status.RESOLVED
        and new_status == SupportCase.Status.IN_PROGRESS
    ):
        support_case.resolution_summary = ""
        support_case.resolved_at = None
        support_case.closed_at = None
        event_type = SupportCaseEvent.EventType.REOPENED

    elif new_status == SupportCase.Status.CLOSED:
        if support_case.resolved_at is None:
            raise InvalidSupportCaseStateError(
                "The case must be resolved before it "
                "can be closed."
            )

        support_case.closed_at = now
        event_type = SupportCaseEvent.EventType.CLOSED

    support_case.status = new_status

    try:
        support_case.full_clean()
    except ValidationError as error:
        raise InvalidSupportCaseDataError(
            "The support case state is invalid."
        ) from error

    support_case.save(
        update_fields=[
            "status",
            "resolution_summary",
            "resolved_at",
            "closed_at",
            "updated_at",
        ]
    )

    SupportCaseEvent.objects.create(
        case=support_case,
        actor=changed_by,
        event_type=event_type,
        previous_status=previous_status,
        new_status=new_status,
        message=message,
    )

    return support_case