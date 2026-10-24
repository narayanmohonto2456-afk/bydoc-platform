from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token, rotate_token
from django.conf import settings
from django.utils.cache import patch_vary_headers
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.exceptions import AuthenticationFailed

from .rate_limits import client_address, consume_limit
from .serializers import (
    AccountSerializer, AuthErrorSerializer, CsrfTokenSerializer,
    LoginResponseSerializer, LoginSerializer, RegistrationSerializer,
    GoogleCredentialSerializer, GoogleStatusSerializer,
    OtpLoginSerializer, OtpConfirmSerializer, OtpAvailabilitySerializer, PhoneCodeSerializer, PhoneStatusSerializer, PhoneVerificationRequestSerializer,
    VerifyRequestSerializer, ResetRequestSerializer, TokenSerializer, ResetConfirmSerializer,
        PatientProfileSerializer,
)
from .models import AccountRecoveryRequest, GoogleIdentity, VerifiedEmail, VerifiedPhone, PatientProfile, OtpChallenge
from .recovery import consume_link, request_link
from .google_auth import google_sign_in, link_google_identity, verify_google_credential
from .jwt_auth import JWTAuthentication, LegacySessionAuthentication, clear_auth_cookies, new_credentials, rotate_credentials, set_auth_cookies
from .otp import SmsUnavailable, confirm_phone, consume_challenge, create_challenge, sms_ready
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone


class AccountAPIView(generics.GenericAPIView):
    authentication_classes = (JWTAuthentication, LegacySessionAuthentication)
    parser_classes = (JSONParser,)

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            # Explicitly protect anonymous login/registration requests too.
            SessionAuthentication().enforce_csrf(request)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        patch_vary_headers(response, ("Cookie",))
        return response


class CsrfTokenView(AccountAPIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    serializer_class = CsrfTokenSerializer

    @extend_schema(responses={200: CsrfTokenSerializer})
    def get(self, request):
        return Response({"csrf_token": get_token(request._request)})


class RegistrationView(AccountAPIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegistrationSerializer

    @extend_schema(responses={201: AccountSerializer, 429: AuthErrorSerializer, 503: AuthErrorSerializer})
    def post(self, request):
        consume_limit("register_ip", client_address(request))
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(AccountSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(AccountAPIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    serializer_class = LoginSerializer

    @extend_schema(responses={200: LoginResponseSerializer, 400: AuthErrorSerializer, 429: AuthErrorSerializer, 503: AuthErrorSerializer})
    def post(self, request):
        consume_limit("login_ip", client_address(request))
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        credentials = serializer.validated_data
        identifier = credentials["username"]
        consume_limit("login_account", identifier.casefold())
        verified = None
        if "@" in identifier:
            verified = VerifiedEmail.objects.select_related("user").filter(
                address__iexact=identifier, user__is_active=True,
            ).first()
        username = verified.user.username if verified else identifier
        user = authenticate(
            request=request._request, username=username,
            password=credentials["password"],
        )
        if user is None:
            return Response(
                {"detail": "Unable to sign in with these credentials."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if settings.API_LEGACY_SESSION_AUTH:
            login(request._request, user)
        else:
            rotate_token(request._request)
        access, refresh, _ = new_credentials(user)
        response = Response({
            "user": AccountSerializer(user).data,
            "csrf_token": get_token(request._request),
        })
        set_auth_cookies(response, access, refresh)
        return response


class GoogleSignInView(AccountAPIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    serializer_class = GoogleCredentialSerializer

    @extend_schema(responses={200: LoginResponseSerializer, 400: AuthErrorSerializer, 409: AuthErrorSerializer})
    def post(self, request):
        consume_limit("login_ip", client_address(request))
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        claims = verify_google_credential(serializer.validated_data["credential"])
        consume_limit("login_account", f"google:{claims.subject}")
        user = google_sign_in(claims)
        if settings.API_LEGACY_SESSION_AUTH:
            login(request._request, user, backend="django.contrib.auth.backends.ModelBackend")
        else:
            rotate_token(request._request)
        access, refresh, _ = new_credentials(user)
        response = Response({
            "user": AccountSerializer(user).data,
            "csrf_token": get_token(request._request),
        })
        set_auth_cookies(response, access, refresh)
        return response


class TokenRefreshView(AccountAPIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    serializer_class = LoginResponseSerializer

    @extend_schema(request=None, responses={200: LoginResponseSerializer})
    def post(self, request):
        raw = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME)
        if not raw:
            return Response({"detail": "Refresh credential is missing."}, status=401)
        try:
            access, refresh, session = rotate_credentials(raw)
        except AuthenticationFailed:
            return Response({"detail": "Refresh credential is invalid."}, status=401)
        response = Response({
            "user": AccountSerializer(session.user).data,
            "csrf_token": get_token(request._request),
        })
        set_auth_cookies(response, access, refresh)
        return response


def otp_user(channel, identifier):
    if channel == OtpChallenge.Channel.EMAIL:
        contact = VerifiedEmail.objects.select_related("user").filter(
            address__iexact=identifier, user__is_active=True,
        ).first()
    else:
        contact = VerifiedPhone.objects.select_related("user").filter(
            number=identifier, user__phone_number=identifier, user__is_active=True,
        ).first()
    return contact.user if contact else None


class OtpLoginRequestView(AccountAPIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    serializer_class = OtpLoginSerializer

    @extend_schema(responses={202: AuthErrorSerializer})
    def post(self, request):
        consume_limit("otp_request_ip", client_address(request))
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        channel = serializer.validated_data["channel"]
        identifier = serializer.validated_data["identifier"]
        consume_limit("otp_destination", f"{channel}:{identifier}")
        if channel == OtpChallenge.Channel.SMS and not sms_ready():
            raise SmsUnavailable()
        user = otp_user(channel, identifier)
        if user:
            create_challenge(user, OtpChallenge.Purpose.LOGIN, channel, identifier)
        return Response({"detail": "If this contact is eligible, a code will be sent."}, status=202)


class OtpAvailabilityView(AccountAPIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    serializer_class = OtpAvailabilitySerializer

    @extend_schema(responses={200: OtpAvailabilitySerializer})
    def get(self, request):
        return Response({"email": True, "sms": bool(sms_ready())})


class OtpLoginConfirmView(AccountAPIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    serializer_class = OtpConfirmSerializer

    @extend_schema(responses={200: LoginResponseSerializer})
    def post(self, request):
        consume_limit("otp_confirm_ip", client_address(request))
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        channel = serializer.validated_data["channel"]
        identifier = serializer.validated_data["identifier"]
        consume_limit("otp_confirm_destination", f"{channel}:{identifier}")
        user = otp_user(channel, identifier)
        if not user:
            return Response({"code": ["The code is invalid or expired."]}, status=400)
        consume_challenge(user, OtpChallenge.Purpose.LOGIN, channel, identifier,
                          serializer.validated_data["code"])
        rotate_token(request._request)
        access, refresh, _ = new_credentials(user)
        response = Response({
            "user": AccountSerializer(user).data,
            "csrf_token": get_token(request._request),
        })
        set_auth_cookies(response, access, refresh)
        return response


class PhoneVerificationStatusView(AccountAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = PhoneStatusSerializer

    @extend_schema(responses={200: PhoneStatusSerializer})
    def get(self, request):
        return Response({
            "verified": VerifiedPhone.objects.filter(
                user=request.user, number=request.user.phone_number,
            ).exists(),
            "sms_available": bool(sms_ready()),
        })


class PhoneVerificationRequestView(AccountAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = PhoneVerificationRequestSerializer

    @extend_schema(responses={202: None})
    @transaction.atomic
    def post(self, request):
        if not sms_ready():
            raise SmsUnavailable()
        consume_limit("otp_request_ip", client_address(request))
        consume_limit("login_account", f"phone-enrollment:{request.user.pk}")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
        if not user.check_password(serializer.validated_data["current_password"]):
            return Response({"detail": "Current password is incorrect."}, status=400)
        number = user.phone_number
        if not number:
            return Response({"phone_number": ["Add a phone number to your profile first."]}, status=400)
        consume_limit("otp_destination", f"verify:{number}")
        create_challenge(user, OtpChallenge.Purpose.VERIFY_PHONE,
                         OtpChallenge.Channel.SMS, number)
        return Response(status=202)


class PhoneVerificationConfirmView(AccountAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = PhoneCodeSerializer

    @extend_schema(responses={204: None})
    def post(self, request):
        consume_limit("otp_confirm_ip", client_address(request))
        consume_limit("login_account", f"phone-enrollment:{request.user.pk}")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        confirm_phone(request.user, serializer.validated_data["code"], serializer.validated_data["current_password"])
        return Response(status=204)


class GoogleLinkView(AccountAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = GoogleCredentialSerializer

    @extend_schema(responses={204: None, 400: AuthErrorSerializer, 409: AuthErrorSerializer})
    def post(self, request):
        consume_limit("verify_ip", client_address(request))
        consume_limit("verify_user", request.user.pk)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        claims = verify_google_credential(serializer.validated_data["credential"])
        link_google_identity(request.user, claims)
        return Response(status=status.HTTP_204_NO_CONTENT)


class GoogleStatusView(AccountAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = GoogleStatusSerializer

    @extend_schema(responses={200: GoogleStatusSerializer})
    def get(self, request):
        verified = VerifiedEmail.objects.filter(user=request.user).first()
        return Response({
            "connected": GoogleIdentity.objects.filter(user=request.user).exists(),
            "verified_email": verified.address if verified else None,
            "has_password": request.user.has_usable_password(),
        })


class LogoutView(AccountAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = AccountSerializer

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        if getattr(request.auth, "pk", None):
            request.auth.revoked_at = timezone.now()
            request.auth.save(update_fields=["revoked_at"])
        if settings.API_LEGACY_SESSION_AUTH:
            logout(request._request)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_auth_cookies(response)
        return response


class MyAccountView(AccountAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = AccountSerializer

    @extend_schema(responses={200: AccountSerializer})
    def get(self, request):
        return Response(self.get_serializer(request.user).data)


class VerifyEmailRequestView(AccountAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = VerifyRequestSerializer

    @extend_schema(responses={202: None})
    def post(self, request):
        consume_limit("verify_ip", client_address(request))
        consume_limit("verify_user", request.user.pk)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        address = serializer.validated_data["address"].strip().lower()
        if not request.user.check_password(serializer.validated_data["current_password"]):
            return Response({"detail": "Current password is incorrect."}, status=400)
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if not VerifiedEmail.objects.filter(address__iexact=address).exclude(user=user).exists():
                request_link(user, AccountRecoveryRequest.Purpose.VERIFY, address)
        return Response(status=202)


class VerifyEmailConfirmView(AccountAPIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    serializer_class = TokenSerializer

    @extend_schema(responses={204: None})
    def post(self, request):
        consume_limit("confirm_ip", client_address(request))
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        consume_link(serializer.validated_data["token"], AccountRecoveryRequest.Purpose.VERIFY)
        return Response(status=204)


class ResetRequestView(AccountAPIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    serializer_class = ResetRequestSerializer

    @extend_schema(responses={202: None})
    def post(self, request):
        consume_limit("reset_ip", client_address(request))
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        address = serializer.validated_data["address"].strip().lower()
        consume_limit("reset_address", address)
        verified = VerifiedEmail.objects.select_related("user").filter(address__iexact=address, user__is_active=True).first()
        if verified:
            with transaction.atomic():
                user = get_user_model().objects.select_for_update().get(pk=verified.user_id)
                request_link(user, AccountRecoveryRequest.Purpose.RESET, verified.address)
        return Response({"detail": "If the address is eligible, an email will be sent."}, status=202)


class ResetConfirmView(AccountAPIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    serializer_class = ResetConfirmSerializer

    @extend_schema(responses={204: None})
    def post(self, request):
        consume_limit("confirm_ip", client_address(request))
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        consume_link(serializer.validated_data["token"], AccountRecoveryRequest.Purpose.RESET,
                     serializer.validated_data["password"])
        return Response(status=204)

class MyPatientProfileView(AccountAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = PatientProfileSerializer

    def get_profile(self, user):
        profile, _ = PatientProfile.objects.get_or_create(
            user=user,
        )

        return (
            PatientProfile.objects
            .select_related("user")
            .get(pk=profile.pk)
        )

    @extend_schema(responses={200: PatientProfileSerializer})
    def get(self, request):
        profile = self.get_profile(request.user)

        return Response(
            self.get_serializer(profile).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=PatientProfileSerializer,
        responses={200: PatientProfileSerializer},
    )
    def patch(self, request):
        profile = self.get_profile(request.user)

        serializer = self.get_serializer(
            profile,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        profile.refresh_from_db()

        return Response(
            self.get_serializer(profile).data,
            status=status.HTTP_200_OK,
        )
