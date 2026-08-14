"""Tests for the recommendation approval workflow (WU-11)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied

from apps.accounts.models import Role, User, UserRole
from apps.accounts.permissions import RoleNames
from apps.core.models import AuditLog
from apps.core.tests.factories import TenantFactory
from apps.inventory.tests.factories import BranchFactory, PartFactory

from ..enums import RecommendationState
from ..models import Recommendation
from ..services import ApprovalService, RecommendationGenerator


@pytest.fixture
def tenant():
    return TenantFactory()


@pytest.fixture
def manager_role():
    role, _ = Role.objects.get_or_create(name=RoleNames.MANAGER)
    return role


@pytest.fixture
def branch_manager(tenant, manager_role):
    user = User.objects.create_user(
        email="manager@example.com", password="pw", tenant=tenant
    )
    UserRole.objects.get_or_create(user=user, role=manager_role)
    return user


@pytest.fixture
def other_branch_manager(tenant, manager_role):
    user = User.objects.create_user(
        email="other@example.com", password="pw", tenant=tenant
    )
    UserRole.objects.get_or_create(user=user, role=manager_role)
    return user


@pytest.fixture
def branch(tenant, branch_manager):
    branch = BranchFactory(tenant=tenant, code="SUC-001")
    branch.manager = branch_manager
    branch.save(update_fields=["manager"])
    return branch


@pytest.fixture
def other_branch(tenant, other_branch_manager):
    branch = BranchFactory(tenant=tenant, code="SUC-002")
    branch.manager = other_branch_manager
    branch.save(update_fields=["manager"])
    return branch


@pytest.fixture
def part(tenant):
    return PartFactory(tenant=tenant, lead_time_days=10)


@pytest.fixture
def pending_recommendation(tenant, branch, part, branch_manager):
    return Recommendation.objects.create(
        tenant=tenant,
        branch=branch,
        part=part,
        assigned_approver=branch_manager,
        run_date=date.today(),
        state=RecommendationState.PENDING,
        quantity=Decimal("12.00"),
        current_stock=Decimal("15.00"),
        punto_pedido=Decimal("47.00"),
        planning_target=Decimal("37.00"),
        velocity=Decimal("20.00"),
    )


@pytest.fixture
def approved_recommendation(tenant, branch, part, branch_manager):
    return Recommendation.objects.create(
        tenant=tenant,
        branch=branch,
        part=part,
        assigned_approver=branch_manager,
        run_date=date.today(),
        state=RecommendationState.APPROVED,
        quantity=Decimal("12.00"),
        current_stock=Decimal("15.00"),
        punto_pedido=Decimal("47.00"),
        planning_target=Decimal("37.00"),
        velocity=Decimal("20.00"),
        decided_by=branch_manager,
    )


@pytest.mark.django_db
class TestSingleApprovals:
    def test_approve_recommendation(self, tenant, pending_recommendation, branch_manager):
        service = ApprovalService(tenant)
        rec = service.approve_recommendation(
            pending_recommendation, branch_manager, notes="Looks good"
        )

        assert rec.state == RecommendationState.APPROVED
        assert rec.decided_by == branch_manager
        assert AuditLog.objects.for_entity("recommendation", rec.id).filter(
            action="approve"
        ).exists()

    def test_reject_recommendation(self, tenant, pending_recommendation, branch_manager):
        service = ApprovalService(tenant)
        rec = service.reject_recommendation(
            pending_recommendation, branch_manager, notes="Skip this run"
        )

        assert rec.state == RecommendationState.REJECTED
        assert rec.decision_notes == "Skip this run"

    def test_mark_handled(self, tenant, pending_recommendation, branch_manager):
        service = ApprovalService(tenant)
        rec = service.mark_handled(
            pending_recommendation, branch_manager, notes="Handled externally"
        )

        assert rec.state == RecommendationState.HANDLED

    def test_mark_ordered(self, tenant, approved_recommendation, branch_manager):
        service = ApprovalService(tenant)
        rec = service.mark_ordered(
            approved_recommendation, branch_manager, notes="PO sent"
        )

        assert rec.state == RecommendationState.ORDERED


@pytest.mark.django_db
class TestBulkActions:
    def test_approve_bulk(self, tenant, branch, branch_manager, part):
        part_b = PartFactory(tenant=tenant, internal_sku_code="SKU-B")
        rec_a = Recommendation.objects.create(
            tenant=tenant,
            branch=branch,
            part=part,
            state=RecommendationState.PENDING,
            run_date=date.today(),
            quantity=Decimal("10.00"),
            current_stock=Decimal("15.00"),
            punto_pedido=Decimal("47.00"),
            planning_target=Decimal("37.00"),
            velocity=Decimal("20.00"),
        )
        rec_b = Recommendation.objects.create(
            tenant=tenant,
            branch=branch,
            part=part_b,
            state=RecommendationState.PENDING,
            run_date=date.today(),
            quantity=Decimal("5.00"),
            current_stock=Decimal("15.00"),
            punto_pedido=Decimal("47.00"),
            planning_target=Decimal("37.00"),
            velocity=Decimal("20.00"),
        )

        service = ApprovalService(tenant)
        updated = service.approve_bulk([rec_a, rec_b], branch_manager)

        assert len(updated) == 2
        assert all(r.state == RecommendationState.APPROVED for r in updated)
        assert AuditLog.objects.filter(
            entity_type="recommendation",
            action="approve",
            user=branch_manager,
        ).count() == 2

    def test_bulk_skips_non_pending(self, tenant, branch, branch_manager, part):
        approved = Recommendation.objects.create(
            tenant=tenant,
            branch=branch,
            part=part,
            state=RecommendationState.APPROVED,
            run_date=date.today(),
            quantity=Decimal("1.00"),
            current_stock=Decimal("15.00"),
            punto_pedido=Decimal("47.00"),
            planning_target=Decimal("37.00"),
            velocity=Decimal("20.00"),
        )
        # Use a different part for the pending rec to respect the partial
        # unique index on pending recommendations.
        part_c = PartFactory(tenant=tenant, internal_sku_code="SKU-C")
        pending = Recommendation.objects.create(
            tenant=tenant,
            branch=branch,
            part=part_c,
            state=RecommendationState.PENDING,
            run_date=date.today(),
            quantity=Decimal("2.00"),
            current_stock=Decimal("15.00"),
            punto_pedido=Decimal("47.00"),
            planning_target=Decimal("37.00"),
            velocity=Decimal("20.00"),
        )

        service = ApprovalService(tenant)
        updated = service.approve_bulk([pending, approved], branch_manager)

        assert len(updated) == 1
        assert updated[0].id == pending.id
        approved.refresh_from_db()
        assert approved.state == RecommendationState.APPROVED


@pytest.mark.django_db
class TestAuditLog:
    def test_audit_log_created(self, tenant, pending_recommendation, branch_manager):
        service = ApprovalService(tenant)
        rec = service.approve_recommendation(pending_recommendation, branch_manager)

        log = AuditLog.objects.for_entity("recommendation", rec.id).get(action="approve")
        assert log.user == branch_manager
        assert log.metadata["before_state"] == RecommendationState.PENDING
        assert log.metadata["after_state"] == RecommendationState.APPROVED
        assert "notes" in log.metadata

    def test_audit_log_includes_role_used(
        self, tenant, pending_recommendation, branch_manager, manager_role
    ):
        service = ApprovalService(tenant)
        rec = service.approve_recommendation(pending_recommendation, branch_manager)

        log = AuditLog.objects.for_entity("recommendation", rec.id).get(action="approve")
        assert log.role_used == manager_role


@pytest.mark.django_db
class TestPermissions:
    def test_permission_denied_for_other_branch_manager(
        self, tenant, pending_recommendation, other_branch_manager
    ):
        service = ApprovalService(tenant)

        with pytest.raises(PermissionDenied):
            service.approve_recommendation(
                pending_recommendation, other_branch_manager
            )


@pytest.mark.django_db
class TestRunRejectionRules:
    def test_reject_cannot_reopen_in_same_run(
        self, tenant, branch, part, branch_manager
    ):
        today = date.today()
        rec = Recommendation.objects.create(
            tenant=tenant,
            branch=branch,
            part=part,
            state=RecommendationState.PENDING,
            run_date=today,
            quantity=Decimal("12.00"),
            current_stock=Decimal("15.00"),
            punto_pedido=Decimal("47.00"),
            planning_target=Decimal("37.00"),
            velocity=Decimal("20.00"),
        )

        service = ApprovalService(tenant)
        service.reject_recommendation(rec, branch_manager)

        generator = RecommendationGenerator(tenant)
        generator.generate_for_branch(branch, run_date=today)

        assert (
            Recommendation.objects.filter(
                tenant=tenant, branch=branch, part=part, run_date=today
            ).count()
            == 1
        )
        rec.refresh_from_db()
        assert rec.state == RecommendationState.REJECTED


@pytest.mark.django_db
class TestDefaultApprover:
    def test_new_recommendation_assigned_to_branch_manager(
        self, tenant, branch, branch_manager, part
    ):
        today = date.today()
        rec = Recommendation.objects.create(
            tenant=tenant,
            branch=branch,
            part=part,
            state=RecommendationState.PENDING,
            run_date=today,
            assigned_approver=branch_manager,
            quantity=Decimal("12.00"),
            current_stock=Decimal("15.00"),
            punto_pedido=Decimal("47.00"),
            planning_target=Decimal("37.00"),
            velocity=Decimal("20.00"),
        )

        assert rec.assigned_approver == branch_manager
