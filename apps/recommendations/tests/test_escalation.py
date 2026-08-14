"""Tests for recommendation escalation and cross-coordinator approval (WU-12)."""

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

from ..enums import EscalationLevel, RecommendationState
from ..escalation import EscalationService, get_escalation_thresholds
from ..models import Recommendation
from ..permissions import can_approve, get_coordinator_scope, is_cross_coordinator
from ..services import ApprovalService


@pytest.fixture
def tenant():
    return TenantFactory()


@pytest.fixture
def manager_role():
    role, _ = Role.objects.get_or_create(name=RoleNames.MANAGER)
    return role


@pytest.fixture
def coordinator_role():
    role, _ = Role.objects.get_or_create(name=RoleNames.COORDINATOR)
    return role


@pytest.fixture
def gerente_role():
    role, _ = Role.objects.get_or_create(name=RoleNames.GERENTE)
    return role


@pytest.fixture
def branch_manager(tenant, manager_role):
    user = User.objects.create_user(
        email="manager@example.com", password="pw", tenant=tenant
    )
    UserRole.objects.get_or_create(user=user, role=manager_role)
    return user


@pytest.fixture
def coordinator(tenant, coordinator_role):
    user = User.objects.create_user(
        email="coordinator@example.com", password="pw", tenant=tenant
    )
    UserRole.objects.get_or_create(
        user=user,
        role=coordinator_role,
        defaults={"scope_json": {"branches": []}},
    )
    return user


@pytest.fixture
def gerente(tenant, gerente_role):
    user = User.objects.create_user(
        email="gerente@example.com", password="pw", tenant=tenant
    )
    UserRole.objects.get_or_create(user=user, role=gerente_role)
    return user


@pytest.fixture
def branch(tenant, branch_manager, coordinator):
    branch = BranchFactory(tenant=tenant, code="SUC-001")
    branch.manager = branch_manager
    branch.coordinator = coordinator
    branch.save(update_fields=["manager", "coordinator"])
    coordinator.user_roles.update(scope_json={"branches": [str(branch.id)]})
    return branch


@pytest.fixture
def other_branch(tenant, coordinator):
    other_manager = User.objects.create_user(
        email="other-manager@example.com", password="pw", tenant=tenant
    )
    other = BranchFactory(tenant=tenant, code="SUC-002")
    other.manager = other_manager
    other.coordinator = coordinator
    other.save(update_fields=["manager", "coordinator"])
    return other


@pytest.fixture
def cross_source_branch(tenant):
    other_coordinator = User.objects.create_user(
        email="other-coordinator@example.com", password="pw", tenant=tenant
    )
    coord_role = Role.objects.get(name=RoleNames.COORDINATOR)
    UserRole.objects.get_or_create(
        user=other_coordinator,
        role=coord_role,
        defaults={"scope_json": {"branches": []}},
    )
    source = BranchFactory(tenant=tenant, code="SUC-SOURCE")
    source.coordinator = other_coordinator
    source.save(update_fields=["coordinator"])
    other_coordinator.user_roles.update(scope_json={"branches": [str(source.id)]})
    return source


@pytest.fixture
def part(tenant):
    return PartFactory(tenant=tenant, lead_time_days=10)


@pytest.fixture
def base_recommendation(tenant, branch, part):
    return Recommendation.objects.create(
        tenant=tenant,
        branch=branch,
        part=part,
        state=RecommendationState.PENDING,
        run_date=date.today(),
        assigned_approver=branch.manager,
        quantity=Decimal("12.00"),
        current_stock=Decimal("15.00"),
        punto_pedido=Decimal("47.00"),
        planning_target=Decimal("37.00"),
        velocity=Decimal("20.00"),
    )


@pytest.mark.django_db
class TestEscalationThresholds:
    def test_default_thresholds(self, tenant):
        thresholds = get_escalation_thresholds(tenant)
        assert thresholds["value_threshold"] == Decimal("10000.00")
        assert thresholds["volume_threshold"] == Decimal("100.00")
        assert thresholds["impact_threshold"] == Decimal("1.00")

    def test_thresholds_from_tenant_config(self, tenant):
        tenant.config = {
            "escalation": {
                "value_threshold": 5000.0,
                "volume_threshold": 50,
                "impact_threshold": 2,
            }
        }
        tenant.save(update_fields=["config"])
        thresholds = get_escalation_thresholds(tenant)
        assert thresholds["value_threshold"] == Decimal("5000.00")
        assert thresholds["volume_threshold"] == Decimal("50.00")
        assert thresholds["impact_threshold"] == Decimal("2.00")


@pytest.mark.django_db
class TestEscalationService:
    def test_no_escalation_below_threshold(self, tenant, base_recommendation):
        service = EscalationService(tenant)
        rec = service.check_and_escalate(base_recommendation)
        assert rec.escalation_level == EscalationLevel.NONE
        assert rec.escalation_reason == ""

    def test_escalate_to_coordinator_above_value_threshold(
        self, tenant, base_recommendation
    ):
        base_recommendation.quantity = Decimal("10001.00")
        base_recommendation.save(update_fields=["quantity"])
        service = EscalationService(tenant)
        rec = service.check_and_escalate(base_recommendation)
        assert rec.escalation_level == EscalationLevel.COORDINATOR
        assert "Value 10001" in rec.escalation_reason

    def test_escalate_to_coordinator_above_volume_threshold(
        self, tenant, base_recommendation
    ):
        base_recommendation.quantity = Decimal("150.00")
        base_recommendation.save(update_fields=["quantity"])
        service = EscalationService(tenant)
        rec = service.check_and_escalate(base_recommendation)
        assert rec.escalation_level == EscalationLevel.COORDINATOR
        assert "Volume 150" in rec.escalation_reason

    def test_escalate_to_gerente_after_coordinator(self, tenant, base_recommendation):
        base_recommendation.quantity = Decimal("150.00")
        base_recommendation.escalation_level = EscalationLevel.COORDINATOR
        base_recommendation.save(update_fields=["quantity", "escalation_level"])
        service = EscalationService(tenant)
        rec = service.check_and_escalate(base_recommendation)
        assert rec.escalation_level == EscalationLevel.GERENTE

    def test_gerente_is_highest_level(self, tenant, base_recommendation):
        base_recommendation.quantity = Decimal("150.00")
        base_recommendation.escalation_level = EscalationLevel.GERENTE
        base_recommendation.save(update_fields=["quantity", "escalation_level"])
        service = EscalationService(tenant)
        rec = service.check_and_escalate(base_recommendation)
        assert rec.escalation_level == EscalationLevel.GERENTE

    def test_escalation_audit_log(self, tenant, base_recommendation):
        base_recommendation.quantity = Decimal("150.00")
        base_recommendation.save(update_fields=["quantity"])
        service = EscalationService(tenant)
        rec = service.check_and_escalate(base_recommendation)
        log = AuditLog.objects.for_entity("recommendation", rec.id).get(
            action="escalate_to_coordinator"
        )
        assert log.metadata["previous_level"] == EscalationLevel.NONE
        assert log.metadata["new_level"] == EscalationLevel.COORDINATOR
        assert "Volume 150" in log.metadata["reason"]

    def test_escalation_records_timestamp(self, tenant, base_recommendation):
        base_recommendation.quantity = Decimal("150.00")
        base_recommendation.save(update_fields=["quantity"])
        service = EscalationService(tenant)
        rec = service.check_and_escalate(base_recommendation)
        assert rec.escalated_at is not None


@pytest.mark.django_db
class TestCrossCoordinatorPermissions:
    def test_is_cross_coordinator_true(self, tenant, branch, cross_source_branch, part):
        rec = Recommendation.objects.create(
            tenant=tenant,
            branch=branch,
            part=part,
            source_branch=cross_source_branch,
            state=RecommendationState.PENDING,
            run_date=date.today(),
            quantity=Decimal("10.00"),
            current_stock=Decimal("15.00"),
            punto_pedido=Decimal("47.00"),
            planning_target=Decimal("37.00"),
            velocity=Decimal("20.00"),
        )
        assert is_cross_coordinator(rec) is True

    def test_is_cross_coordinator_false_same_coordinator(self, tenant, branch, part):
        source = BranchFactory(tenant=tenant, code="SUC-SOURCE-SAME")
        source.coordinator = branch.coordinator
        source.save(update_fields=["coordinator"])
        rec = Recommendation.objects.create(
            tenant=tenant,
            branch=branch,
            part=part,
            source_branch=source,
            state=RecommendationState.PENDING,
            run_date=date.today(),
            quantity=Decimal("10.00"),
            current_stock=Decimal("15.00"),
            punto_pedido=Decimal("47.00"),
            planning_target=Decimal("37.00"),
            velocity=Decimal("20.00"),
        )
        assert is_cross_coordinator(rec) is False

    def test_is_cross_coordinator_false_external_supplier(self, tenant, branch, part):
        rec = Recommendation.objects.create(
            tenant=tenant,
            branch=branch,
            part=part,
            source_branch=None,
            state=RecommendationState.PENDING,
            run_date=date.today(),
            quantity=Decimal("10.00"),
            current_stock=Decimal("15.00"),
            punto_pedido=Decimal("47.00"),
            planning_target=Decimal("37.00"),
            velocity=Decimal("20.00"),
        )
        assert is_cross_coordinator(rec) is False

    def test_cross_coordinator_requires_gerente(
        self, tenant, branch, cross_source_branch, part, coordinator, gerente
    ):
        rec = Recommendation.objects.create(
            tenant=tenant,
            branch=branch,
            part=part,
            source_branch=cross_source_branch,
            state=RecommendationState.PENDING,
            run_date=date.today(),
            quantity=Decimal("10.00"),
            current_stock=Decimal("15.00"),
            punto_pedido=Decimal("47.00"),
            planning_target=Decimal("37.00"),
            velocity=Decimal("20.00"),
        )
        assert can_approve(gerente, rec) is True
        assert can_approve(coordinator, rec) is False
        assert can_approve(branch.manager, rec) is False

    def test_single_coordinator_can_approve_own_scope(
        self, tenant, branch, part, coordinator
    ):
        rec = Recommendation.objects.create(
            tenant=tenant,
            branch=branch,
            part=part,
            source_branch=None,
            state=RecommendationState.PENDING,
            run_date=date.today(),
            quantity=Decimal("10.00"),
            current_stock=Decimal("15.00"),
            punto_pedido=Decimal("47.00"),
            planning_target=Decimal("37.00"),
            velocity=Decimal("20.00"),
        )
        assert can_approve(coordinator, rec) is True

    def test_coordinator_cannot_approve_out_of_scope(
        self, tenant, branch, part, coordinator_role
    ):
        other_coordinator = User.objects.create_user(
            email="out-of-scope@example.com", password="pw", tenant=tenant
        )
        UserRole.objects.get_or_create(
            user=other_coordinator,
            role=coordinator_role,
            defaults={"scope_json": {"branches": []}},
        )
        rec = Recommendation.objects.create(
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
        assert can_approve(other_coordinator, rec) is False


@pytest.mark.django_db
class TestApprovalServiceCrossCoordinator:
    def test_approve_cross_coordinator_transfer_by_gerente(
        self, tenant, branch, cross_source_branch, part, gerente
    ):
        rec = Recommendation.objects.create(
            tenant=tenant,
            branch=branch,
            part=part,
            source_branch=cross_source_branch,
            state=RecommendationState.PENDING,
            run_date=date.today(),
            quantity=Decimal("10.00"),
            current_stock=Decimal("15.00"),
            punto_pedido=Decimal("47.00"),
            planning_target=Decimal("37.00"),
            velocity=Decimal("20.00"),
        )
        service = ApprovalService(tenant)
        approved = service.approve_cross_coordinator_transfer(rec, gerente)
        assert approved.state == RecommendationState.APPROVED

    def test_approve_cross_coordinator_transfer_rejects_coordinator(
        self, tenant, branch, cross_source_branch, part, coordinator
    ):
        rec = Recommendation.objects.create(
            tenant=tenant,
            branch=branch,
            part=part,
            source_branch=cross_source_branch,
            state=RecommendationState.PENDING,
            run_date=date.today(),
            quantity=Decimal("10.00"),
            current_stock=Decimal("15.00"),
            punto_pedido=Decimal("47.00"),
            planning_target=Decimal("37.00"),
            velocity=Decimal("20.00"),
        )
        service = ApprovalService(tenant)
        with pytest.raises(PermissionDenied):
            service.approve_cross_coordinator_transfer(rec, coordinator)

    def test_approve_recommendation_requires_gerente_for_cross_coordinator(
        self, tenant, branch, cross_source_branch, part, coordinator
    ):
        rec = Recommendation.objects.create(
            tenant=tenant,
            branch=branch,
            part=part,
            source_branch=cross_source_branch,
            state=RecommendationState.PENDING,
            run_date=date.today(),
            quantity=Decimal("10.00"),
            current_stock=Decimal("15.00"),
            punto_pedido=Decimal("47.00"),
            planning_target=Decimal("37.00"),
            velocity=Decimal("20.00"),
        )
        service = ApprovalService(tenant)
        with pytest.raises(PermissionDenied):
            service.approve_recommendation(rec, coordinator)


@pytest.mark.django_db
class TestCoordinatorScope:
    def test_get_coordinator_scope(self, tenant, branch, coordinator):
        scope = get_coordinator_scope(coordinator, tenant)
        assert branch.id in scope
