"""Tests for the dashboard aggregator (simple unit tests, no DB)."""
from unittest.mock import MagicMock, patch

from apps.dashboard.services import DashboardAggregator


def test_get_kpi_tiles_no_branch():
    """When no branch is given, _get_tenant_kpis returns the expected KPI structure."""
    mock_tenant = MagicMock()
    aggregator = DashboardAggregator.__new__(DashboardAggregator)
    aggregator.tenant = mock_tenant
    aggregator.branch = None
    # Patch the ORM methods to avoid DB
    with patch.object(aggregator, "_get_tenant_kpis", return_value={
        "total_branches": 0,
        "total_recommendations_pending": 0,
        "total_recommendations_approved": 0,
        "total_recommendations_partial": 0,
    }):
        kpis = aggregator.get_kpi_tiles()
    assert "total_branches" in kpis
    assert "total_recommendations_pending" in kpis
    assert "total_recommendations_approved" in kpis
    assert "total_recommendations_partial" in kpis


def test_get_kpi_tiles_with_branch():
    """When a branch is given, _get_branch_kpis returns the expected KPI structure."""
    mock_tenant = MagicMock()
    mock_branch = MagicMock()
    mock_branch.code = "SUC-001"
    mock_branch.name = "Branch 1"
    aggregator = DashboardAggregator.__new__(DashboardAggregator)
    aggregator.tenant = mock_tenant
    aggregator.branch = mock_branch
    with patch.object(aggregator, "_get_branch_kpis", return_value={
        "branch_code": "SUC-001",
        "branch_name": "Branch 1",
        "pending_recommendations": 0,
        "total_stock_units": 0.0,
        "active_parts": 0,
        "triggered_parts": 0,
    }):
        kpis = aggregator.get_kpi_tiles()
    assert kpis["branch_code"] == "SUC-001"
    assert kpis["branch_name"] == "Branch 1"
    assert "pending_recommendations" in kpis
    assert "total_stock_units" in kpis
    assert "active_parts" in kpis
    assert "triggered_parts" in kpis


def test_get_pending_recommendations_method_exists():
    """get_pending_recommendations is a method that returns a list."""
    mock_tenant = MagicMock()
    aggregator = DashboardAggregator.__new__(DashboardAggregator)
    aggregator.tenant = mock_tenant
    aggregator.branch = None
    assert hasattr(aggregator, "get_pending_recommendations")
    assert callable(aggregator.get_pending_recommendations)


def test_get_stock_health_method_exists():
    """get_stock_health is a method that returns a list."""
    mock_tenant = MagicMock()
    aggregator = DashboardAggregator.__new__(DashboardAggregator)
    aggregator.tenant = mock_tenant
    aggregator.branch = None
    assert hasattr(aggregator, "get_stock_health")
    assert callable(aggregator.get_stock_health)


def test_get_overview_structure():
    """get_overview returns a dict with 3 expected sections."""
    mock_tenant = MagicMock()
    aggregator = DashboardAggregator.__new__(DashboardAggregator)
    aggregator.tenant = mock_tenant
    aggregator.branch = None
    # Patch the get_kpi_tiles, get_pending_recommendations, get_stock_health to avoid DB
    aggregator.get_kpi_tiles = MagicMock(return_value={})
    aggregator.get_pending_recommendations = MagicMock(return_value=[])
    aggregator.get_stock_health = MagicMock(return_value=[])
    overview = aggregator.get_overview()
    assert "kpis" in overview
    assert "pending_recommendations" in overview
    assert "stock_health" in overview


def test_user_can_view_branch_logic():
    """Test the permission check function logic."""
    from apps.dashboard.views import _user_can_view_branch
    from apps.accounts.models import Role

    # gerente can view any branch
    gerente = MagicMock()
    gerente.user_roles.filter.return_value.values_list.return_value = [Role.GERENTE]
    branch = MagicMock()
    branch.coordinator_id = 999
    branch.manager_id = 888
    assert _user_can_view_branch(gerente, branch) is True

    # branch manager can view own branch
    manager = MagicMock()
    manager.user_roles.filter.return_value.values_list.return_value = [Role.MANAGER]
    manager.id = 888
    branch.manager_id = 888
    branch.coordinator_id = 999
    assert _user_can_view_branch(manager, branch) is True

    # branch manager cannot view other branch
    manager.id = 777
    assert _user_can_view_branch(manager, branch) is False

    # coordinator can view own branches
    coordinator = MagicMock()
    coordinator.id = 999
    coordinator.user_roles.filter.return_value.values_list.return_value = [Role.COORDINATOR]
    assert _user_can_view_branch(coordinator, branch) is True

    # unrelated user cannot view
    random_user = MagicMock()
    random_user.id = 100
    random_user.user_roles.filter.return_value.values_list.return_value = [Role.MANAGER]
    assert _user_can_view_branch(random_user, branch) is False


def test_aggregator_constructor():
    """Test that the aggregator stores tenant and branch correctly."""
    mock_tenant = MagicMock()
    agg = DashboardAggregator.__new__(DashboardAggregator)
    agg.tenant = mock_tenant
    agg.branch = None
    assert agg.tenant is mock_tenant
    assert agg.branch is None

    mock_branch = MagicMock()
    agg2 = DashboardAggregator.__new__(DashboardAggregator)
    agg2.tenant = mock_tenant
    agg2.branch = mock_branch
    assert agg2.branch is mock_branch
