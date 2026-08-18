"""Onboarding views: checklist and step actions."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.accounts.models import Role
from apps.branches.models import Branch
from apps.core.models import Tenant

from .services import OnboardingService


def _get_user_tenant(user):
    """Return the user's tenant from their profile or first role."""
    if hasattr(user, "tenant") and user.tenant:
        return user.tenant
    first_role = user.user_roles.first()
    if first_role:
        return first_role.tenant
    return None


@login_required
def onboarding_status(request):
    """Onboarding checklist for a tenant."""
    user = request.user
    tenant = _get_user_tenant(user)
    if tenant is None:
        return HttpResponseForbidden("No tenant found for user")

    if not _can_view_onboarding(user, tenant):
        return HttpResponseForbidden("You don't have access to onboarding")

    service = OnboardingService(tenant)
    state = service.get_state()
    checklist = [
        (
            "DMS connection",
            state.status
            in [
                "dms_connected",
                "sales_backfilling",
                "backfill_complete",
                "manager_assigning",
                "test_running",
                "live",
            ],
        ),
        ("Sales backfill (12+ months)", state.sales_backfilled_until is not None),
        ("Branch manager assignment", state.manager_assigned),
        ("Test run completed", state.test_run_completed_at is not None),
        ("Go-live", state.is_complete()),
    ]
    context = {
        "state": state,
        "checklist": checklist,
        "is_overdue": state.is_overdue(),
    }
    return render(request, "onboarding/status.html", context)


@login_required
def test_dms(request):
    """Test the DMS connection for this tenant."""
    user = request.user
    tenant = _get_user_tenant(user)
    if tenant is None:
        return HttpResponseForbidden("No tenant found for user")
    if not _can_manage_onboarding(user, tenant):
        return HttpResponseForbidden("Admin or gerente required")

    service = OnboardingService(tenant)
    ok = service.test_dms_connection()
    # Stay on status page; future work can add messages framework feedback.
    return redirect(reverse("onboarding:status"))


@login_required
def backfill(request):
    """Backfill historical sales for this tenant."""
    user = request.user
    tenant = _get_user_tenant(user)
    if tenant is None:
        return HttpResponseForbidden("No tenant found for user")
    if not _can_manage_onboarding(user, tenant):
        return HttpResponseForbidden("Admin or gerente required")

    service = OnboardingService(tenant)
    service.backfill_sales()
    return redirect(reverse("onboarding:status"))


@login_required
def test_run(request):
    """Run the first test replenishment cycle for this tenant."""
    user = request.user
    tenant = _get_user_tenant(user)
    if tenant is None:
        return HttpResponseForbidden("No tenant found for user")
    if not _can_manage_onboarding(user, tenant):
        return HttpResponseForbidden("Admin or gerente required")

    service = OnboardingService(tenant)
    service.run_test_recommendation()
    return redirect(reverse("onboarding:status"))


def _can_view_onboarding(user, tenant) -> bool:
    """Any authenticated user with a role can view onboarding."""
    return user.user_roles.exists()


def _can_manage_onboarding(user, tenant) -> bool:
    """Only admins and gerentes can drive onboarding actions."""
    role_names = set(user.user_roles.values_list("role__name", flat=True))
    return Role.ADMINISTRATOR in role_names or Role.GERENTE in role_names
