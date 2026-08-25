"""Production settings: DEBUG off, PostgreSQL, env-var driven."""

from __future__ import annotations

from .base import *  # noqa: F403

DEBUG = False
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])  # type: ignore[name-defined]  # noqa: F405

DATABASES["default"] = env.db()  # type: ignore[name-defined]  # noqa: F405

# Security hardening
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)  # type: ignore[name-defined]  # noqa: F405
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="localhost")  # type: ignore[name-defined]  # noqa: F405
EMAIL_PORT = env.int("EMAIL_PORT", default=587)  # type: ignore[name-defined]  # noqa: F405
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)  # type: ignore[name-defined]  # noqa: F405
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")  # type: ignore[name-defined]  # noqa: F405
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")  # type: ignore[name-defined]  # noqa: F405
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@example.com")  # type: ignore[name-defined]  # noqa: F405

LOGGING["root"]["level"] = "INFO"  # type: ignore[index]  # noqa: F405
