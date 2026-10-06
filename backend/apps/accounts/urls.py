from django.urls import path
from .views import CsrfTokenView, LoginView, LogoutView, MyAccountView, RegistrationView
from .views import VerifyEmailRequestView, VerifyEmailConfirmView, ResetRequestView, ResetConfirmView, MyPatientProfileView
from .views import GoogleSignInView, GoogleLinkView, GoogleStatusView

app_name = "accounts"

urlpatterns = [
    path("csrf/", CsrfTokenView.as_view(), name="csrf"),
    path("register/", RegistrationView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("google/", GoogleSignInView.as_view(), name="google-sign-in"),
    path("google/link/", GoogleLinkView.as_view(), name="google-link"),
    path("google/status/", GoogleStatusView.as_view(), name="google-status"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MyAccountView.as_view(), name="me"),
    path("email/verify/request/", VerifyEmailRequestView.as_view(), name="verify-email-request"),
    path("email/verify/confirm/", VerifyEmailConfirmView.as_view(), name="verify-email-confirm"),
    path("password/reset/request/", ResetRequestView.as_view(), name="reset-request"),
    path("password/reset/confirm/", ResetConfirmView.as_view(), name="reset-confirm"),
        path(
        "profile/",
        MyPatientProfileView.as_view(),
        name="my-patient-profile",
    ),
]
