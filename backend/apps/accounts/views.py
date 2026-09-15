from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.utils.cache import patch_vary_headers
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from .rate_limits import client_address, consume_limit
from .serializers import (
    AccountSerializer, AuthErrorSerializer, CsrfTokenSerializer,
    LoginResponseSerializer, LoginSerializer, RegistrationSerializer,
)


class AccountAPIView(generics.GenericAPIView):
    authentication_classes = (SessionAuthentication,)
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
        consume_limit("login_account", credentials["username"])
        user = authenticate(request=request._request, **credentials)
        if user is None:
            return Response(
                {"detail": "Unable to sign in with these credentials."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request._request, user)
        return Response({
            "user": AccountSerializer(user).data,
            "csrf_token": get_token(request._request),
        })


class LogoutView(AccountAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = AccountSerializer

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        logout(request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyAccountView(AccountAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = AccountSerializer

    @extend_schema(responses={200: AccountSerializer})
    def get(self, request):
        return Response(self.get_serializer(request.user).data)
