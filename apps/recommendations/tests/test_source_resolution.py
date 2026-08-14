"""Tests for SourceResolutionService."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.branches.models import BranchType
from apps.core.tests.factories import TenantFactory
from apps.inventory.models import StockLevel, StockMovement, StockMovementType
from apps.inventory.tests.factories import BranchFactory, PartFactory

from ..enums import RecommendationState
from ..models import Recommendation
from ..services import RecommendationGenerator
from ..source_resolution import SourceResolutionService


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


def create_sales(tenant, branch, part, quantities: list[float], today: date | None = None):
    """Create SALE movements ordered oldest month to newest month."""
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


@pytest.mark.django_db
class TestSourceResolutionService:
    def test_single_source_branch_with_enough_excess(self, tenant, branch, part):
        # velocity=20, period=30, security=10, lead=10 -> PT=33.33, PP=43.33
        create_sales(tenant, branch, part, [20.0] * 12)
        create_stock(tenant, branch, part, 15.0, 10.0)  # stock=25, needs ~18 -> rec

        source_branch = BranchFactory(tenant=tenant, code="SUC-002")
        create_sales(tenant, source_branch, part, [20.0] * 12)
        # stock=100, PP=43.33 -> excess=56.67
        create_stock(tenant, source_branch, part, 100.0)

        generator = RecommendationGenerator(tenant)
        recs = generator.generate_for_branch(branch)
        assert len(recs) == 1
        rec = recs[0]

        assert rec.source_type == "inter_branch"
        assert rec.source_branch == source_branch
        assert rec.is_partial is False
        assert rec.partial_gap == Decimal("0")
        assert len(rec.source_breakdown) == 1
        assert rec.source_breakdown[0]["source_type"] == "inter_branch"
        assert rec.source_breakdown[0]["source_branch"] == str(source_branch.id)
        assert Decimal(rec.source_breakdown[0]["quantity"]) == rec.quantity

    def test_multiple_source_branches_greedy_allocation(self, tenant, branch, part):
        create_sales(tenant, branch, part, [20.0] * 12)
        # stock=5, transito=0 -> CP=28.33, larger than any single source excess.
        create_stock(tenant, branch, part, 5.0, 0.0)

        source_a = BranchFactory(tenant=tenant, code="SUC-002")
        source_b = BranchFactory(tenant=tenant, code="SUC-003")
        create_sales(tenant, source_a, part, [20.0] * 12)
        create_sales(tenant, source_b, part, [20.0] * 12)
        # source_a: stock=60, PP=43.33 -> excess=16.67
        create_stock(tenant, source_a, part, 60.0)
        # source_b: stock=55, PP=43.33 -> excess=11.67
        create_stock(tenant, source_b, part, 55.0)

        generator = RecommendationGenerator(tenant)
        rec = generator.generate_for_branch(branch)[0]

        assert rec.source_type == "inter_branch"
        assert len(rec.source_breakdown) == 2
        assert Decimal(rec.source_breakdown[0]["quantity"]) >= Decimal(
            rec.source_breakdown[1]["quantity"]
        )
        total = sum(Decimal(item["quantity"]) for item in rec.source_breakdown)
        assert total == rec.quantity

    def test_no_excess_uses_external_supplier(self, tenant, branch, part):
        create_sales(tenant, branch, part, [20.0] * 12)
        create_stock(tenant, branch, part, 15.0, 10.0)

        source_branch = BranchFactory(tenant=tenant, code="SUC-002")
        create_sales(tenant, source_branch, part, [20.0] * 12)
        # stock=40, PP=43.33 -> excess=0
        create_stock(tenant, source_branch, part, 40.0)

        generator = RecommendationGenerator(tenant)
        rec = generator.generate_for_branch(branch)[0]

        assert rec.source_type == "external_supplier"
        assert rec.source_branch is None
        assert rec.is_partial is False
        assert rec.partial_gap == Decimal("0")
        assert len(rec.source_breakdown) == 1
        assert rec.source_breakdown[0]["source_type"] == "external_supplier"
        assert rec.source_breakdown[0]["source_branch"] is None
        assert Decimal(rec.source_breakdown[0]["quantity"]) == rec.quantity

    def test_partial_fulfillment_mixed_sources(self, tenant, branch, part):
        create_sales(tenant, branch, part, [20.0] * 12)
        create_stock(tenant, branch, part, 15.0, 10.0)

        source_branch = BranchFactory(tenant=tenant, code="SUC-002")
        create_sales(tenant, source_branch, part, [20.0] * 12)
        # stock=50, PP=43.33 -> excess=6.67 (less than needed ~18)
        create_stock(tenant, source_branch, part, 50.0)

        generator = RecommendationGenerator(tenant)
        rec = generator.generate_for_branch(branch)[0]

        assert rec.source_type == "inter_branch"
        assert rec.source_branch == source_branch
        assert rec.is_partial is True
        assert rec.partial_gap > 0
        assert len(rec.source_breakdown) == 2

        inter_branch_qty = Decimal(rec.source_breakdown[0]["quantity"])
        external_qty = Decimal(rec.source_breakdown[1]["quantity"])
        assert rec.source_breakdown[0]["source_type"] == "inter_branch"
        assert rec.source_breakdown[1]["source_type"] == "external_supplier"
        assert inter_branch_qty + external_qty == rec.quantity
        assert external_qty == rec.partial_gap

    def test_zero_excess_everywhere_external_only(self, tenant, branch, part):
        create_sales(tenant, branch, part, [20.0] * 12)
        create_stock(tenant, branch, part, 15.0, 10.0)

        source_branch = BranchFactory(tenant=tenant, code="SUC-002")
        create_sales(tenant, source_branch, part, [20.0] * 12)
        # stock=43, PP=43.33 -> excess=0 (effectively no excess)
        create_stock(tenant, source_branch, part, 43.0)

        generator = RecommendationGenerator(tenant)
        rec = generator.generate_for_branch(branch)[0]

        assert rec.source_type == "external_supplier"
        assert rec.is_partial is False
        assert rec.source_breakdown[0]["source_type"] == "external_supplier"

    def test_tenant_isolation(self, tenant, branch, part):
        other_tenant = TenantFactory()
        other_branch = BranchFactory(tenant=other_tenant, code="OTHER-001")
        create_sales(tenant, branch, part, [20.0] * 12)
        create_stock(tenant, branch, part, 15.0, 10.0)

        # Same SKU in another tenant with plenty of excess.
        other_part = PartFactory(
            tenant=other_tenant, internal_sku_code=part.internal_sku_code, lead_time_days=10
        )
        create_sales(other_tenant, other_branch, other_part, [20.0] * 12)
        create_stock(other_tenant, other_branch, other_part, 1000.0)

        generator = RecommendationGenerator(tenant)
        rec = generator.generate_for_branch(branch)[0]

        assert rec.source_type == "external_supplier"
        assert rec.source_branch is None

    def test_parent_dc_checked_first(self, tenant, branch, part):
        dc = BranchFactory(tenant=tenant, code="DC-001", type=BranchType.CENTRO_DISTRIBUCION)
        branch.parent_branch = dc
        branch.save()

        other_branch = BranchFactory(tenant=tenant, code="SUC-002")

        create_sales(tenant, branch, part, [20.0] * 12)
        create_stock(tenant, branch, part, 15.0, 10.0)

        create_sales(tenant, dc, part, [20.0] * 12)
        # DC has small excess but should still be chosen first.
        create_stock(tenant, dc, part, 50.0)  # excess ~6.67

        create_sales(tenant, other_branch, part, [20.0] * 12)
        create_stock(tenant, other_branch, part, 100.0)  # excess ~56.67

        generator = RecommendationGenerator(tenant)
        rec = generator.generate_for_branch(branch)[0]

        assert rec.source_type == "inter_branch"
        # Parent DC is first in the breakdown even though its excess is smaller.
        assert rec.source_breakdown[0]["source_branch"] == str(dc.id)

    def test_resolve_sources_directly(self, tenant, branch, part):
        create_sales(tenant, branch, part, [20.0] * 12)
        create_stock(tenant, branch, part, 15.0, 10.0)

        source_branch = BranchFactory(tenant=tenant, code="SUC-002")
        create_sales(tenant, source_branch, part, [20.0] * 12)
        create_stock(tenant, source_branch, part, 100.0)

        rec = Recommendation.objects.create(
            tenant=tenant,
            branch=branch,
            part=part,
            state=RecommendationState.PENDING,
            quantity=Decimal("10.00"),
            current_stock=Decimal("25.00"),
            punto_pedido=Decimal("43.33"),
            planning_target=Decimal("33.33"),
            velocity=Decimal("20.00"),
        )

        service = SourceResolutionService(tenant)
        resolved = service.resolve_sources(rec)

        assert resolved.source_type == "inter_branch"
        assert resolved.source_branch == source_branch
        assert resolved.is_partial is False

    def test_compute_excess_returns_zero_when_no_stock_level(self, tenant, branch, part):
        source_branch = BranchFactory(tenant=tenant, code="SUC-002")
        service = SourceResolutionService(tenant)
        assert service._compute_excess_for_branch(part, source_branch) == Decimal("0")

    def test_greedy_stops_when_need_met_exactly(self, tenant, branch, part):
        source_a = BranchFactory(tenant=tenant, code="SUC-002")
        source_b = BranchFactory(tenant=tenant, code="SUC-003")

        candidates = [
            (source_a, Decimal("10.00")),
            (source_b, Decimal("5.00")),
        ]
        allocations = SourceResolutionService._greedy_allocate(Decimal("10.00"), candidates)

        assert len(allocations) == 1
        assert allocations[0] == (source_a, Decimal("10.00"))

