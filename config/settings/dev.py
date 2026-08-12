"""Development settings: DEBUG on, SQLite friendly, verbose console logging."""

from __future__ import annotations

from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

DATABASES["default"]["OPTIONS"] = {"timeout": 20}  # type: ignore[index]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

LOGGING["root"]["level"] = "DEBUG"  # type: ignore[index]
