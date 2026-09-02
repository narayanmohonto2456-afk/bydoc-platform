from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
)
from rest_framework import (
    generics,
    permissions,
    status,
)
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import InAppNotification
from .serializers import (
    InAppNotificationSerializer,
    MarkAllReadResultSerializer,
    UnreadCountSerializer,
)


def recipient_inbox_queryset(user):
    """
    Return only delivered in-app notifications belonging to the
    authenticated user.
    """
    return (
        InAppNotification.objects
        .for_recipient(user)
        .select_related("outbox")
        .order_by("-created_at")
    )


@extend_schema_view(
    get=extend_schema(
        parameters=[
            OpenApiParameter(
                name="unread",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                description=(
                    "Filter by unread or read state."
                ),
            ),
        ],
        responses=InAppNotificationSerializer(
            many=True
        ),
    )
)
class InboxListView(generics.ListAPIView):
    serializer_class = InAppNotificationSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        queryset = recipient_inbox_queryset(
            self.request.user
        )

        unread_value = self.request.query_params.get(
            "unread"
        )

        if unread_value is None:
            return queryset

        normalized_value = unread_value.strip().lower()

        if normalized_value in {"true", "1", "yes"}:
            return queryset.unread()

        if normalized_value in {"false", "0", "no"}:
            return queryset.filter(
                read_at__isnull=False
            )

        raise ValidationError(
            {
                "unread": "Enter true or false.",
            }
        )


class UnreadCountView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(
        responses=UnreadCountSerializer,
    )
    def get(self, request):
        unread_count = (
            recipient_inbox_queryset(request.user)
            .unread()
            .count()
        )

        return Response(
            {
                "unread_count": unread_count,
            },
            status=status.HTTP_200_OK,
        )


class MarkNotificationReadView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(
        request=None,
        responses=InAppNotificationSerializer,
    )
    @transaction.atomic
    def post(self, request, notification_id):
        notification = get_object_or_404(
            recipient_inbox_queryset(request.user)
            .select_for_update(of=("self",)),
            pk=notification_id,
        )

        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(
                update_fields=["read_at"]
            )

        return Response(
            InAppNotificationSerializer(
                notification
            ).data,
            status=status.HTTP_200_OK,
        )


class MarkAllNotificationsReadView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(
        request=None,
        responses=MarkAllReadResultSerializer,
    )
    @transaction.atomic
    def post(self, request):
        updated_count = (
            recipient_inbox_queryset(request.user)
            .unread()
            .update(read_at=timezone.now())
        )

        return Response(
            {
                "updated_count": updated_count,
            },
            status=status.HTTP_200_OK,
        )