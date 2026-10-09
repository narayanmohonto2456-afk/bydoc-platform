from django.urls import path
from .views import CsrfTokenView, LoginView, LogoutView, MyAccountView, RegistrationView
from .views import VerifyEmailRequestView, VerifyEmailConfirmView, ResetRequestView, ResetConfirmView, MyPatientProfileView
from .views import GoogleSignInView, GoogleLinkView, GoogleStatusView, TokenRefreshView
from .views import OtpAvailabilityView, OtpLoginRequestView, OtpLoginConfirmView, PhoneVerificationStatusView, PhoneVerificationRequestView, PhoneVerificationConfirmView

app_name = "accounts"

urlpatterns = [
    path("csrf/", CsrfTokenView.as_view(), name="csrf"),
    path("register/", RegistrationView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("otp/request/", OtpLoginRequestView.as_view(), name="otp-request"),
    path("otp/status/", OtpAvailabilityView.as_view(), name="otp-status"),
    path("otp/confirm/", OtpLoginConfirmView.as_view(), name="otp-confirm"),
    path("phone/status/", PhoneVerificationStatusView.as_view(), name="phone-status"),
    path("phone/verify/request/", PhoneVerificationRequestView.as_view(), name="phone-verify-request"),
    path("phone/verify/confirm/", PhoneVerificationConfirmView.as_view(), name="phone-verify-confirm"),
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
