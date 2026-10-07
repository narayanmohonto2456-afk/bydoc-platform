"""Production settings must fail before serving traffic when configuration is unsafe."""

import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PRODUCTION_ENV = {
    "DJANGO_SETTINGS_MODULE": "config.settings.production",
    "DJANGO_SECRET_KEY": "test-only-" + "x" * 64,
    "APP_ALLOWED_HOSTS": "api.example.com",
    "CORS_ALLOWED_ORIGINS": "https://app.example.com",
    "CSRF_TRUSTED_ORIGINS": "https://app.example.com",
    "ACCOUNT_LINK_BASE_URL": "https://app.example.com",
    "POSTGRES_DB": "test_db",
    "POSTGRES_USER": "test_user",
    "POSTGRES_PASSWORD": "test-password",
    "POSTGRES_HOST": "db.example.com",
    "POSTGRES_PORT": "5432",
    "POSTGRES_SSLROOTCERT": str(BACKEND_DIR / "certs" / "rds-global-bundle.pem"),
    "REDIS_URL": "rediss://:test-password@redis.example.com:6379/0?ssl_cert_reqs=required",
    "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
    "EMAIL_HOST": "smtp.example.com",
    "EMAIL_PORT": "587",
    "EMAIL_HOST_USER": "test-user",
    "EMAIL_HOST_PASSWORD": "test-password",
    "EMAIL_USE_TLS": "True",
    "DEFAULT_FROM_EMAIL": "SehatSaathi <no-reply@example.com>",
}


def load_production(overrides=None, code=None):
    environment = os.environ.copy()
    for name in PRODUCTION_ENV:
        environment.pop(name, None)
    environment.update(PRODUCTION_ENV)
    environment.update(overrides or {})
    return subprocess.run(
        [
            sys.executable,
            "-c",
            code
            or "import django; django.setup(); from django.conf import settings; print(settings.SECURE_SSL_REDIRECT, settings.SESSION_COOKIE_SECURE, settings.DATABASES['default']['OPTIONS']['sslmode'])",
        ],
        cwd=BACKEND_DIR,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_production_enforces_https_and_verified_database_tls():
    result = load_production()
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True True verify-full"


def test_production_never_takes_missing_secret_from_local_env_file():
    result = load_production({"DJANGO_SECRET_KEY": ""})
    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY is required" in result.stderr


def test_production_rejects_http_frontend_origin():
    result = load_production({"CORS_ALLOWED_ORIGINS": "http://app.example.com"})
    assert result.returncode != 0
    assert "HTTPS origins only" in result.stderr


def test_production_rejects_plain_redis():
    result = load_production({"REDIS_URL": "redis://:test-password@redis.example.com:6379/0"})
    assert result.returncode != 0
    assert "authenticated TLS" in result.stderr


def test_production_rejects_missing_database_ca_bundle():
    result = load_production({"POSTGRES_SSLROOTCERT": "missing-ca-bundle.pem"})
    assert result.returncode != 0
    assert "existing CA bundle" in result.stderr


def test_production_chat_rejects_localhost_model_service():
    result = load_production({
        "AI_CHAT_ENABLED": "True",
        "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
        "OLLAMA_MODEL": "llama3.2:3b",
    })
    assert result.returncode != 0
    assert "separate private service" in result.stderr


def test_production_chat_accepts_private_model_service():
    result = load_production({
        "AI_CHAT_ENABLED": "True",
        "OLLAMA_BASE_URL": "http://ollama.service.internal:11434",
        "OLLAMA_MODEL": "llama3.2:3b",
    })
    assert result.returncode == 0, result.stderr


def test_production_chat_rejects_public_model_service():
    result = load_production({
        "AI_CHAT_ENABLED": "True",
        "OLLAMA_BASE_URL": "https://model.example.com",
        "OLLAMA_MODEL": "llama3.2:3b",
    })
    assert result.returncode != 0
    assert "separate private service" in result.stderr


def test_production_rejects_file_email_backend():
    result = load_production({"EMAIL_BACKEND": "django.core.mail.backends.filebased.EmailBackend"})
    assert result.returncode != 0
    assert "SMTP backend" in result.stderr


def test_private_load_balancer_health_check_does_not_redirect_or_require_public_host():
    result = load_production(
        code=(
            "import django; django.setup(); "
            "from django.test import Client; "
            "response = Client().get('/health/live/', HTTP_HOST='10.0.1.5:8000'); "
            "print(response.status_code)"
        )
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "200"


def test_public_api_keeps_host_and_https_checks():
    result = load_production(
        code=(
            "import django; django.setup(); "
            "from django.test import Client; "
            "client = Client(); "
            "print(client.get('/api/v1/auth/csrf/', HTTP_HOST='evil.example.com').status_code, "
            "client.get('/api/v1/auth/csrf/', HTTP_HOST='api.example.com').status_code)"
        )
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "400 301"


def test_django_deployment_checks_have_no_errors():
    result = load_production(
        code=(
            "import django; django.setup(); "
            "from django.core.management import call_command; "
            "call_command('check', deploy=True, fail_level='ERROR')"
        )
    )
    assert result.returncode == 0, result.stdout + result.stderr
