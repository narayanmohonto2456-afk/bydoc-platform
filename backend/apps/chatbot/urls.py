from django.urls import path

from .views import ChatStatusView, ChatView

app_name = "chatbot"

urlpatterns = [
    path("status/", ChatStatusView.as_view(), name="status"),
    path("chat/", ChatView.as_view(), name="chat"),
]
