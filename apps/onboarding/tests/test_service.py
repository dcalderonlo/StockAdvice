from __future__ import annotations

from datetime import date, timedelta

import pytest

from apps.accounts.models import Role, User, UserRole
from apps.branches.models import Branch
from apps.catalog.models import Part
from apps.core.tests.factories import TenantFactory
from apps.inventory.services import InventoryIngestionService
from apps.inventory.tests.factories import BranchFactory, PartFactory

from ..models import OnboardingState
from ..services import OnboardingService


pytestmark = pytest.mark.django_db


@pytest.fixture
def tenant():
    return TenantFactory(dms_adapter_type="mock")


@pytest.fixture
def branch(tenant):
    return BranchFactory(tenant=tenant, code="SUC-001")


@pytest.fixture
def admin_user(tenant):
    user = User.objects.create_user(
        email="admin@example.com", password="password", tenant=tenant
    )
    admin_role = Role.objects.get(name=Role.ADMINISTRATOR)
    UserRole.objects.create(user=user, role=admin_role)
    return user


@pytest.fixture
def manager_user(tenant):
    user = User.objects.create_user(
        email="manager@example.com", password="password", tenant=tenant
    )
    manager_role = Role.objects.get(name=Role.MANAGER)
    UserRole.objects.create(user=user, role=manager_role)
    return user


@pytest.fixture
def mock_parts(tenant):
    return [
        PartFactory(tenant=tenant, internal_sku_code=f"SKU-{i:04d}")
        for i in range(1, 11)
    ]


@pytest.fixture
def seeded_branch(branch, mock_parts):
    """Branch with stock and sales synced from the mock DMS adapter."""
    service = InventoryIngestionService(branch.tenant)
    service.sync_stock(branch.code)
    service.sync_sales(branch.code, date.today() - timedelta(days=400))
    return branch


class TestOnboardingService:
    def test_start_onboarding_creates_state(self, tenant):
        service = OnboardingService(tenant)
        state = service.start_onboarding("mock", {"key": "value"})

        assert state.tenant == tenant
        assert state.dms_adapter_type == "mock"
        assert state.dms_config == {"key": "value"}
        assert state.status == "dms_connecting"
        assert OnboardingState.objects.filter(tenant=tenant).count() == 1

    def test_test_dms_connection_returns_true_for_mock(self, tenant):
        service = OnboardingService(tenant)
        service.start_onboarding("mock", {})
        ok = service.test_dms_connection()

        assert ok is True
        state = service.get_state()
        assert state.status == "dms_connected"
        assert state.dms_test_status == "ok"
        assert state.dms_connected_at is not None

    def test_test_dms_connection_returns_false_for_invalid_adapter(self, tenant):
        service = OnboardingService(tenant)
        service.start_onboarding("invalid_adapter", {})
        ok = service.test_dms_connection()

        assert ok is False
        state = service.get_state()
        assert state.status == "failed"
        assert "failed" in state.dms_test_status

    def test_backfill_sales_imports_sales(self, tenant, seeded_branch):
        service = OnboardingService(tenant)
        service.start_onboarding("mock", {})
        service.test_dms_connection()
        count = service.backfill_sales()

        assert count > 0
        state = service.get_state()
        assert state.status == "backfill_complete"
        assert state.sales_backfilled_until == date.today()
        assert state.sales_backfill_count == count

    def test_assign_branch_manager(self, tenant, branch, manager_user):
        service = OnboardingService(tenant)
        service.start_onboarding("mock", {})
        result = service.assign_branch_manager(branch, manager_user)

        assert result is True
        branch.refresh_from_db()
        assert branch.manager == manager_user
        state = service.get_state()
        assert state.manager_assigned is True
        assert state.status == "manager_assigning"

    def test_run_test_recommendation_creates_recommendations(
        self, tenant, seeded_branch, manager_user
    ):
        service = OnboardingService(tenant)
        service.start_onboarding("mock", {})
        service.test_dms_connection()
        service.backfill_sales()
        service.assign_branch_manager(seeded_branch, manager_user)
        count = service.run_test_recommendation()

        assert count >= 0
        state = service.get_state()
        assert state.status == "live"
        assert state.test_run_completed_at is not None
        assert state.go_live_at is not None
        assert state.test_run_recommendations_count == count

    def test_run_test_recommendation_assigns_fallback_manager(
        self, tenant, seeded_branch
    ):
        service = OnboardingService(tenant)
        service.start_onboarding("mock", {})
        service.test_dms_connection()
        service.backfill_sales()
        # No explicit manager assignment; service should pick an active user.
        User.objects.create_user(
            email="fallback@example.com", password="password", tenant=tenant
        )
        count = service.run_test_recommendation()

        state = service.get_state()
        assert state.status == "live"
        assert state.test_run_recommendations_count == count
        seeded_branch.refresh_from_db()
        assert seeded_branch.manager is not None
