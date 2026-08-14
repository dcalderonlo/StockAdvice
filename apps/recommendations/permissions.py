"""Permission helpers for recommendation approval actions."""

from __future__ import annotations

from django.core.exceptions import PermissionDenied

from apps.accounts.models import User
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


def can_approve(user: User, recommendation: Recommendation) -> bool:
    """Check if the user can approve the recommendation.

    For WU-11: branch manager of the recommendation's branch.
    Future (WU-12): coordinator/gerente for escalated cases.
    """
    return recommendation.branch.manager_id == user.id


def assert_can_approve(user: User, recommendation: Recommendation) -> None:
    """Raise PermissionDenied if the user cannot act on the recommendation."""
    if not can_approve(user, recommendation):
        raise PermissionDenied(
            f"User {user.id} cannot approve recommendation {recommendation.id}"
        )
