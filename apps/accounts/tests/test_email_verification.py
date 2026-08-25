from __future__ import annotations

from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from apps.core.tests.factories import TenantFactory

from .. import services
from ..models import User
from ..tokens import TokenExpired


@pytest.fixture
def user():
    tenant = TenantFactory()
    return User.objects.create_user(
        email="user@example.com", password="secret", tenant=tenant
    )


@pytest.mark.django_db
class TestEmailVerificationService:
    def test_create_verification(self, user):
        verification = services.create_email_verification(user)
        assert verification.user == user
        assert verification.verified_at is None

    def test_verify_email(self, user):
        verification = services.create_email_verification(user)
        services.verify_email(str(verification.token))
        user.refresh_from_db()
        assert user.is_verified is True
        verification.refresh_from_db()
        assert verification.verified_at is not None

    def test_expired_verification_fails(self, user):
        verification = services.create_email_verification(user)
        verification.expires_at = timezone.now() - timedelta(hours=2)
        verification.save()
        with pytest.raises(TokenExpired):
            services.verify_email(str(verification.token))


@pytest.mark.django_db
class TestEmailVerificationView:
    def test_verify_email_view(self, user, client):
        verification = services.create_email_verification(user)
        response = client.get(f"/accounts/verify/{verification.token}/")
        assert response.status_code == 200
        assert b"verificado" in response.content.lower()

    def test_send_verification_email(self, user, rf):
        verification = services.create_email_verification(user)
        request = rf.get("/")
        services.send_verification_email(verification, request)
        assert len(mail.outbox) == 1
        assert "Verifica" in mail.outbox[0].subject
