"""Permission helpers and decorators for multi-role hierarchical access."""

from __future__ import annotations

from functools import wraps
from typing import Callable, Set
from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from apps.core.models import AuditLog

from .models import Role, User, UserRole


class RoleNames:
    ADMINISTRATOR = Role.ADMINISTRATOR
    GERENTE = Role.GERENTE
    COORDINATOR = Role.COORDINATOR
    MANAGER = Role.MANAGER


RISK_PAIRS: set[frozenset[str]] = {
    frozenset({RoleNames.ADMINISTRATOR, RoleNames.MANAGER}),
}


def has_conflict_of_interest(user: User) -> bool:
    roles = user.get_role_names()
    return any(pair <= roles for pair in RISK_PAIRS)


def get_user_roles(user: User) -> list[Role]:
    return list(Role.objects.filter(user_roles__user=user))


def get_branch_scope(user: User) -> set[UUID]:
    scope: set[UUID] = set()
    for user_role in user.user_roles.all():
        if user_role.role.name == RoleNames.MANAGER and user_role.branch_id:
            scope.add(user_role.branch_id)
        elif user_role.role.name == RoleNames.COORDINATOR:
            for branch_id in user_role.scope_json.get("branches", []):
                scope.add(UUID(branch_id))
        elif user_role.role.name in {RoleNames.ADMINISTRATOR, RoleNames.GERENTE}:
            return set()  # unlimited
    return scope


def user_can_manage_user(manager: User, target: User) -> bool:
    if not manager.is_active or not target.is_active:
        return False
    manager_roles = manager.get_role_names()
    target_roles = target.get_role_names()

    if RoleNames.ADMINISTRATOR in manager_roles:
        return True
    if RoleNames.GERENTE in manager_roles and RoleNames.ADMINISTRATOR not in target_roles:
        return True
    if RoleNames.COORDINATOR in manager_roles and target_roles <= {RoleNames.MANAGER}:
        manager_scope = get_branch_scope(manager)
        target_branches = {
            ur.branch_id for ur in target.user_roles.filter(role__name=RoleNames.MANAGER)
        }
        return bool(target_branches) and target_branches <= manager_scope
    return False


def user_can_access_branch(user: User, branch_id: UUID | None) -> bool:
    if branch_id is None:
        return True
    roles = user.get_role_names()
    if {RoleNames.ADMINISTRATOR, RoleNames.GERENTE} & roles:
        return True
    return branch_id in get_branch_scope(user)


def require_any_role(*role_names: str):
    def decorator(view: Callable):
        @wraps(view)
        def wrapper(request: HttpRequest, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied
            if not request.user.get_role_names() & set(role_names):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def log_action(
    user: User,
    action: str,
    entity_type: str,
    entity_id: UUID | None = None,
    role: Role | None = None,
    metadata: dict | None = None,
) -> AuditLog:
    return AuditLog.objects.create(
        tenant=user.tenant,
        user=user,
        role_used=role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata=metadata or {},
    )
