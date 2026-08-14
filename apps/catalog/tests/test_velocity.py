"""Tests for the velocity calculation service."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.branches.models import BranchType
from apps.catalog.models import Part
from apps.catalog.services import VelocityCalculator, VelocityResult
from apps.core.tests.factories import TenantFactory
from apps.inventory.models import StockLevel, StockMovement, StockMovementType
from apps.inventory.tests.factories import BranchFactory, PartFactory


def _add_months(year: int, month: int, months: int) -> tuple[int, int]:
    """Add/subtract months from a (year, month) pair."""
    month += months
    while month <= 0:
        year -= 1
        month += 12
    while month > 12:
        year += 1
        month -= 12
    return year, month


def _month_sequence(today: date, months: int) -> list[tuple[int, int]]:
    """Return (year, month) tuples from oldest to newest."""
    sequence: list[tuple[int, int]] = []
    for offset in range(months - 1, -1, -1):
        sequence.append(_add_months(today.year, today.month, -offset))
    return sequence


def create_sales(
    tenant,
    branch,
    part: Part,
    quantities: list[float],
    today: date | None = None,
) -> None:
    """Create SALE movements for ``part`` at ``branch``.

    ``quantities`` is ordered oldest month to newest month. Missing months are
    represented by zeros and skipped when creating movements.
    """
    today = today or date.today()
    months = _month_sequence(today, len(quantities))

    for (year, month), qty in zip(months, quantities):
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


def create_stock(tenant, branch, part: Part, disponible: float) -> StockLevel:
    """Create a StockLevel record for the given branch/part."""
    return StockLevel.objects.create(
        tenant=tenant,
        branch=branch,
        part=part,
        stock_disponible=Decimal(str(disponible)),
        stock_en_transito=Decimal("0"),
    )


@pytest.fixture
def tenant():
    return TenantFactory()


@pytest.fixture
def part(tenant):
    return PartFactory(tenant=tenant)


@pytest.fixture
def branch(tenant):
    return BranchFactory(tenant=tenant, code="SUC-001")


@pytest.mark.django_db
def test_flat_history_returns_same_velocity(tenant, part, branch):
    create_sales(tenant, branch, part, [10.0] * 12)
    create_stock(tenant, branch, part, 100.0)

    calculator = VelocityCalculator(tenant)
    result = calculator.calculate_for_part(part, branch=branch)

    assert result.velocity == pytest.approx(10.0)
    assert result.annual_sales == pytest.approx(120.0)


@pytest.mark.django_db
def test_recent_months_weigh_heavier(tenant, part, branch):
    rising = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0]
    create_sales(tenant, branch, part, rising)
    create_stock(tenant, branch, part, 100.0)

    calculator = VelocityCalculator(tenant)
    result = calculator.calculate_for_part(part, branch=branch)

    assert result.velocity > sum(rising) / len(rising)
    assert result.velocity == pytest.approx(16.58, abs=0.01)


@pytest.mark.django_db
def test_empty_history_returns_zero(tenant, part, branch):
    create_stock(tenant, branch, part, 0.0)

    calculator = VelocityCalculator(tenant)
    result = calculator.calculate_for_part(part, branch=branch)

    assert result.velocity == 0.0
    assert result.annual_sales == 0.0
    assert result.projected_demand == 0.0
    assert result.is_cold_start is True


@pytest.mark.django_db
def test_shorter_history_is_accepted(tenant, part, branch):
    history = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0]
    create_sales(tenant, branch, part, history)
    create_stock(tenant, branch, part, 50.0)

    calculator = VelocityCalculator(tenant)
    result = calculator.calculate_for_part(part, branch=branch, months=6)

    assert result.velocity == pytest.approx(8.17, abs=0.01)


@pytest.mark.django_db
def test_coverage_days_calculation(tenant, part, branch):
    # 12 months of sales that sum to 5605 units.
    monthly = [5605.0 / 12] * 12
    create_sales(tenant, branch, part, monthly)
    create_stock(tenant, branch, part, 1830.0)

    calculator = VelocityCalculator(tenant)
    result = calculator.calculate_for_part(part, branch=branch)

    assert result.stock_turn_ratio == pytest.approx(3.06, abs=0.01)
    assert result.coverage_days == pytest.approx(119.2, abs=0.1)


@pytest.mark.django_db
def test_coverage_days_avoids_division_by_zero(tenant, part, branch):
    create_sales(tenant, branch, part, [10.0] * 12)
    # No StockLevel means average stock is zero.

    calculator = VelocityCalculator(tenant)
    result = calculator.calculate_for_part(part, branch=branch)

    assert result.stock_turn_ratio == 0.0
    assert result.coverage_days == 0.0


@pytest.mark.django_db
def test_projected_demand_monthly(tenant, part, branch):
    create_sales(tenant, branch, part, [20.0] * 12)
    create_stock(tenant, branch, part, 100.0)

    calculator = VelocityCalculator(tenant)
    result = calculator.calculate_for_part(part, branch=branch, period_days=30)

    assert result.projected_demand == pytest.approx(20.0)


@pytest.mark.django_db
def test_projected_demand_extended_period(tenant, part, branch):
    create_sales(tenant, branch, part, [15.0] * 12)
    create_stock(tenant, branch, part, 100.0)

    calculator = VelocityCalculator(tenant)
    result = calculator.calculate_for_part(part, branch=branch, period_days=55)

    assert result.projected_demand == pytest.approx(27.5)


@pytest.mark.django_db
def test_calculate_projected_demand_static():
    assert VelocityCalculator.calculate_projected_demand(20.0, 30) == pytest.approx(
        20.0
    )
    assert VelocityCalculator.calculate_projected_demand(15.0, 55) == pytest.approx(
        27.5
    )
    assert VelocityCalculator.calculate_projected_demand(0.0, 30) == 0.0


@pytest.mark.django_db
def test_stock_turn_ratio_avoids_division_by_zero():
    assert VelocityCalculator.calculate_stock_turn_ratio(1000.0, 0.0) == 0.0
    assert VelocityCalculator.calculate_coverage_days(1000.0, 0.0) == 0.0


@pytest.mark.django_db
def test_org_wide_velocity_aggregates_branches(tenant, part):
    branch_a = BranchFactory(tenant=tenant, code="SUC-A")
    branch_b = BranchFactory(tenant=tenant, code="SUC-B")

    create_sales(tenant, branch_a, part, [10.0] * 12)
    create_sales(tenant, branch_b, part, [10.0] * 12)
    create_stock(tenant, branch_a, part, 100.0)
    create_stock(tenant, branch_b, part, 100.0)

    calculator = VelocityCalculator(tenant)
    result = calculator.calculate_for_part(part)

    assert result.branch_id is None
    assert result.velocity == pytest.approx(20.0)
    assert result.annual_sales == pytest.approx(240.0)


@pytest.mark.django_db
def test_tenant_isolation(tenant, part):
    other_tenant = TenantFactory()
    other_branch = BranchFactory(tenant=other_tenant, code="OTHER-001")

    create_sales(tenant, other_branch, part, [99.0] * 12)
    create_stock(tenant, other_branch, part, 100.0)

    calculator = VelocityCalculator(tenant)
    result = calculator.calculate_for_part(part)

    assert result.velocity == 0.0


@pytest.mark.django_db
def test_dc_velocity_aggregation(tenant, part):
    dc = BranchFactory(
        tenant=tenant, code="DC-001", type=BranchType.CENTRO_DISTRIBUCION
    )
    dependent_a = BranchFactory(tenant=tenant, code="SUC-A", parent_branch=dc)
    dependent_b = BranchFactory(tenant=tenant, code="SUC-B", parent_branch=dc)

    create_sales(tenant, dc, part, [10.0] * 12)
    create_sales(tenant, dependent_a, part, [15.0] * 12)
    create_sales(tenant, dependent_b, part, [8.0] * 12)
    create_stock(tenant, dc, part, 100.0)
    create_stock(tenant, dependent_a, part, 100.0)
    create_stock(tenant, dependent_b, part, 100.0)

    calculator = VelocityCalculator(tenant)
    result = calculator.calculate_for_dc(dc)

    assert result.branch_id == dc.id
    assert result.part_id is None
    assert result.velocity == pytest.approx(33.0)
    assert result.annual_sales == pytest.approx((10.0 + 15.0 + 8.0) * 12)


@pytest.mark.django_db
def test_dc_with_no_dependents(tenant, part):
    dc = BranchFactory(
        tenant=tenant, code="DC-001", type=BranchType.CENTRO_DISTRIBUCION
    )
    create_sales(tenant, dc, part, [7.0] * 12)
    create_stock(tenant, dc, part, 50.0)

    calculator = VelocityCalculator(tenant)
    result = calculator.calculate_for_dc(dc)

    assert result.velocity == pytest.approx(7.0)
    assert result.annual_sales == pytest.approx(84.0)


@pytest.mark.django_db
def test_dc_requires_distribution_center(tenant, part, branch):
    calculator = VelocityCalculator(tenant)
    with pytest.raises(ValueError, match="not a distribution center"):
        calculator.calculate_for_dc(branch)


@pytest.mark.django_db
def test_calculate_for_all_parts(tenant):
    part_a = PartFactory(tenant=tenant, internal_sku_code="SKU-A")
    part_b = PartFactory(tenant=tenant, internal_sku_code="SKU-B")
    branch = BranchFactory(tenant=tenant, code="SUC-001")

    create_sales(tenant, branch, part_a, [5.0] * 12)
    create_sales(tenant, branch, part_b, [20.0] * 12)
    create_stock(tenant, branch, part_a, 100.0)
    create_stock(tenant, branch, part_b, 100.0)

    calculator = VelocityCalculator(tenant)
    results = calculator.calculate_for_all_parts(branch=branch)

    assert len(results) == 2
    assert isinstance(results[part_a.id], VelocityResult)
    assert results[part_a.id].velocity == pytest.approx(5.0)
    assert results[part_b.id].velocity == pytest.approx(20.0)


@pytest.mark.django_db
def test_velocity_result_to_dict(tenant, part, branch):
    create_sales(tenant, branch, part, [10.0] * 12)
    create_stock(tenant, branch, part, 100.0)

    calculator = VelocityCalculator(tenant)
    result = calculator.calculate_for_part(part, branch=branch)
    data = result.to_dict()

    assert data["part_id"] == str(part.id)
    assert data["branch_id"] == str(branch.id)
    assert data["velocity"] == pytest.approx(10.0)
    assert data["annual_sales"] == pytest.approx(120.0)
    assert data["is_cold_start"] is False
    assert "last_updated" in data
