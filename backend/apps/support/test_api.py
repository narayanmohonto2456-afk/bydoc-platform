import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.operations.models import StaffGrant

from .models import SupportCase, SupportCaseEvent
from .services import create_support_case


pytestmark = pytest.mark.django_db

User = get_user_model()


def create_user(username, *, is_staff=False):
    user = User.objects.create_user(
        username=username,
        password="test-password",
        is_staff=is_staff,
    )
    if is_staff:
        StaffGrant.objects.create(user=user, role=StaffGrant.Role.SUPPORT, granted_by=user)
    return user


def create_case(requester, subject="Appointment support"):
    return create_support_case(
        requester=requester,
        category=SupportCase.Category.APPOINTMENT,
        subject=subject,
        description=(
            "I could not complete an appointment action."
        ),
    )


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_anonymous_user_cannot_list_support_cases():
    client = APIClient()

    response = client.get(
        reverse("support:case-list-create")
    )

    assert response.status_code in {
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    }


def test_anonymous_user_cannot_create_support_case():
    client = APIClient()

    response = client.post(
        reverse("support:case-list-create"),
        {
            "category": SupportCase.Category.OTHER,
            "subject": "Support request",
            "description": "An operational issue occurred.",
        },
        format="json",
    )

    assert response.status_code in {
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    }
    assert SupportCase.objects.count() == 0


def test_authenticated_user_can_create_support_case():
    requester = create_user("api-case-requester")
    client = authenticated_client(requester)

    response = client.post(
        reverse("support:case-list-create"),
        {
            "category": (
                SupportCase.Category.APPOINTMENT
            ),
            "subject": "Unable to update appointment",
            "description": (
                "The appointment action did not complete."
            ),
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["reference"].startswith("SUP-")
    assert (
        response.data["status"]
        == SupportCase.Status.OPEN
    )
    assert (
        response.data["priority"]
        == SupportCase.Priority.NORMAL
    )
    assert response.data["clinic_id"] is None
    assert response.data["appointment_id"] is None
    assert len(response.data["events"]) == 1
    assert (
        response.data["events"][0]["event_type"]
        == SupportCaseEvent.EventType.CREATED
    )
    assert (
        response.data["events"][0]["actor_role"]
        == "requester"
    )

    support_case = SupportCase.objects.get(
        pk=response.data["id"]
    )

    assert support_case.requester == requester
    assert support_case.assigned_to is None


def test_support_submissions_are_limited_per_account():
    requester = create_user("submission-limit-user")
    client = authenticated_client(requester)
    url = reverse("support:case-list-create")
    payload = {
        "category": SupportCase.Category.OTHER,
        "subject": "App issue",
        "description": "An operational issue occurred.",
    }

    for _ in range(5):
        assert client.post(url, payload, format="json").status_code == 201
    assert client.post(url, payload, format="json").status_code == 429
    assert SupportCase.objects.filter(requester=requester).count() == 5


def test_client_cannot_control_protected_case_fields():
    requester = create_user("protected-fields-user")
    other_user = create_user("protected-other-user")
    client = authenticated_client(requester)

    response = client.post(
        reverse("support:case-list-create"),
        {
            "category": SupportCase.Category.OTHER,
            "subject": "Protected fields",
            "description": "Testing protected fields.",
            "requester": str(other_user.pk),
            "assigned_to": str(other_user.pk),
            "status": SupportCase.Status.CLOSED,
            "priority": SupportCase.Priority.HIGH,
            "resolution_summary": "Client supplied.",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED

    support_case = SupportCase.objects.get(
        pk=response.data["id"]
    )

    assert support_case.requester == requester
    assert support_case.assigned_to is None
    assert support_case.status == SupportCase.Status.OPEN
    assert support_case.priority == SupportCase.Priority.NORMAL
    assert support_case.resolution_summary == ""
    assert support_case.resolved_at is None
    assert support_case.closed_at is None


def test_user_only_lists_own_support_cases():
    first_user = create_user("first-api-support-user")
    second_user = create_user("second-api-support-user")

    first_case = create_case(
        first_user,
        subject="First private case",
    )
    create_case(
        second_user,
        subject="Second private case",
    )

    client = authenticated_client(first_user)

    response = client.get(
        reverse("support:case-list-create")
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]["id"] == str(first_case.pk)
    assert response.data[0]["subject"] == "First private case"


def test_user_can_view_own_support_case_detail():
    requester = create_user("detail-case-user")
    support_case = create_case(requester)
    client = authenticated_client(requester)

    response = client.get(
        reverse(
            "support:case-detail",
            kwargs={"case_id": support_case.pk},
        )
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == str(support_case.pk)
    assert response.data["description"] == (
        "I could not complete an appointment action."
    )
    assert len(response.data["events"]) == 1


def test_unrelated_user_cannot_view_support_case():
    requester = create_user("private-detail-requester")
    unrelated_user = create_user("private-detail-other")
    support_case = create_case(requester)
    client = authenticated_client(unrelated_user)

    response = client.get(
        reverse(
            "support:case-detail",
            kwargs={"case_id": support_case.pk},
        )
    )

    assert (
        response.status_code
        == status.HTTP_404_NOT_FOUND
    )


def test_requester_can_add_comment():
    requester = create_user("api-comment-requester")
    support_case = create_case(requester)
    client = authenticated_client(requester)

    response = client.post(
        reverse(
            "support:case-comment",
            kwargs={"case_id": support_case.pk},
        ),
        {
            "message": "Please provide an update.",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["events"]) == 2

    comment_event = SupportCaseEvent.objects.get(
        case=support_case,
        event_type=SupportCaseEvent.EventType.COMMENTED,
    )

    assert comment_event.actor == requester
    assert comment_event.message == "Please provide an update."


def test_unrelated_user_cannot_comment():
    requester = create_user("private-comment-requester")
    unrelated_user = create_user("private-comment-other")
    support_case = create_case(requester)
    client = authenticated_client(unrelated_user)

    response = client.post(
        reverse(
            "support:case-comment",
            kwargs={"case_id": support_case.pk},
        ),
        {
            "message": "Unauthorized comment.",
        },
        format="json",
    )

    assert (
        response.status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert not SupportCaseEvent.objects.filter(
        case=support_case,
        event_type=SupportCaseEvent.EventType.COMMENTED,
    ).exists()


def test_non_staff_user_cannot_assign_case():
    requester = create_user("assignment-api-requester")
    support_agent = create_user(
        "assignment-api-agent",
        is_staff=True,
    )
    support_case = create_case(requester)
    client = authenticated_client(requester)

    response = client.post(
        reverse(
            "support:staff-case-assign",
            kwargs={"case_id": support_case.pk},
        ),
        {
            "assigned_to_id": str(support_agent.pk),
        },
        format="json",
    )

    assert response.status_code in {
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    }

    support_case.refresh_from_db()

    assert support_case.assigned_to is None


def test_staff_can_assign_case_to_staff_member():
    requester = create_user("staff-assign-requester")
    manager = create_user(
        "staff-assign-manager",
        is_staff=True,
    )
    support_agent = create_user(
        "staff-assign-agent",
        is_staff=True,
    )
    support_case = create_case(requester)
    client = authenticated_client(manager)

    response = client.post(
        reverse(
            "support:staff-case-assign",
            kwargs={"case_id": support_case.pk},
        ),
        {
            "assigned_to_id": str(support_agent.pk),
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK

    support_case.refresh_from_db()

    assert support_case.assigned_to == support_agent
    assert SupportCaseEvent.objects.filter(
        case=support_case,
        actor=manager,
        event_type=SupportCaseEvent.EventType.ASSIGNED,
    ).exists()


def test_staff_cannot_assign_case_to_non_staff_user():
    requester = create_user("invalid-assign-requester")
    manager = create_user(
        "invalid-assign-manager",
        is_staff=True,
    )
    ordinary_user = create_user("invalid-assign-target")
    support_case = create_case(requester)
    client = authenticated_client(manager)

    response = client.post(
        reverse(
            "support:staff-case-assign",
            kwargs={"case_id": support_case.pk},
        ),
        {
            "assigned_to_id": str(ordinary_user.pk),
        },
        format="json",
    )

    assert (
        response.status_code
        == status.HTTP_404_NOT_FOUND
    )

    support_case.refresh_from_db()

    assert support_case.assigned_to is None


def test_non_staff_user_cannot_change_case_status():
    requester = create_user("status-api-requester")
    support_case = create_case(requester)
    client = authenticated_client(requester)

    response = client.post(
        reverse(
            "support:staff-case-status",
            kwargs={"case_id": support_case.pk},
        ),
        {
            "new_status": SupportCase.Status.IN_PROGRESS,
        },
        format="json",
    )

    assert response.status_code in {
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    }

    support_case.refresh_from_db()

    assert support_case.status == SupportCase.Status.OPEN


def test_staff_can_complete_case_lifecycle():
    requester = create_user("lifecycle-requester")
    staff_user = create_user(
        "lifecycle-support-agent",
        is_staff=True,
    )
    support_case = create_case(requester)
    client = authenticated_client(staff_user)

    progress_response = client.post(
        reverse(
            "support:staff-case-status",
            kwargs={"case_id": support_case.pk},
        ),
        {
            "new_status": SupportCase.Status.IN_PROGRESS,
            "message": "Review started.",
        },
        format="json",
    )

    assert (
        progress_response.status_code
        == status.HTTP_200_OK
    )
    assert (
        progress_response.data["status"]
        == SupportCase.Status.IN_PROGRESS
    )

    resolved_response = client.post(
        reverse(
            "support:staff-case-status",
            kwargs={"case_id": support_case.pk},
        ),
        {
            "new_status": SupportCase.Status.RESOLVED,
            "message": "Issue corrected.",
            "resolution_summary": (
                "The appointment action was restored."
            ),
        },
        format="json",
    )

    assert (
        resolved_response.status_code
        == status.HTTP_200_OK
    )
    assert (
        resolved_response.data["status"]
        == SupportCase.Status.RESOLVED
    )
    assert resolved_response.data["resolved_at"] is not None
    assert resolved_response.data["closed_at"] is None

    closed_response = client.post(
        reverse(
            "support:staff-case-status",
            kwargs={"case_id": support_case.pk},
        ),
        {
            "new_status": SupportCase.Status.CLOSED,
            "message": "Case closed.",
        },
        format="json",
    )

    assert (
        closed_response.status_code
        == status.HTTP_200_OK
    )
    assert (
        closed_response.data["status"]
        == SupportCase.Status.CLOSED
    )
    assert closed_response.data["closed_at"] is not None

    support_case.refresh_from_db()

    assert support_case.status == SupportCase.Status.CLOSED
    assert support_case.events.filter(
        event_type=SupportCaseEvent.EventType.RESOLVED
    ).exists()
    assert support_case.events.filter(
        event_type=SupportCaseEvent.EventType.CLOSED
    ).exists()


def test_resolution_without_summary_returns_bad_request():
    requester = create_user("summary-api-requester")
    staff_user = create_user(
        "summary-api-agent",
        is_staff=True,
    )
    support_case = create_case(requester)
    client = authenticated_client(staff_user)

    client.post(
        reverse(
            "support:staff-case-status",
            kwargs={"case_id": support_case.pk},
        ),
        {
            "new_status": SupportCase.Status.IN_PROGRESS,
        },
        format="json",
    )

    response = client.post(
        reverse(
            "support:staff-case-status",
            kwargs={"case_id": support_case.pk},
        ),
        {
            "new_status": SupportCase.Status.RESOLVED,
            "resolution_summary": "",
        },
        format="json",
    )

    assert (
        response.status_code
        == status.HTTP_400_BAD_REQUEST
    )

    support_case.refresh_from_db()

    assert (
        support_case.status
        == SupportCase.Status.IN_PROGRESS
    )
    assert support_case.resolved_at is None


def test_closed_case_rejects_new_comments():
    requester = create_user("closed-comment-api-user")
    staff_user = create_user(
        "closed-comment-api-agent",
        is_staff=True,
    )
    support_case = create_case(requester)
    staff_client = authenticated_client(staff_user)

    staff_client.post(
        reverse(
            "support:staff-case-status",
            kwargs={"case_id": support_case.pk},
        ),
        {
            "new_status": SupportCase.Status.IN_PROGRESS,
        },
        format="json",
    )

    staff_client.post(
        reverse(
            "support:staff-case-status",
            kwargs={"case_id": support_case.pk},
        ),
        {
            "new_status": SupportCase.Status.RESOLVED,
            "resolution_summary": "Issue resolved.",
        },
        format="json",
    )

    staff_client.post(
        reverse(
            "support:staff-case-status",
            kwargs={"case_id": support_case.pk},
        ),
        {
            "new_status": SupportCase.Status.CLOSED,
        },
        format="json",
    )

    requester_client = authenticated_client(requester)

    response = requester_client.post(
        reverse(
            "support:case-comment",
            kwargs={"case_id": support_case.pk},
        ),
        {
            "message": "Late comment.",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_409_CONFLICT
