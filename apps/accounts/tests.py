from __future__ import annotations

import pytest

from .models import User


@pytest.mark.django_db
def test_create_user() -> None:
    user = User.objects.create_user(email="user@example.com", password="secret")
    assert user.email == "user@example.com"
    assert user.check_password("secret")


@pytest.mark.django_db
def test_create_superuser() -> None:
    user = User.objects.create_superuser(email="admin@example.com", password="secret")
    assert user.is_staff is True
    assert user.is_superuser is True

