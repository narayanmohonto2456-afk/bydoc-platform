from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    ChatRequestSerializer,
    ChatResponseSerializer,
    ChatStatusSerializer,
)
from .service import ChatUnavailable, classify, limit_chat, ANSWERS


class ChatStatusView(APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

    @extend_schema(responses={200: ChatStatusSerializer})
    def get(self, request):
        return Response({
            "enabled": settings.ASSISTANT_ENABLED,
            "ai_enabled": settings.ASSISTANT_ENABLED and settings.AI_CHAT_ENABLED,
        })


class ChatView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(request=ChatRequestSerializer, responses={200: ChatResponseSerializer})
    def post(self, request):
        if not settings.ASSISTANT_ENABLED:
            raise ChatUnavailable()
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        limit_chat(request.user.pk)
        topic = classify(
            serializer.validated_data["message"],
            serializer.validated_data.get("history", []),
            use_model=settings.AI_CHAT_ENABLED,
        )
        return Response({"reply": ANSWERS[topic], "topic": topic}, status=status.HTTP_200_OK)
