from __future__ import annotations
from uuid import uuid4

import pytest
from django.core.exceptions import PermissionDenied

from apps.core.tests.factories import TenantFactory

from ..models import Role, User, UserRole
from ..permissions import (
    RoleNames,
    get_branch_scope,
    has_conflict_of_interest,
    require_any_role,
    user_can_access_branch,
    user_can_manage_user,
)


@pytest.fixture
def tenant():
    return TenantFactory()


@pytest.mark.django_db
class TestPermissions:
    def test_conflict_of_interest(self, tenant):
        user = User.objects.create_user(email="u@example.com", tenant=tenant)
        admin_role, _ = Role.objects.get_or_create(name=RoleNames.ADMINISTRATOR)
        manager_role, _ = Role.objects.get_or_create(name=RoleNames.MANAGER)
        UserRole.objects.create(user=user, role=admin_role)
        UserRole.objects.create(user=user, role=manager_role)
        assert has_conflict_of_interest(user) is True

    def test_no_conflict_for_single_role(self, tenant):
        user = User.objects.create_user(email="u@example.com", tenant=tenant)
        role, _ = Role.objects.get_or_create(name=RoleNames.MANAGER)
        UserRole.objects.create(user=user, role=role)
        assert has_conflict_of_interest(user) is False

    def test_branch_scope_for_manager(self, tenant):
        user = User.objects.create_user(email="m@example.com", tenant=tenant)
        branch_id = uuid4()
        role, _ = Role.objects.get_or_create(name=RoleNames.MANAGER)
        UserRole.objects.create(user=user, role=role, branch_id=branch_id)
        assert get_branch_scope(user) == {branch_id}

    def test_branch_scope_for_coordinator(self, tenant):
        user = User.objects.create_user(email="c@example.com", tenant=tenant)
        branch_ids = [uuid4(), uuid4()]
        role, _ = Role.objects.get_or_create(name=RoleNames.COORDINATOR)
        UserRole.objects.create(
            user=user, role=role, scope_json={"branches": [str(b) for b in branch_ids]}
        )
        assert get_branch_scope(user) == set(branch_ids)

    def test_admin_has_unlimited_scope(self, tenant):
        user = User.objects.create_user(email="a@example.com", tenant=tenant)
        role, _ = Role.objects.get_or_create(name=RoleNames.ADMINISTRATOR)
        UserRole.objects.create(user=user, role=role)
        assert get_branch_scope(user) == set()

    def test_user_can_access_branch(self, tenant):
        user = User.objects.create_user(email="m@example.com", tenant=tenant)
        branch_id = uuid4()
        role, _ = Role.objects.get_or_create(name=RoleNames.MANAGER)
        UserRole.objects.create(user=user, role=role, branch_id=branch_id)
        assert user_can_access_branch(user, branch_id) is True
        assert user_can_access_branch(user, uuid4()) is False

    def test_user_can_manage_user(self, tenant):
        admin = User.objects.create_user(email="admin@example.com", tenant=tenant)
        manager = User.objects.create_user(email="manager@example.com", tenant=tenant)
        admin_role, _ = Role.objects.get_or_create(name=RoleNames.ADMINISTRATOR)
        manager_role, _ = Role.objects.get_or_create(name=RoleNames.MANAGER)
        UserRole.objects.create(user=admin, role=admin_role)
        UserRole.objects.create(user=manager, role=manager_role, branch_id=uuid4())
        assert user_can_manage_user(admin, manager) is True
        assert user_can_manage_user(manager, admin) is False

    def test_require_any_role_decorator(self, tenant, rf):
        user = User.objects.create_user(email="u@example.com", tenant=tenant)
        role, _ = Role.objects.get_or_create(name=RoleNames.MANAGER)
        UserRole.objects.create(user=user, role=role)

        @require_any_role(RoleNames.MANAGER)
        def view(request):
            return "ok"

        request = rf.get("/")
        request.user = user
        assert view(request) == "ok"

        request.user = User.objects.create_user(
            email="other@example.com", tenant=tenant
        )
        with pytest.raises(PermissionDenied):
            view(request)
