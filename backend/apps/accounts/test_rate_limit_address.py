from django.test import RequestFactory, override_settings

from .rate_limits import client_address


def test_forwarded_client_ip_is_ignored_without_proxy_trust():
    request = RequestFactory().get("/", REMOTE_ADDR="10.0.0.5", HTTP_X_FORWARDED_FOR="198.51.100.20")
    assert client_address(request) == "10.0.0.5"


@override_settings(AUTH_TRUST_FORWARDED_CLIENT_IP=True)
def test_trusted_proxy_uses_first_valid_forwarded_address():
    request = RequestFactory().get("/", REMOTE_ADDR="10.0.0.5", HTTP_X_FORWARDED_FOR="198.51.100.20, 10.0.0.5")
    assert client_address(request) == "198.51.100.20"


@override_settings(AUTH_TRUST_FORWARDED_CLIENT_IP=True)
def test_bad_forwarded_address_falls_back_to_proxy():
    request = RequestFactory().get("/", REMOTE_ADDR="10.0.0.5", HTTP_X_FORWARDED_FOR="spoofed, 198.51.100.20")
    assert client_address(request) == "10.0.0.5"
