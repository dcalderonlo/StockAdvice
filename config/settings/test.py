"""Test settings: fast in-memory SQLite, quick password hashing."""

from __future__ import annotations

from .base import *  # noqa: F403

DEBUG = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

LOGGING["root"]["level"] = "CRITICAL"  # type: ignore[index]  # noqa: F405
