"""Integration tests for notification triggers wired into services."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Role, User, UserRole
from apps.branches.models import Branch, BranchType
from apps.catalog.models import Part
from apps.core.tests.factories import TenantFactory
from apps.inventory.models import StockLevel, StockMovement, StockMovementType
from apps.inventory.tests.factories import BranchFactory, PartFactory
from apps.notifications.enums import NotificationChannel, NotificationType
from apps.notifications.models import Notification
from apps.recommendations.enums import RecommendationState
from apps.recommendations.models import Recommendation
from apps.recommendations.services import ApprovalService, RecommendationGenerator


def _create_sales(tenant, branch, part, quantities: list[float], today: date | None = None):
    today = today or date.today()
    for offset, qty in enumerate(reversed(quantities)):
        year, month = _add_months(today.year, today.month, -offset)
        if qty == 0:
            continue
        StockMovement.objects.create(
            tenant=tenant,
            branch=branch,
            part=part,
            movement_type=StockMovementType.SALE,
            quantity=Decimal(str(-qty)),
            movement_date=date(year, month, 15),
        )


def _add_months(year: int, month: int, months: int) -> tuple[int, int]:
    month += months
    while month <= 0:
        year -= 1
        month += 12
    while month > 12:
        year += 1
        month -= 12
    return year, month


def _create_stock(tenant, branch, part, disponible: float) -> StockLevel:
    return StockLevel.objects.create(
        tenant=tenant,
        branch=branch,
        part=part,
        stock_disponible=Decimal(str(disponible)),
    )


@pytest.fixture
def tenant():
    return TenantFactory()


@pytest.fixture
def manager(tenant):
    return User.objects.create_user(
        email="manager@example.com", password="secret", tenant=tenant
    )


@pytest.fixture
def coordinator(tenant):
    return User.objects.create_user(
        email="coordinator@example.com", password="secret", tenant=tenant
    )


@pytest.fixture
def gerente(tenant):
    user = User.objects.create_user(
        email="gerente@example.com", password="secret", tenant=tenant
    )
    role, _ = Role.objects.get_or_create(name=Role.GERENTE)
    UserRole.objects.create(user=user, role=role)
    return user


@pytest.fixture
def branch(tenant, manager, coordinator):
    return Branch.objects.create(
        tenant=tenant,
        code="SUC-001",
        name="Branch One",
        type="sucursal",
        manager=manager,
        coordinator=coordinator,
    )


@pytest.fixture
def part(tenant):
    return PartFactory(tenant=tenant, lead_time_days=10)


@pytest.mark.django_db
def test_generation_creates_new_recommendation_notification(
    tenant, branch, part, manager, coordinator
):
    _create_sales(tenant, branch, part, [20.0] * 12)
    _create_stock(tenant, branch, part, 15.0)

    generator = RecommendationGenerator(tenant)
    recs = generator.generate_for_branch(branch)

    assert len(recs) == 1
    assert Notification.objects.filter(
        type=NotificationType.NEW_RECOMMENDATION
    ).exists()
    assert (
        Notification.objects.filter(
            user=manager, type=NotificationType.NEW_RECOMMENDATION
        ).count()
        == 2
    )
    assert (
        Notification.objects.filter(
            user=coordinator, type=NotificationType.NEW_RECOMMENDATION
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_escalation_creates_escalated_notification(tenant, branch, part, coordinator):
    rec = Recommendation.objects.create(
        tenant=tenant,
        branch=branch,
        part=part,
        state=RecommendationState.PENDING,
        quantity=Decimal("150.00"),
        current_stock=Decimal("15.00"),
        punto_pedido=Decimal("47.00"),
        planning_target=Decimal("37.00"),
        velocity=Decimal("20.00"),
    )

    from apps.recommendations.escalation import EscalationService

    service = EscalationService(tenant)
    service.check_and_escalate(rec)

    rec.refresh_from_db()
    assert rec.escalation_level == "coordinator"
    assert Notification.objects.filter(
        type=NotificationType.RECOMMENDATION_ESCALATED
    ).exists()
    assert (
        Notification.objects.filter(
            user=coordinator,
            type=NotificationType.RECOMMENDATION_ESCALATED,
            channel=NotificationChannel.EMAIL,
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_approval_creates_approved_notification(tenant, branch, part, manager):
    rec = Recommendation.objects.create(
        tenant=tenant,
        branch=branch,
        part=part,
        state=RecommendationState.PENDING,
        run_date=date.today(),
        quantity=Decimal("12.00"),
        current_stock=Decimal("15.00"),
        punto_pedido=Decimal("47.00"),
        planning_target=Decimal("37.00"),
        velocity=Decimal("20.00"),
    )

    service = ApprovalService(tenant)
    service.approve_recommendation(rec, manager)

    assert Notification.objects.filter(
        type=NotificationType.RECOMMENDATION_APPROVED
    ).exists()
    assert (
        Notification.objects.filter(
            user=manager,
            type=NotificationType.RECOMMENDATION_APPROVED,
            channel=NotificationChannel.IN_APP,
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_source_resolution_partial_creates_partial_fulfillment_notification(
    tenant, branch, part, manager, coordinator, gerente
):
    _create_sales(tenant, branch, part, [20.0] * 12)
    _create_stock(tenant, branch, part, 25.0)  # triggers recommendation

    source_branch = BranchFactory(tenant=tenant, code="SUC-002")
    _create_sales(tenant, source_branch, part, [20.0] * 12)
    # Small excess: partial fulfillment.
    _create_stock(tenant, source_branch, part, 50.0)

    generator = RecommendationGenerator(tenant)
    recs = generator.generate_for_branch(branch)

    assert len(recs) == 1
    rec = recs[0]
    assert rec.is_partial is True

    assert Notification.objects.filter(
        type=NotificationType.PARTIAL_FULFILLMENT
    ).exists()
    assert (
        Notification.objects.filter(
            user=manager,
            type=NotificationType.PARTIAL_FULFILLMENT,
            channel=NotificationChannel.EMAIL,
        ).count()
        == 1
    )
    assert (
        Notification.objects.filter(
            user=gerente,
            type=NotificationType.PARTIAL_FULFILLMENT,
            channel=NotificationChannel.EMAIL,
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_generation_with_cross_coordinator_transfer_notifies_gerente(
    tenant, part, manager, coordinator, gerente
):
    # Source branch belongs to a different coordinator.
    source_coordinator = User.objects.create_user(
        email="source-coordinator@example.com", password="secret", tenant=tenant
    )
    source_branch = BranchFactory(
        tenant=tenant,
        code="SUC-002",
        coordinator=source_coordinator,
    )

    target_branch = BranchFactory(
        tenant=tenant,
        code="SUC-001",
        manager=manager,
        coordinator=coordinator,
    )

    _create_sales(tenant, target_branch, part, [20.0] * 12)
    _create_stock(tenant, target_branch, part, 25.0)

    _create_sales(tenant, source_branch, part, [20.0] * 12)
    # Enough excess to fully cover -> inter_branch, cross-coordinator.
    _create_stock(tenant, source_branch, part, 100.0)

    generator = RecommendationGenerator(tenant)
    recs = generator.generate_for_branch(target_branch)

    assert len(recs) == 1
    rec = recs[0]
    assert rec.source_type == "inter_branch"
    assert rec.source_branch == source_branch

    assert Notification.objects.filter(
        type=NotificationType.CROSS_COORDINATOR_PENDING
    ).exists()
    assert (
        Notification.objects.filter(
            user=gerente,
            type=NotificationType.CROSS_COORDINATOR_PENDING,
            channel=NotificationChannel.EMAIL,
        ).count()
        == 1
    )
