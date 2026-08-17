"""Dashboard views: branch manager, coordinator, gerente, admin views with role-based access."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from apps.branches.models import Branch
from apps.accounts.models import Role

from .services import DashboardAggregator


def _user_has_role(user, tenant, *role_names) -> bool:
    """Check if the user has any of the specified roles for this tenant."""
    user_roles = set(
        user.user_roles.filter(tenant=tenant).values_list("role__name", flat=True)
    )
    return any(r in user_roles for r in role_names)


def _user_can_view_branch(user, branch: Branch) -> bool:
    """Check if the user has access to view the branch dashboard."""
    tenant = branch.tenant
    user_roles = set(
        user.user_roles.filter(tenant=tenant).values_list("role__name", flat=True)
    )
    if Role.GERENTE in user_roles or Role.ADMINISTRATOR in user_roles:
        return True
    if Role.COORDINATOR in user_roles and branch.coordinator_id == user.id:
        return True
    if branch.manager_id == user.id:
        return True
    return False


def _get_user_tenant(user):
    """Get the user's tenant (from the first UserRole or attribute)."""
    if hasattr(user, "tenant") and user.tenant:
        return user.tenant
    first_role = user.user_roles.first()
    if first_role:
        return first_role.tenant
    return None


def _get_accessible_branches(user, tenant):
    """Get all branches the user can view (for gerente: all; for coordinator: own scope)."""
    user_roles = set(
        user.user_roles.filter(tenant=tenant).values_list("role__name", flat=True)
    )
    qs = Branch.objects.filter(tenant=tenant, is_active=True)
    if Role.GERENTE in user_roles or Role.ADMINISTRATOR in user_roles:
        return qs
    if Role.COORDINATOR in user_roles:
        return qs.filter(coordinator_id=user.id)
    if Role.MANAGER in user_roles:
        return qs.filter(manager_id=user.id)
    return qs.none()


@login_required
def branch_dashboard(request, branch_code: str | None = None):
    """Branch manager dashboard.

    URL: /dashboard/ (defaults to user's branch) or /dashboard/<branch_code>/
    """
    user = request.user
    tenant = _get_user_tenant(user)
    if tenant is None:
        return HttpResponseForbidden("No tenant found for user")

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


@login_required
def coordinator_dashboard(request):
    """Coordinator dashboard: all branches in coordinator's scope."""
    user = request.user
    tenant = _get_user_tenant(user)
    if tenant is None:
        return HttpResponseForbidden("No tenant found for user")
    if not _user_has_role(user, tenant, Role.COORDINATOR, Role.GERENTE, Role.ADMINISTRATOR):
        return HttpResponseForbidden("Coordinator role required")

    aggregator = DashboardAggregator(tenant, branch=None)  # tenant-wide
    overview = aggregator.get_overview()
    accessible_branches = list(_get_accessible_branches(user, tenant))
    overview["user"] = user
    overview["accessible_branches"] = accessible_branches
    overview["view_type"] = "coordinator"
    return render(request, "dashboard/coordinator_dashboard.html", overview)


@login_required
def gerente_dashboard(request):
    """Gerente dashboard: all branches, all recommendations, tenant-wide KPIs."""
    user = request.user
    tenant = _get_user_tenant(user)
    if tenant is None:
        return HttpResponseForbidden("No tenant found for user")
    if not _user_has_role(user, tenant, Role.GERENTE, Role.ADMINISTRATOR):
        return HttpResponseForbidden("Gerente or admin role required")

    aggregator = DashboardAggregator(tenant, branch=None)
    overview = aggregator.get_overview()
    accessible_branches = list(_get_accessible_branches(user, tenant))
    overview["user"] = user
    overview["accessible_branches"] = accessible_branches
    overview["view_type"] = "gerente"
    return render(request, "dashboard/gerente_dashboard.html", overview)


@login_required
def admin_dashboard(request):
    """Admin dashboard: full system view, all branches, all data."""
    user = request.user
    tenant = _get_user_tenant(user)
    if tenant is None:
        return HttpResponseForbidden("No tenant found for user")
    if not _user_has_role(user, tenant, Role.ADMINISTRATOR):
        return HttpResponseForbidden("Admin role required")

    aggregator = DashboardAggregator(tenant, branch=None)
    overview = aggregator.get_overview()
    accessible_branches = list(_get_accessible_branches(user, tenant))
    overview["user"] = user
    overview["accessible_branches"] = accessible_branches
    overview["view_type"] = "admin"
    return render(request, "dashboard/admin_dashboard.html", overview)
