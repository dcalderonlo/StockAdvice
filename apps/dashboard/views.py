"""Dashboard views: branch manager dashboard with role-based access."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from apps.branches.models import Branch
from apps.accounts.models import Role

from .services import DashboardAggregator


def _user_can_view_branch(user, branch: Branch) -> bool:
    """Check if the user has access to view the branch dashboard."""
    tenant = branch.tenant
    user_roles = list(
        user.user_roles.filter(tenant=tenant).values_list("role__name", flat=True)
    )
    # gerente and administrator can view all branches
    if Role.GERENTE in user_roles or Role.ADMINISTRATOR in user_roles:
        return True
    # coordinator can view their branches
    if Role.COORDINATOR in user_roles and branch.coordinator_id == user.id:
        return True
    # branch manager can view their own branch
    if branch.manager_id == user.id:
        return True
    return False


@login_required
def branch_dashboard(request, branch_code: str | None = None):
    """Branch manager dashboard.

    URL: /dashboard/ (defaults to user's branch) or /dashboard/<branch_code>/
    """
    user = request.user
    tenant = getattr(user, "tenant", None) or user.user_roles.first().tenant
    branch = None

    if branch_code:
        try:
            branch = Branch.objects.get(tenant=tenant, code=branch_code)
        except Branch.DoesNotExist:
            return HttpResponseForbidden("Branch not found")

    if branch and not _user_can_view_branch(user, branch):
        return HttpResponseForbidden("You don't have access to this branch")

    aggregator = DashboardAggregator(tenant, branch)
    overview = aggregator.get_overview()
    overview["branch"] = branch
    overview["user"] = user
    return render(request, "dashboard/branch_dashboard.html", overview)
