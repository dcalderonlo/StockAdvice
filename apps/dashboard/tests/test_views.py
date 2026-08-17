"""Tests for the dashboard views (role-based access for coordinator/gerente/admin)."""
from unittest.mock import MagicMock, patch

from apps.accounts.models import Role


def test_user_has_role_true():
    """_user_has_role returns True when user has the role."""
    from apps.dashboard.views import _user_has_role
    user = MagicMock()
    user.user_roles.filter.return_value.values_list.return_value = [Role.GERENTE]
    tenant = MagicMock()
    assert _user_has_role(user, tenant, Role.GERENTE) is True


def test_user_has_role_false():
    """_user_has_role returns False when user doesn't have any of the roles."""
    from apps.dashboard.views import _user_has_role
    user = MagicMock()
    user.user_roles.filter.return_value.values_list.return_value = [Role.MANAGER]
    tenant = MagicMock()
    assert _user_has_role(user, tenant, Role.GERENTE, Role.ADMINISTRATOR) is False


def test_user_can_view_branch_gerente():
    """Gerente can view any branch."""
    from apps.dashboard.views import _user_can_view_branch
    user = MagicMock()
    user.user_roles.filter.return_value.values_list.return_value = [Role.GERENTE]
    branch = MagicMock()
    branch.coordinator_id = 999
    branch.manager_id = 888
    assert _user_can_view_branch(user, branch) is True


def test_user_can_view_branch_admin():
    """Administrator can view any branch."""
    from apps.dashboard.views import _user_can_view_branch
    user = MagicMock()
    user.user_roles.filter.return_value.values_list.return_value = [Role.ADMINISTRATOR]
    branch = MagicMock()
    branch.coordinator_id = 999
    branch.manager_id = 888
    assert _user_can_view_branch(user, branch) is True


def test_user_can_view_branch_coordinator_own():
    """Coordinator can view branches they coordinate."""
    from apps.dashboard.views import _user_can_view_branch
    user = MagicMock()
    user.id = 999
    user.user_roles.filter.return_value.values_list.return_value = [Role.COORDINATOR]
    branch = MagicMock()
    branch.coordinator_id = 999
    branch.manager_id = 888
    assert _user_can_view_branch(user, branch) is True


def test_user_can_view_branch_coordinator_other():
    """Coordinator cannot view branches they don't coordinate."""
    from apps.dashboard.views import _user_can_view_branch
    user = MagicMock()
    user.id = 999
    user.user_roles.filter.return_value.values_list.return_value = [Role.COORDINATOR]
    branch = MagicMock()
    branch.coordinator_id = 111
    branch.manager_id = 888
    assert _user_can_view_branch(user, branch) is False


def test_get_user_tenant_with_tenant_attr():
    """Returns user.tenant if set."""
    from apps.dashboard.views import _get_user_tenant
    user = MagicMock()
    user.tenant = "tenant1"
    user.user_roles.first.return_value = None
    assert _get_user_tenant(user) == "tenant1"


def test_get_user_tenant_from_user_role():
    """Falls back to first user_role's tenant."""
    from apps.dashboard.views import _get_user_tenant
    user = MagicMock()
    user.tenant = None
    mock_tenant = "tenant2"
    user.user_roles.first.return_value = MagicMock(tenant=mock_tenant)
    assert _get_user_tenant(user) == "tenant2"


def test_get_user_tenant_none():
    """Returns None when no tenant found."""
    from apps.dashboard.views import _get_user_tenant
    user = MagicMock()
    user.tenant = None
    user.user_roles.first.return_value = None
    assert _get_user_tenant(user) is None


def test_get_accessible_branches_gerente():
    """Gerente gets all active branches."""
    from apps.dashboard.views import _get_accessible_branches
    user = MagicMock()
    user.user_roles.filter.return_value.values_list.return_value = [Role.GERENTE]
    tenant = MagicMock()
    with patch("apps.dashboard.views.Branch.objects") as mock_qs:
        mock_qs.filter.return_value = MagicMock()
        result = _get_accessible_branches(user, tenant)
        assert result == mock_qs.filter.return_value


def test_get_accessible_branches_coordinator():
    """Coordinator gets only branches where coordinator_id == user.id."""
    from apps.dashboard.views import _get_accessible_branches
    user = MagicMock()
    user.id = 42
    user.user_roles.filter.return_value.values_list.return_value = [Role.COORDINATOR]
    tenant = MagicMock()
    with patch("apps.dashboard.views.Branch.objects") as mock_qs:
        mock_qs.filter.return_value.filter.return_value = MagicMock()
        result = _get_accessible_branches(user, tenant)
        mock_qs.filter.assert_called_with(tenant=tenant, is_active=True)
        mock_qs.filter.return_value.filter.assert_called_with(coordinator_id=42)


def test_coordinator_dashboard_requires_coordinator_role():
    """coordinator_dashboard denies non-coordinator users."""
    from apps.dashboard.views import coordinator_dashboard
    user = MagicMock()
    user.user_roles.filter.return_value.values_list.return_value = [Role.MANAGER]  # not coordinator
    request = MagicMock()
    request.user = user
    response = coordinator_dashboard(request)
    assert response.status_code == 403


def test_gerente_dashboard_requires_gerente_or_admin():
    """gerente_dashboard denies coordinator-only users."""
    from apps.dashboard.views import gerente_dashboard
    user = MagicMock()
    user.user_roles.filter.return_value.values_list.return_value = [Role.COORDINATOR]
    request = MagicMock()
    request.user = user
    response = gerente_dashboard(request)
    assert response.status_code == 403


def test_admin_dashboard_requires_admin_role():
    """admin_dashboard denies gerente-only users."""
    from apps.dashboard.views import admin_dashboard
    user = MagicMock()
    user.user_roles.filter.return_value.values_list.return_value = [Role.GERENTE]
    request = MagicMock()
    request.user = user
    response = admin_dashboard(request)
    assert response.status_code == 403


def test_admin_dashboard_allows_admin():
    """admin_dashboard allows administrator."""
    from apps.dashboard.views import admin_dashboard
    user = MagicMock()
    user.user_roles.filter.return_value.values_list.return_value = [Role.ADMINISTRATOR]
    user.tenant = MagicMock()
    request = MagicMock()
    request.user = user
    with patch("apps.dashboard.views.DashboardAggregator") as mock_agg:
        mock_agg.return_value.get_overview.return_value = {"kpis": {}, "pending_recommendations": [], "stock_health": []}
        with patch("apps.dashboard.views._get_accessible_branches") as mock_branches:
            mock_branches.return_value = []
            response = admin_dashboard(request)
    # Should render (200) not 403
    assert response.status_code != 403
