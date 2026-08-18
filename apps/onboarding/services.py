"""Onboarding service: coordinate the steps from DMS connection to go-live."""

from __future__ import annotations

from datetime import date, timedelta

import structlog
from django.utils import timezone

from apps.branches.models import Branch
from apps.catalog.adapters.factory import get_dms_adapter_for_tenant
from apps.core.models import Tenant
from apps.inventory.services import InventoryIngestionService

from .models import OnboardingState

logger = structlog.get_logger(__name__)


class OnboardingService:
    """Orchestrates a tenant's implementation-assisted onboarding flow."""

    def __init__(self, tenant: Tenant):
        self.tenant = tenant

    def get_state(self) -> OnboardingState:
        """Return the onboarding state for this tenant, creating it if needed."""
        state, _ = OnboardingState.objects.get_or_create(
            tenant=self.tenant,
            defaults={"dms_adapter_type": self.tenant.dms_adapter_type or "mock"},
        )
        return state

    def start_onboarding(
        self, dms_adapter_type: str, dms_config: dict
    ) -> OnboardingState:
        """Initialize onboarding: set DMS adapter and transition to dms_connecting."""
        state, _ = OnboardingState.objects.get_or_create(tenant=self.tenant)
        state.dms_adapter_type = dms_adapter_type
        state.dms_config = dms_config
        state.status = "dms_connecting"
        state.save()
        logger.info(
            "onboarding.started",
            tenant=str(self.tenant.id),
            adapter_type=dms_adapter_type,
        )
        return state

    def test_dms_connection(self) -> bool:
        """Test DMS connection using the tenant's adapter."""
        state = self.get_state()
        try:
            adapter = get_dms_adapter_for_tenant(
                self.tenant, state.dms_adapter_type, state.dms_config
            )
            ok = adapter.test_connection()
            state.dms_test_status = "ok" if ok else "failed"
            if ok:
                state.status = "dms_connected"
                state.dms_connected_at = timezone.now()
            state.save()
            logger.info(
                "onboarding.dms_tested",
                tenant=str(self.tenant.id),
                ok=ok,
            )
            return ok
        except Exception as e:  # noqa: BLE001
            state.dms_test_status = f"failed: {e}"
            state.status = "failed"
            state.save()
            logger.error(
                "onboarding.dms_test_failed",
                tenant=str(self.tenant.id),
                error=str(e),
            )
            return False

    def backfill_sales(self) -> int:
        """Import 12+ months of sales history from DMS. Returns count imported."""
        state = self.get_state()
        state.status = "sales_backfilling"
        state.save()

        adapter = get_dms_adapter_for_tenant(
            self.tenant, state.dms_adapter_type, state.dms_config
        )
        since_date = date.today() - timedelta(days=400)  # 12+ months

        count = 0
        branches = Branch.objects.filter(tenant=self.tenant, is_active=True)
        for branch in branches:
            sales_data = adapter.read_sales(branch.code, since_date)
            ingestion = InventoryIngestionService(self.tenant)
            count += ingestion.import_sales({branch.code: sales_data})

        state.sales_backfilled_until = date.today()
        state.sales_backfill_count = count
        state.status = "backfill_complete"
        state.save()
        logger.info(
            "onboarding.sales_backfilled",
            tenant=str(self.tenant.id),
            count=count,
        )
        return count

    def assign_branch_manager(
        self, branch: Branch, user
    ) -> bool:
        """Assign a branch manager (required before first replenishment run)."""
        from apps.accounts.models import User

        if not isinstance(user, User):
            raise ValueError("user must be a User instance")

        state = self.get_state()
        branch.manager = user
        branch.save()
        if not state.manager_assigned:
            state.manager_assigned = True
            state.status = "manager_assigning"
            state.save()
        logger.info(
            "onboarding.manager_assigned",
            tenant=str(self.tenant.id),
            branch=branch.code,
            user=str(user.id),
        )
        return True

    def run_test_recommendation(self) -> int:
        """Run a test replenishment cycle. Returns number of recommendations generated."""
        from apps.accounts.models import User
        from apps.recommendations.services import RecommendationGenerator

        state = self.get_state()
        state.status = "test_running"
        state.save()

        generator = RecommendationGenerator(self.tenant)
        recommendations = []
        branches = Branch.objects.filter(tenant=self.tenant, is_active=True)
        for branch in branches:
            # Ensure the branch has a manager assigned so recommendations can be
            # routed to a default approver.
            if branch.manager_id is None:
                branch.manager = User.objects.filter(
                    tenant=self.tenant, is_active=True
                ).first()
                branch.save(update_fields=["manager"])
            recs = generator.generate_for_branch(branch)
            recommendations.extend(recs)

        state.test_run_recommendations_count = len(recommendations)
        state.test_run_completed_at = timezone.now()
        state.status = "live"
        state.go_live_at = timezone.now()
        state.save()
        logger.info(
            "onboarding.test_run_completed",
            tenant=str(self.tenant.id),
            recommendations=len(recommendations),
        )
        return len(recommendations)
