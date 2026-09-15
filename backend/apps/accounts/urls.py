from django.urls import path
from .views import CsrfTokenView, LoginView, LogoutView, MyAccountView, RegistrationView

app_name = "accounts"

urlpatterns = [
    path("csrf/", CsrfTokenView.as_view(), name="csrf"),
    path("register/", RegistrationView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MyAccountView.as_view(), name="me"),
]
