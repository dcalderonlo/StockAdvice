from __future__ import annotations

from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from apps.core.tests.factories import TenantFactory

from .. import services
from ..models import PasswordReset, User
from ..tokens import TokenExpired


@pytest.fixture
def user():
    tenant = TenantFactory()
    return User.objects.create_user(
        email="user@example.com", password="oldpassword", tenant=tenant
    )


@pytest.mark.django_db
class TestPasswordResetService:
    def test_create_password_reset(self, user):
        reset = services.create_password_reset("user@example.com")
        assert reset is not None
        assert reset.user == user

    def test_create_password_reset_unknown_email(self):
        assert services.create_password_reset("missing@example.com") is None

    def test_reset_password(self, user):
        reset = services.create_password_reset("user@example.com")
        services.reset_password(str(reset.token), "newpassword")
        user.refresh_from_db()
        assert user.check_password("newpassword")
        reset.refresh_from_db()
        assert reset.used_at is not None

    def test_expired_token_cannot_reset(self, user):
        reset = services.create_password_reset("user@example.com")
        reset.expires_at = timezone.now() - timedelta(hours=2)
        reset.save()
        with pytest.raises(TokenExpired):
            services.reset_password(str(reset.token), "newpassword")


@pytest.mark.django_db
class TestPasswordResetViews:
    def test_request_reset_sends_email(self, user, client):
        response = client.post(
            "/accounts/password-reset/", {"email": "user@example.com"}
        )
        assert response.status_code == 302
        assert len(mail.outbox) == 1

    def test_request_reset_unknown_email_still_redirects(self, client):
        response = client.post(
            "/accounts/password-reset/", {"email": "missing@example.com"}
        )
        assert response.status_code == 302
        assert len(mail.outbox) == 0

    def test_confirm_reset_view(self, user, client):
        reset = services.create_password_reset("user@example.com")
        response = client.post(
            f"/accounts/password-reset/{reset.token}/",
            {"new_password": "newpassword", "new_password_confirm": "newpassword"},
        )
        assert response.status_code == 302
        user.refresh_from_db()
        assert user.check_password("newpassword")
