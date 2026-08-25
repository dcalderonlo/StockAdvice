from __future__ import annotations

from uuid import uuid4

import pytest

from apps.core.tests.factories import TenantFactory

from .. import services
from ..models import Role, User, UserRole
from ..permissions import RoleNames


@pytest.mark.django_db
def test_invitation_to_login_flow(client):
    tenant = TenantFactory()
    admin = User.objects.create_user(
        email="admin@example.com", password="secret", tenant=tenant
    )
    admin_role, _ = Role.objects.get_or_create(name=RoleNames.ADMINISTRATOR)
    UserRole.objects.create(user=admin, role=admin_role)

    branch_id = uuid4()
    invitation = services.create_invitation(
        admin, "new@example.com", [RoleNames.MANAGER], branch_id=branch_id
    )

    response = client.post(
        f"/accounts/invite/{invitation.token}/",
        {"password": "newpassword", "password_confirm": "newpassword"},
    )
    assert response.status_code == 200

    user = User.objects.get(email="new@example.com")
    assert user.is_verified is True
    assert user.user_roles.filter(role__name=RoleNames.MANAGER, branch_id=branch_id).exists()

    login = client.post(
        "/accounts/login/", {"username": "new@example.com", "password": "newpassword"}
    )
    assert login.status_code == 302
