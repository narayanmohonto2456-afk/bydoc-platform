from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from apps.operations.models import StaffGrant

from .models import SupportCase, SupportCaseEvent


pytestmark = pytest.mark.django_db

User = get_user_model()


def create_user(username):
    return User.objects.create_user(
        username=username,
        password="test-password",
    )


def create_case(
    requester,
    *,
    category=SupportCase.Category.APPOINTMENT,
    priority=SupportCase.Priority.NORMAL,
    status=SupportCase.Status.OPEN,
    resolved_at=None,
    closed_at=None,
):
    return SupportCase.objects.create(
        requester=requester,
        category=category,
        priority=priority,
        status=status,
        subject="Unable to manage appointment",
        description=(
            "The appointment action did not complete."
        ),
        resolved_at=resolved_at,
        closed_at=closed_at,
    )


def test_support_case_is_created_with_safe_defaults():
    requester = create_user("support-requester")

    support_case = create_case(requester)

    assert support_case.pk is not None
    assert support_case.reference.startswith("SUP-")
    assert support_case.requester == requester
    assert support_case.assigned_to is None
    assert support_case.status == SupportCase.Status.OPEN
    assert support_case.priority == SupportCase.Priority.NORMAL
    assert support_case.resolved_at is None
    assert support_case.closed_at is None
    assert support_case.created_at is not None
    assert support_case.updated_at is not None


def test_support_case_references_are_unique():
    requester = create_user("reference-requester")

    first_case = create_case(requester)
    second_case = create_case(requester)

    assert first_case.reference != second_case.reference


def test_visible_to_only_returns_requester_cases():
    first_user = create_user("first-support-user")
    second_user = create_user("second-support-user")

    first_case = create_case(first_user)
    create_case(second_user)

    visible_cases = SupportCase.objects.visible_to(
        first_user
    )

    assert list(visible_cases) == [first_case]


def test_visible_to_returns_no_cases_for_anonymous_user():
    requester = create_user("anonymous-test-requester")
    create_case(requester)

    visible_cases = SupportCase.objects.visible_to(None)

    assert list(visible_cases) == []


def test_staff_user_can_view_all_cases():
    first_user = create_user("staff-visible-first")
    second_user = create_user("staff-visible-second")

    staff_user = User.objects.create_user(
        username="support-staff",
        password="test-password",
        is_staff=True,
    )
    StaffGrant.objects.create(user=staff_user, role=StaffGrant.Role.SUPPORT, granted_by=staff_user)

    first_case = create_case(first_user)
    second_case = create_case(second_user)

    visible_ids = set(
        SupportCase.objects
        .visible_to(staff_user)
        .values_list("pk", flat=True)
    )

    assert visible_ids == {
        first_case.pk,
        second_case.pk,
    }


def test_active_queryset_excludes_closed_cases():
    requester = create_user("active-case-requester")
    now = timezone.now()

    open_case = create_case(requester)

    create_case(
        requester,
        status=SupportCase.Status.CLOSED,
        resolved_at=now - timedelta(minutes=5),
        closed_at=now,
    )

    assert list(SupportCase.objects.active()) == [open_case]


def test_resolved_case_requires_resolved_timestamp():
    requester = create_user("resolved-state-requester")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create_case(
                requester,
                status=SupportCase.Status.RESOLVED,
                resolved_at=None,
            )


def test_active_case_cannot_have_resolved_timestamp():
    requester = create_user("active-resolved-requester")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create_case(
                requester,
                status=SupportCase.Status.OPEN,
                resolved_at=timezone.now(),
            )


def test_closed_case_requires_both_timestamps():
    requester = create_user("closed-state-requester")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create_case(
                requester,
                status=SupportCase.Status.CLOSED,
                resolved_at=timezone.now(),
                closed_at=None,
            )


def test_non_closed_case_cannot_have_closed_timestamp():
    requester = create_user("invalid-closed-requester")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create_case(
                requester,
                status=SupportCase.Status.IN_PROGRESS,
                closed_at=timezone.now(),
            )


def test_valid_resolved_case_can_be_created():
    requester = create_user("valid-resolved-requester")
    resolved_at = timezone.now()

    support_case = create_case(
        requester,
        status=SupportCase.Status.RESOLVED,
        resolved_at=resolved_at,
    )

    assert support_case.status == SupportCase.Status.RESOLVED
    assert support_case.resolved_at == resolved_at
    assert support_case.closed_at is None


def test_valid_closed_case_can_be_created():
    requester = create_user("valid-closed-requester")
    resolved_at = timezone.now() - timedelta(minutes=5)
    closed_at = timezone.now()

    support_case = create_case(
        requester,
        status=SupportCase.Status.CLOSED,
        resolved_at=resolved_at,
        closed_at=closed_at,
    )

    assert support_case.status == SupportCase.Status.CLOSED
    assert support_case.resolved_at == resolved_at
    assert support_case.closed_at == closed_at


def test_support_case_event_can_be_created():
    requester = create_user("event-requester")
    support_case = create_case(requester)

    event = SupportCaseEvent.objects.create(
        case=support_case,
        actor=requester,
        event_type=SupportCaseEvent.EventType.CREATED,
        message="Support case created.",
    )

    assert event.pk is not None
    assert event.case == support_case
    assert event.actor == requester
    assert (
        event.event_type
        == SupportCaseEvent.EventType.CREATED
    )
    assert event.created_at is not None


def test_system_event_can_have_no_actor():
    requester = create_user("system-event-requester")
    support_case = create_case(requester)

    event = SupportCaseEvent.objects.create(
        case=support_case,
        actor=None,
        event_type=SupportCaseEvent.EventType.COMMENTED,
        message="Automated support update.",
    )

    assert event.actor is None


def test_status_changed_event_requires_status_values():
    requester = create_user("status-event-requester")
    support_case = create_case(requester)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            SupportCaseEvent.objects.create(
                case=support_case,
                actor=requester,
                event_type=(
                    SupportCaseEvent.EventType.STATUS_CHANGED
                ),
                message="Status changed.",
            )


def test_valid_status_changed_event_can_be_created():
    requester = create_user("valid-status-event-user")
    support_case = create_case(requester)

    event = SupportCaseEvent.objects.create(
        case=support_case,
        actor=requester,
        event_type=(
            SupportCaseEvent.EventType.STATUS_CHANGED
        ),
        previous_status=SupportCase.Status.OPEN,
        new_status=SupportCase.Status.IN_PROGRESS,
        message="Support team started reviewing the case.",
    )

    assert event.previous_status == SupportCase.Status.OPEN
    assert (
        event.new_status
        == SupportCase.Status.IN_PROGRESS
    )


def test_support_case_event_cannot_be_updated():
    requester = create_user("immutable-event-requester")
    support_case = create_case(requester)

    event = SupportCaseEvent.objects.create(
        case=support_case,
        actor=requester,
        event_type=SupportCaseEvent.EventType.CREATED,
        message="Original audit entry.",
    )

    event.message = "Changed audit entry."

    with pytest.raises(
        ValidationError,
        match="immutable",
    ):
        event.save()


def test_support_case_event_cannot_be_deleted():
    requester = create_user("protected-event-requester")
    support_case = create_case(requester)

    event = SupportCaseEvent.objects.create(
        case=support_case,
        actor=requester,
        event_type=SupportCaseEvent.EventType.CREATED,
        message="Permanent audit entry.",
    )

    with pytest.raises(
        ValidationError,
        match="cannot be deleted",
    ):
        event.delete()

    assert SupportCaseEvent.objects.filter(
        pk=event.pk
    ).exists()


def test_case_with_audit_history_cannot_be_deleted():
    requester = create_user("protected-case-requester")
    support_case = create_case(requester)

    SupportCaseEvent.objects.create(
        case=support_case,
        actor=requester,
        event_type=SupportCaseEvent.EventType.CREATED,
        message="Permanent audit history.",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            support_case.delete()

    assert SupportCase.objects.filter(
        pk=support_case.pk
    ).exists()
