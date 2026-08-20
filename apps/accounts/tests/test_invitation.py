from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.core.tests.factories import TenantFactory

from .. import services
from ..models import Invitation, Role, User, UserRole
from ..permissions import RoleNames
from ..tokens import TokenExpired


@pytest.fixture
def tenant():
    return TenantFactory()


@pytest.fixture
def admin_user(tenant):
    user = User.objects.create_user(
        email="admin@example.com", password="secret", tenant=tenant, is_staff=True
    )
    role, _ = Role.objects.get_or_create(name=RoleNames.ADMINISTRATOR)
    UserRole.objects.create(user=user, role=role)
    return user


@pytest.fixture
def branch_id():
    return uuid4()


@pytest.mark.django_db
class TestInvitationService:
    def test_create_invitation(self, admin_user, tenant, branch_id):
        role, _ = Role.objects.get_or_create(name=RoleNames.MANAGER)
        invitation = services.create_invitation(
            admin_user, "new@example.com", [RoleNames.MANAGER], branch_id=branch_id
        )
        assert invitation.email == "new@example.com"
        assert invitation.tenant == tenant
        assert invitation.status == Invitation.Status.PENDING
        assert list(invitation.roles.all()) == [role]
        assert invitation.branch_id == branch_id

    def test_accept_invitation_creates_user(self, admin_user, branch_id):
        invitation = services.create_invitation(
            admin_user, "new@example.com", [RoleNames.MANAGER], branch_id=branch_id
        )
        user = services.accept_invitation(str(invitation.token), "newpassword")
        assert user.email == "new@example.com"
        assert user.check_password("newpassword")
        assert user.is_verified is True
        assert user.user_roles.filter(role__name=RoleNames.MANAGER).exists()
        invitation.refresh_from_db()
        assert invitation.status == Invitation.Status.ACCEPTED

    def test_expired_invitation_cannot_be_accepted(self, admin_user):
        invitation = services.create_invitation(
            admin_user, "late@example.com", [RoleNames.MANAGER]
        )
        invitation.expires_at = timezone.now() - timedelta(days=1)
        invitation.save()
        with pytest.raises(TokenExpired):
            services.accept_invitation(str(invitation.token), "pw")

    def test_revoke_invitation(self, admin_user):
        invitation = services.create_invitation(
            admin_user, "revoke@example.com", [RoleNames.MANAGER]
        )
        services.revoke_invitation(invitation)
        assert invitation.status == Invitation.Status.REVOKED


@pytest.mark.django_db
class TestInvitationViews:
    def test_accept_invitation_view(self, admin_user, branch_id, client):
        invitation = services.create_invitation(
            admin_user, "view@example.com", [RoleNames.MANAGER], branch_id=branch_id
        )
        response = client.post(
            f"/accounts/invite/{invitation.token}/",
            {"password": "newpassword", "password_confirm": "newpassword"},
        )
        assert response.status_code == 200
        assert User.objects.filter(email="view@example.com").exists()

    def test_invalid_invitation_token(self, client):
        response = client.get("/accounts/invite/not-a-token/")
        assert response.status_code == 200
        assert b"Invitaci" in response.content
