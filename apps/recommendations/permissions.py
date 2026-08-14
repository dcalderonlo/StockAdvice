"""Permission helpers for recommendation approval actions."""

from __future__ import annotations

from uuid import UUID

from django.core.exceptions import PermissionDenied

from apps.accounts.models import User
from apps.accounts.permissions import RoleNames
from apps.core.models import Tenant

from .models import Recommendation


def get_active_role(user: User, tenant: Tenant) -> str | None:
    """Return the role the user is currently using for this tenant.

    For WU-11, default to the user's first role. Multi-role role-switching
    is not yet implemented; that's a future enhancement.
    """
    if user.tenant_id and user.tenant_id != tenant.id:
        raise ValueError("User does not belong to the requested tenant.")
    user_role = user.user_roles.select_related("role").first()
    return user_role.role.name if user_role else None


def get_coordinator_scope(coordinator: User, tenant: Tenant) -> list[UUID]:
    """Return the branch IDs that belong to ``coordinator``'s scope."""
    if coordinator.tenant_id and coordinator.tenant_id != tenant.id:
        return []
    scope: list[UUID] = []
    for user_role in coordinator.user_roles.select_related("role").filter(
        role__name=RoleNames.COORDINATOR
    ):
        for branch_id in user_role.scope_json.get("branches", []):
            scope.append(UUID(branch_id))
    return scope


def is_cross_coordinator(recommendation: Recommendation) -> bool:
    """Return True when the recommendation crosses coordinator boundaries.

    A recommendation is cross-coordinator when its source branch and target
    branch belong to different coordinators. External supplier recommendations
    (no source branch) are not cross-coordinator.
    """
    source_branch = recommendation.source_branch
    if source_branch is None:
        return False
    target = recommendation.branch
    if target.coordinator_id is None or source_branch.coordinator_id is None:
        return False
    return target.coordinator_id != source_branch.coordinator_id


def can_approve(user: User, recommendation: Recommendation) -> bool:
    """Check if the user can approve the recommendation.

    Hierarchy (effective permissions are the union of all assigned roles):

    - Gerente can approve anything, including cross-coordinator transfers.
    - Cross-coordinator transfers require gerente approval.
    - Coordinator can approve recommendations within their scope.
    - Branch manager can approve recommendations for their own branch.
    """
    roles = user.get_role_names()

    if RoleNames.GERENTE in roles:
        return True

    if is_cross_coordinator(recommendation):
        return False

    if RoleNames.COORDINATOR in roles:
        scope = get_coordinator_scope(user, recommendation.tenant)
        if recommendation.branch_id in scope:
            return True

    if recommendation.branch.manager_id == user.id:
        return True

    return False


def assert_can_approve(user: User, recommendation: Recommendation) -> None:
    """Raise PermissionDenied if the user cannot act on the recommendation."""
    if not can_approve(user, recommendation):
        raise PermissionDenied(
            f"User {user.id} cannot approve recommendation {recommendation.id}"
        )
