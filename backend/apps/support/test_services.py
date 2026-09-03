import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from .models import SupportCase, SupportCaseEvent
from .services import (
    InvalidSupportCaseDataError,
    InvalidSupportCaseStateError,
    SupportCaseAuthorizationError,
    add_support_case_comment,
    assign_support_case,
    change_support_case_status,
    create_support_case,
)


pytestmark = pytest.mark.django_db

User = get_user_model()


def create_user(username, *, is_staff=False):
    return User.objects.create_user(
        username=username,
        password="test-password",
        is_staff=is_staff,
    )


def create_open_case(requester):
    return create_support_case(
        requester=requester,
        category=SupportCase.Category.APPOINTMENT,
        subject="Appointment support",
        description=(
            "I could not complete an appointment action."
        ),
    )


def test_create_support_case_creates_audit_event():
    requester = create_user("case-requester")

    support_case = create_open_case(requester)

    assert support_case.requester == requester
    assert support_case.status == SupportCase.Status.OPEN

    events = list(support_case.events.all())

    assert len(events) == 1

    event = events[0]

    assert event.actor == requester
    assert (
        event.event_type
        == SupportCaseEvent.EventType.CREATED
    )
    assert event.new_status == SupportCase.Status.OPEN


def test_anonymous_user_cannot_create_case():
    with pytest.raises(
        SupportCaseAuthorizationError,
        match="authenticated",
    ):
        create_support_case(
            requester=AnonymousUser(),
            category=SupportCase.Category.OTHER,
            subject="Support request",
            description="Unable to complete an action.",
        )

    assert SupportCase.objects.count() == 0
    assert SupportCaseEvent.objects.count() == 0


def test_support_case_requires_subject():
    requester = create_user("missing-subject-user")

    with pytest.raises(
        InvalidSupportCaseDataError,
        match="Subject is required",
    ):
        create_support_case(
            requester=requester,
            category=SupportCase.Category.OTHER,
            subject=" ",
            description="An operational problem occurred.",
        )

    assert SupportCase.objects.count() == 0


def test_support_case_requires_description():
    requester = create_user("missing-description-user")

    with pytest.raises(
        InvalidSupportCaseDataError,
        match="Description is required",
    ):
        create_support_case(
            requester=requester,
            category=SupportCase.Category.OTHER,
            subject="Support request",
            description=" ",
        )

    assert SupportCase.objects.count() == 0


def test_staff_can_assign_case_to_staff_member():
    requester = create_user("assignment-requester")
    assigned_by = create_user(
        "assignment-manager",
        is_staff=True,
    )
    assigned_to = create_user(
        "assigned-agent",
        is_staff=True,
    )
    support_case = create_open_case(requester)

    updated_case = assign_support_case(
        case_id=support_case.pk,
        assigned_to=assigned_to,
        assigned_by=assigned_by,
    )

    assert updated_case.assigned_to == assigned_to

    assignment_event = updated_case.events.get(
        event_type=SupportCaseEvent.EventType.ASSIGNED
    )

    assert assignment_event.actor == assigned_by
    assert (
        assignment_event.metadata["new_assignee_id"]
        == str(assigned_to.pk)
    )


def test_non_staff_user_cannot_assign_case():
    requester = create_user("unauthorized-requester")
    ordinary_user = create_user("ordinary-user")
    support_agent = create_user(
        "available-support-agent",
        is_staff=True,
    )
    support_case = create_open_case(requester)

    with pytest.raises(
        SupportCaseAuthorizationError,
        match="staff permission",
    ):
        assign_support_case(
            case_id=support_case.pk,
            assigned_to=support_agent,
            assigned_by=ordinary_user,
        )

    support_case.refresh_from_db()

    assert support_case.assigned_to is None


def test_case_cannot_be_assigned_to_non_staff_user():
    requester = create_user("invalid-assignee-requester")
    manager = create_user(
        "support-manager",
        is_staff=True,
    )
    ordinary_user = create_user("invalid-assignee")
    support_case = create_open_case(requester)

    with pytest.raises(
        SupportCaseAuthorizationError,
        match="staff permission",
    ):
        assign_support_case(
            case_id=support_case.pk,
            assigned_to=ordinary_user,
            assigned_by=manager,
        )

    support_case.refresh_from_db()

    assert support_case.assigned_to is None


def test_repeated_assignment_is_idempotent():
    requester = create_user("repeat-assignment-requester")
    manager = create_user(
        "repeat-assignment-manager",
        is_staff=True,
    )
    agent = create_user(
        "repeat-assignment-agent",
        is_staff=True,
    )
    support_case = create_open_case(requester)

    assign_support_case(
        case_id=support_case.pk,
        assigned_to=agent,
        assigned_by=manager,
    )

    assign_support_case(
        case_id=support_case.pk,
        assigned_to=agent,
        assigned_by=manager,
    )

    assignment_events = support_case.events.filter(
        event_type=SupportCaseEvent.EventType.ASSIGNED
    )

    assert assignment_events.count() == 1


def test_requester_can_add_comment_to_own_case():
    requester = create_user("comment-requester")
    support_case = create_open_case(requester)

    event = add_support_case_comment(
        case_id=support_case.pk,
        actor=requester,
        message="Please help me with this issue.",
    )

    assert (
        event.event_type
        == SupportCaseEvent.EventType.COMMENTED
    )
    assert event.actor == requester
    assert event.message == "Please help me with this issue."


def test_staff_can_add_comment_to_case():
    requester = create_user("staff-comment-requester")
    staff_user = create_user(
        "staff-comment-agent",
        is_staff=True,
    )
    support_case = create_open_case(requester)

    event = add_support_case_comment(
        case_id=support_case.pk,
        actor=staff_user,
        message="We are reviewing your request.",
    )

    assert event.actor == staff_user


def test_unrelated_user_cannot_comment():
    requester = create_user("private-case-requester")
    unrelated_user = create_user("unrelated-comment-user")
    support_case = create_open_case(requester)

    with pytest.raises(
        SupportCaseAuthorizationError,
        match="not found",
    ):
        add_support_case_comment(
            case_id=support_case.pk,
            actor=unrelated_user,
            message="Unauthorized comment.",
        )

    assert not support_case.events.filter(
        event_type=SupportCaseEvent.EventType.COMMENTED
    ).exists()


def test_empty_comment_is_rejected():
    requester = create_user("empty-comment-requester")
    support_case = create_open_case(requester)

    with pytest.raises(
        InvalidSupportCaseDataError,
        match="Comment is required",
    ):
        add_support_case_comment(
            case_id=support_case.pk,
            actor=requester,
            message=" ",
        )


def test_staff_can_move_open_case_to_in_progress():
    requester = create_user("progress-requester")
    staff_user = create_user(
        "progress-agent",
        is_staff=True,
    )
    support_case = create_open_case(requester)

    updated_case = change_support_case_status(
        case_id=support_case.pk,
        changed_by=staff_user,
        new_status=SupportCase.Status.IN_PROGRESS,
        message="Review started.",
    )

    assert (
        updated_case.status
        == SupportCase.Status.IN_PROGRESS
    )

    event = updated_case.events.get(
        event_type=(
            SupportCaseEvent.EventType.STATUS_CHANGED
        )
    )

    assert event.previous_status == SupportCase.Status.OPEN
    assert event.new_status == SupportCase.Status.IN_PROGRESS
    assert event.actor == staff_user


def test_non_staff_user_cannot_change_status():
    requester = create_user("status-requester")
    support_case = create_open_case(requester)

    with pytest.raises(
        SupportCaseAuthorizationError,
        match="staff permission",
    ):
        change_support_case_status(
            case_id=support_case.pk,
            changed_by=requester,
            new_status=SupportCase.Status.IN_PROGRESS,
        )

    support_case.refresh_from_db()

    assert support_case.status == SupportCase.Status.OPEN


def test_invalid_status_transition_is_rejected():
    requester = create_user("invalid-transition-requester")
    staff_user = create_user(
        "invalid-transition-agent",
        is_staff=True,
    )
    support_case = create_open_case(requester)

    with pytest.raises(
        InvalidSupportCaseStateError,
        match="not allowed",
    ):
        change_support_case_status(
            case_id=support_case.pk,
            changed_by=staff_user,
            new_status=SupportCase.Status.RESOLVED,
            resolution_summary="Attempted resolution.",
        )

    support_case.refresh_from_db()

    assert support_case.status == SupportCase.Status.OPEN
    assert support_case.resolved_at is None


def test_resolution_requires_summary():
    requester = create_user("resolution-requester")
    staff_user = create_user(
        "resolution-agent",
        is_staff=True,
    )
    support_case = create_open_case(requester)

    change_support_case_status(
        case_id=support_case.pk,
        changed_by=staff_user,
        new_status=SupportCase.Status.IN_PROGRESS,
    )

    with pytest.raises(
        InvalidSupportCaseDataError,
        match="resolution summary",
    ):
        change_support_case_status(
            case_id=support_case.pk,
            changed_by=staff_user,
            new_status=SupportCase.Status.RESOLVED,
            resolution_summary=" ",
        )

    support_case.refresh_from_db()

    assert (
        support_case.status
        == SupportCase.Status.IN_PROGRESS
    )
    assert support_case.resolved_at is None


def test_case_can_be_resolved_with_summary():
    requester = create_user("resolved-case-requester")
    staff_user = create_user(
        "resolved-case-agent",
        is_staff=True,
    )
    support_case = create_open_case(requester)

    change_support_case_status(
        case_id=support_case.pk,
        changed_by=staff_user,
        new_status=SupportCase.Status.IN_PROGRESS,
    )

    resolved_case = change_support_case_status(
        case_id=support_case.pk,
        changed_by=staff_user,
        new_status=SupportCase.Status.RESOLVED,
        message="The appointment issue was corrected.",
        resolution_summary=(
            "The appointment was restored successfully."
        ),
    )

    assert (
        resolved_case.status
        == SupportCase.Status.RESOLVED
    )
    assert resolved_case.resolved_at is not None
    assert resolved_case.closed_at is None
    assert (
        resolved_case.resolution_summary
        == "The appointment was restored successfully."
    )

    resolved_event = resolved_case.events.get(
        event_type=SupportCaseEvent.EventType.RESOLVED
    )

    assert (
        resolved_event.previous_status
        == SupportCase.Status.IN_PROGRESS
    )
    assert (
        resolved_event.new_status
        == SupportCase.Status.RESOLVED
    )


def test_resolved_case_can_be_reopened():
    requester = create_user("reopen-requester")
    staff_user = create_user(
        "reopen-agent",
        is_staff=True,
    )
    support_case = create_open_case(requester)

    change_support_case_status(
        case_id=support_case.pk,
        changed_by=staff_user,
        new_status=SupportCase.Status.IN_PROGRESS,
    )

    change_support_case_status(
        case_id=support_case.pk,
        changed_by=staff_user,
        new_status=SupportCase.Status.RESOLVED,
        resolution_summary="Initial resolution.",
    )

    reopened_case = change_support_case_status(
        case_id=support_case.pk,
        changed_by=staff_user,
        new_status=SupportCase.Status.IN_PROGRESS,
        message="Additional review is required.",
    )

    assert (
        reopened_case.status
        == SupportCase.Status.IN_PROGRESS
    )
    assert reopened_case.resolved_at is None
    assert reopened_case.closed_at is None
    assert reopened_case.resolution_summary == ""

    reopened_event = reopened_case.events.get(
        event_type=SupportCaseEvent.EventType.REOPENED
    )

    assert (
        reopened_event.previous_status
        == SupportCase.Status.RESOLVED
    )
    assert (
        reopened_event.new_status
        == SupportCase.Status.IN_PROGRESS
    )


def test_resolved_case_can_be_closed():
    requester = create_user("close-requester")
    staff_user = create_user(
        "close-agent",
        is_staff=True,
    )
    support_case = create_open_case(requester)

    change_support_case_status(
        case_id=support_case.pk,
        changed_by=staff_user,
        new_status=SupportCase.Status.IN_PROGRESS,
    )

    change_support_case_status(
        case_id=support_case.pk,
        changed_by=staff_user,
        new_status=SupportCase.Status.RESOLVED,
        resolution_summary="Support issue resolved.",
    )

    closed_case = change_support_case_status(
        case_id=support_case.pk,
        changed_by=staff_user,
        new_status=SupportCase.Status.CLOSED,
        message="Case closed after resolution.",
    )

    assert closed_case.status == SupportCase.Status.CLOSED
    assert closed_case.resolved_at is not None
    assert closed_case.closed_at is not None

    closed_event = closed_case.events.get(
        event_type=SupportCaseEvent.EventType.CLOSED
    )

    assert (
        closed_event.previous_status
        == SupportCase.Status.RESOLVED
    )
    assert (
        closed_event.new_status
        == SupportCase.Status.CLOSED
    )


def test_comment_cannot_be_added_to_closed_case():
    requester = create_user("closed-comment-requester")
    staff_user = create_user(
        "closed-comment-agent",
        is_staff=True,
    )
    support_case = create_open_case(requester)

    change_support_case_status(
        case_id=support_case.pk,
        changed_by=staff_user,
        new_status=SupportCase.Status.IN_PROGRESS,
    )

    change_support_case_status(
        case_id=support_case.pk,
        changed_by=staff_user,
        new_status=SupportCase.Status.RESOLVED,
        resolution_summary="Resolved.",
    )

    change_support_case_status(
        case_id=support_case.pk,
        changed_by=staff_user,
        new_status=SupportCase.Status.CLOSED,
    )

    with pytest.raises(
        InvalidSupportCaseStateError,
        match="closed case",
    ):
        add_support_case_comment(
            case_id=support_case.pk,
            actor=requester,
            message="Late comment.",
        )