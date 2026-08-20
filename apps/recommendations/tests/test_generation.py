"""Tests for the RecommendationGenerator service."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.branches.models import BranchType
from apps.accounts.models import User
from apps.core.tests.factories import TenantFactory
from apps.inventory.models import StockLevel, StockMovement, StockMovementType
from apps.inventory.tests.factories import BranchFactory, PartFactory

from ..enums import RecommendationState
from ..models import InvalidTransitionError, Recommendation
from ..services import RecommendationGenerator


def create_sales(tenant, branch, part, quantities: list[float], today: date | None = None):
    today = today or date.today()
    sequence = _month_sequence(today, len(quantities))
    for (year, month), qty in zip(sequence, quantities):
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


def _month_sequence(today: date, months: int) -> list[tuple[int, int]]:
    sequence: list[tuple[int, int]] = []
    for offset in range(months - 1, -1, -1):
        sequence.append(_add_months(today.year, today.month, -offset))
    return sequence


def create_stock(tenant, branch, part, disponible: float, transito: float = 0.0) -> StockLevel:
    return StockLevel.objects.create(
        tenant=tenant,
        branch=branch,
        part=part,
        stock_disponible=Decimal(str(disponible)),
        stock_en_transito=Decimal(str(transito)),
    )


@pytest.fixture
def tenant():
    return TenantFactory()


@pytest.fixture
def branch(tenant):
    return BranchFactory(tenant=tenant, code="SUC-001")


@pytest.fixture
def part(tenant):
    return PartFactory(tenant=tenant, lead_time_days=10)


@pytest.fixture
def user(tenant):
    return User.objects.create_user(
        email="manager@example.com", password="pw", tenant=tenant
    )


@pytest.mark.django_db
class TestGenerateForBranch:
    def test_creates_recommendation_when_stock_below_pp(self, tenant, branch, part):
        # velocity=20, period=30, security=10, lead=10 -> PT=33.33, PP=43.33
        create_sales(tenant, branch, part, [20.0] * 12)
        create_stock(tenant, branch, part, 15.0, 10.0)

        generator = RecommendationGenerator(tenant)
        recs = generator.generate_for_branch(branch)

        assert len(recs) == 1
        rec = recs[0]
        assert rec.state == RecommendationState.PENDING
        assert rec.branch == branch
        assert rec.part == part
        assert rec.quantity > 0
        assert rec.current_stock == Decimal("15.00")
        assert "PP" in rec.explanation

    def test_no_recommendation_when_stock_above_pp(self, tenant, branch, part):
        create_sales(tenant, branch, part, [20.0] * 12)
        create_stock(tenant, branch, part, 200.0)

        generator = RecommendationGenerator(tenant)
        recs = generator.generate_for_branch(branch)

        assert len(recs) == 0

    def test_skips_cold_start_part(self, tenant, branch, part):
        create_stock(tenant, branch, part, 0.0)

        generator = RecommendationGenerator(tenant)
        recs = generator.generate_for_branch(branch)

        assert len(recs) == 0

    def test_skips_obs_r_part(self, tenant, branch, part):
        # Make the part >24 months old with no sales and some stock.
        create_stock(tenant, branch, part, 5.0)
        old_date = timezone.make_aware(
            datetime(date.today().year - 3, date.today().month, date.today().day)
        )
        part.created_at = old_date
        part.save(update_fields=["created_at"])

        generator = RecommendationGenerator(tenant)
        recs = generator.generate_for_branch(branch)

        assert len(recs) == 0

    def test_skips_non_stock_part(self, tenant, branch, part):
        part.special_flags = {"is_non_stock": True}
        part.save()
        create_stock(tenant, branch, part, 0.0)

        generator = RecommendationGenerator(tenant)
        recs = generator.generate_for_branch(branch)

        assert len(recs) == 0

    def test_idempotent_generation_does_not_duplicate(self, tenant, branch, part):
        create_sales(tenant, branch, part, [20.0] * 12)
        create_stock(tenant, branch, part, 15.0)

        generator = RecommendationGenerator(tenant)
        first = generator.generate_for_branch(branch)
        second = generator.generate_for_branch(branch)

        assert len(first) == 1
        assert len(second) == 0
        assert Recommendation.objects.filter(
            tenant=tenant, branch=branch, part=part, state=RecommendationState.PENDING
        ).count() == 1

    def test_generates_for_multiple_parts(self, tenant, branch):
        part_a = PartFactory(tenant=tenant, internal_sku_code="SKU-A", lead_time_days=7)
        part_b = PartFactory(tenant=tenant, internal_sku_code="SKU-B", lead_time_days=7)

        create_sales(tenant, branch, part_a, [20.0] * 12)
        create_sales(tenant, branch, part_b, [20.0] * 12)
        create_stock(tenant, branch, part_a, 10.0)
        create_stock(tenant, branch, part_b, 200.0)

        generator = RecommendationGenerator(tenant)
        recs = generator.generate_for_branch(branch)

        assert len(recs) == 1
        assert recs[0].part == part_a


@pytest.mark.django_db
class TestGenerateForTenant:
    def test_generates_for_all_branches(self, tenant):
        branch_a = BranchFactory(tenant=tenant, code="SUC-A")
        branch_b = BranchFactory(tenant=tenant, code="SUC-B")
        part = PartFactory(tenant=tenant, lead_time_days=10)

        create_sales(tenant, branch_a, part, [20.0] * 12)
        create_sales(tenant, branch_b, part, [20.0] * 12)
        create_stock(tenant, branch_a, part, 15.0)
        create_stock(tenant, branch_b, part, 15.0)

        generator = RecommendationGenerator(tenant)
        results = generator.generate_for_tenant()

        assert len(results[branch_a.id]) == 1
        assert len(results[branch_b.id]) == 1


@pytest.mark.django_db
class TestGenerateForDc:
    def test_dc_recommendation_aggregates_dependent_velocity(self, tenant):
        dc = BranchFactory(
            tenant=tenant, code="DC-001", type=BranchType.CENTRO_DISTRIBUCION
        )
        dependent = BranchFactory(tenant=tenant, code="SUC-A", parent_branch=dc)
        part = PartFactory(tenant=tenant, lead_time_days=10)

        # DC own velocity = 5, dependent velocity = 15 -> total = 20.
        create_sales(tenant, dc, part, [5.0] * 12)
        create_sales(tenant, dependent, part, [15.0] * 12)
        create_stock(tenant, dc, part, 20.0)

        generator = RecommendationGenerator(tenant)
        recs = generator.generate_for_dc(dc)

        assert len(recs) == 1
        rec = recs[0]
        assert rec.branch == dc
        assert rec.velocity == Decimal("20.00")

    def test_dc_with_no_dependents_uses_own_velocity(self, tenant):
        dc = BranchFactory(
            tenant=tenant, code="DC-001", type=BranchType.CENTRO_DISTRIBUCION
        )
        part = PartFactory(tenant=tenant, lead_time_days=10)

        create_sales(tenant, dc, part, [20.0] * 12)
        create_stock(tenant, dc, part, 15.0)

        generator = RecommendationGenerator(tenant)
        recs = generator.generate_for_dc(dc)

        assert len(recs) == 1
        assert recs[0].velocity == Decimal("20.00")

    def test_dc_requires_distribution_center(self, tenant, branch, part):
        generator = RecommendationGenerator(tenant)

        with pytest.raises(ValueError, match="not a distribution center"):
            generator.generate_for_dc(branch)


@pytest.mark.django_db
class TestRecalculateRecommendation:
    def test_recalculate_updates_pending_recommendation(self, tenant, branch, part):
        create_sales(tenant, branch, part, [20.0] * 12)
        create_stock(tenant, branch, part, 15.0)

        generator = RecommendationGenerator(tenant)
        rec = generator.generate_for_branch(branch)[0]
        original_quantity = rec.quantity

        # Increase stock so it still triggers but quantity changes.
        StockLevel.objects.filter(tenant=tenant, branch=branch, part=part).update(
            stock_disponible=Decimal("20.00")
        )

        recalculated = generator.recalculate_recommendation(rec)
        assert recalculated is not None
        assert recalculated.quantity != original_quantity

    def test_recalculate_deletes_stale_recommendation(self, tenant, branch, part):
        create_sales(tenant, branch, part, [20.0] * 12)
        create_stock(tenant, branch, part, 15.0)

        generator = RecommendationGenerator(tenant)
        rec = generator.generate_for_branch(branch)[0]

        # Add enough stock so it no longer triggers.
        StockLevel.objects.filter(tenant=tenant, branch=branch, part=part).update(
            stock_disponible=Decimal("200.00")
        )

        result = generator.recalculate_recommendation(rec)
        assert result is None
        assert not Recommendation.objects.filter(pk=rec.pk).exists()

    def test_recalculate_only_pending(self, tenant, branch, part, user):
        rec = Recommendation.objects.create(
            tenant=tenant,
            branch=branch,
            part=part,
            state=RecommendationState.APPROVED,
            quantity=Decimal("12.00"),
            current_stock=Decimal("15.00"),
            punto_pedido=Decimal("47.00"),
            planning_target=Decimal("37.00"),
            velocity=Decimal("20.00"),
        )

        generator = RecommendationGenerator(tenant)
        with pytest.raises(InvalidTransitionError):
            generator.recalculate_recommendation(rec)
