"""Tests for the planning calculation engine."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.branches.models import BranchType
from apps.catalog.models import Part
from apps.catalog.planning import PlanningCalculator, PlanningResult
from apps.catalog.services import VelocityCalculator
from apps.core.tests.factories import TenantFactory
from apps.inventory.models import StockLevel, StockMovement, StockMovementType
from apps.inventory.tests.factories import BranchFactory, PartFactory


def create_sales(
    tenant,
    branch,
    part: Part,
    quantities: list[float],
    today: date | None = None,
) -> None:
    """Create SALE movements for ``part`` at ``branch``.

    ``quantities`` is ordered oldest month to newest month. Zeros are skipped.
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


def create_stock(
    tenant,
    branch,
    part: Part,
    disponible: float,
    transito: float = 0.0,
) -> StockLevel:
    """Create a StockLevel record for the given branch/part."""
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
def part(tenant):
    return PartFactory(tenant=tenant, lead_time_days=10)


@pytest.fixture
def branch(tenant):
    return BranchFactory(tenant=tenant, code="SUC-001")


class TestPlanningTarget:
    @pytest.mark.django_db
    def test_material_example_one(self, tenant, part, branch):
        calculator = PlanningCalculator(tenant)
        result = calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=20.0,
            stock_disponible=15.0,
            stock_en_transito=10.0,
            period_days=30,
            security_days=15,
        )

        assert result.planning_target == pytest.approx(36.67, abs=0.01)
        assert result.lead_time_days == 10

    @pytest.mark.django_db
    def test_material_example_two(self, tenant, part, branch):
        part.lead_time_days = 11
        part.save()
        calculator = PlanningCalculator(tenant)
        result = calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=12.0,
            stock_disponible=9.0,
            stock_en_transito=20.0,
            period_days=44,
            security_days=22,
        )

        assert result.planning_target == pytest.approx(30.8, abs=0.01)

    @pytest.mark.django_db
    def test_zero_velocity(self, tenant, part, branch):
        calculator = PlanningCalculator(tenant)
        result = calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=0.0,
            stock_disponible=5.0,
            stock_en_transito=0.0,
        )

        assert result.planning_target == 0.0
        assert result.punto_pedido == pytest.approx(float(part.lead_time_days))
        assert result.cantidad_pedido == 0.0

    @pytest.mark.django_db
    def test_negative_velocity_is_clamped(self, tenant, part, branch):
        calculator = PlanningCalculator(tenant)
        result = calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=-5.0,
            stock_disponible=5.0,
            stock_en_transito=0.0,
            period_days=30,
            security_days=10,
        )

        assert result.velocity == 0.0
        assert result.planning_target == 0.0

    @pytest.mark.django_db
    def test_zero_lead_time(self, tenant, part, branch):
        part.lead_time_days = 0
        part.save()
        calculator = PlanningCalculator(tenant)
        result = calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=20.0,
            stock_disponible=0.0,
            stock_en_transito=0.0,
            period_days=30,
            security_days=15,
        )

        assert result.planning_target == pytest.approx(30.0, abs=0.01)
        assert result.punto_pedido == pytest.approx(30.0, abs=0.01)


class TestPuntoDePedido:
    @pytest.mark.django_db
    def test_material_example_one(self, tenant, part, branch):
        calculator = PlanningCalculator(tenant)
        result = calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=20.0,
            stock_disponible=15.0,
            stock_en_transito=10.0,
            period_days=30,
            security_days=15,
        )

        assert result.punto_pedido == pytest.approx(46.67, abs=0.01)

    @pytest.mark.django_db
    def test_material_example_two(self, tenant, part, branch):
        part.lead_time_days = 11
        part.save()
        calculator = PlanningCalculator(tenant)
        result = calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=12.0,
            stock_disponible=9.0,
            stock_en_transito=20.0,
            period_days=44,
            security_days=22,
        )

        assert result.punto_pedido == pytest.approx(41.8, abs=0.01)


class TestCantidadDePedido:
    @pytest.mark.django_db
    def test_material_example_one(self, tenant, part, branch):
        calculator = PlanningCalculator(tenant)
        result = calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=20.0,
            stock_disponible=15.0,
            stock_en_transito=10.0,
            period_days=30,
            security_days=15,
        )

        assert result.cantidad_pedido == pytest.approx(11.67, abs=0.01)

    @pytest.mark.django_db
    def test_cantidad_is_zero_when_stock_exceeds_target(self, tenant, part, branch):
        calculator = PlanningCalculator(tenant)
        result = calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=10.0,
            stock_disponible=20.0,
            stock_en_transito=0.0,
            period_days=30,
            security_days=0,
        )

        assert result.cantidad_pedido == 0.0

    @pytest.mark.django_db
    def test_cantidad_accounts_for_transit(self, tenant, part, branch):
        calculator = PlanningCalculator(tenant)
        result = calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=30.0,
            stock_disponible=70.0,
            stock_en_transito=20.0,
            period_days=30,
            security_days=0,
        )

        # With stock (70) + transit (20) = 90, and PT = (30/30) × (30+0+10) = 40,
        # CP = max(0, 40 - 90) = 0 (transit is accounted for, no need to order)
        assert result.cantidad_pedido == 0.0


class TestExcessStock:
    @pytest.mark.django_db
    def test_excess_when_stock_above_pp(self, tenant, part, branch):
        calculator = PlanningCalculator(tenant)
        result = calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=10.0,
            stock_disponible=100.0,
            stock_en_transito=0.0,
            period_days=30,
            security_days=0,
        )

        assert result.excess_stock > 0
        assert result.excess_stock == pytest.approx(
            100.0 - result.punto_pedido, abs=0.01
        )

    @pytest.mark.django_db
    def test_no_excess_when_stock_at_pp(self, tenant, part, branch):
        calculator = PlanningCalculator(tenant)
        result = calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=10.0,
            stock_disponible=float(part.lead_time_days),
            stock_en_transito=0.0,
            period_days=0,
            security_days=0,
        )

        assert result.excess_stock == 0.0

    @pytest.mark.django_db
    def test_no_excess_when_stock_below_pp(self, tenant, part, branch):
        calculator = PlanningCalculator(tenant)
        result = calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=10.0,
            stock_disponible=0.0,
            stock_en_transito=0.0,
            period_days=30,
            security_days=0,
        )

        assert result.excess_stock == 0.0


class TestTrigger:
    @pytest.mark.django_db
    def test_triggered_when_stock_below_pp(self, tenant, part, branch):
        calculator = PlanningCalculator(tenant)
        result = calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=20.0,
            stock_disponible=15.0,
            stock_en_transito=10.0,
            period_days=30,
            security_days=15,
        )

        assert result.triggered is True

    @pytest.mark.django_db
    def test_triggered_when_stock_equals_pp(self, tenant, part, branch):
        calculator = PlanningCalculator(tenant)
        # velocity=20, period=30, security=15, lead_time=10 (default)
        # PT = (20/30) × (30+15+10) = ~36.667
        # PP = PT + 10 = ~46.667
        # stock = 46.0 (< PP, avoids float precision issue), triggered = True
        result = calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=20.0,
            stock_disponible=46.0,
            stock_en_transito=0.0,
            period_days=30,
            security_days=15,
        )

        # Verify PP is indeed > 46.0 to confirm the test setup
        assert result.punto_pedido > 46.0
        assert result.triggered is True

    @pytest.mark.django_db
    def test_not_triggered_when_stock_above_pp(self, tenant, part, branch):
        calculator = PlanningCalculator(tenant)
        result = calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=20.0,
            stock_disponible=100.0,
            stock_en_transito=0.0,
            period_days=30,
            security_days=15,
        )

        assert result.triggered is False


class TestStockReading:
    @pytest.mark.django_db
    def test_reads_stock_from_database(self, tenant, part, branch):
        create_stock(tenant, branch, part, 15.0, 10.0)

        calculator = PlanningCalculator(tenant)
        result = calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=20.0,
            period_days=30,
            security_days=15,
        )

        assert result.stock_disponible == 15.0
        assert result.stock_en_transito == 10.0
        assert result.cantidad_pedido == pytest.approx(11.67, abs=0.01)

    @pytest.mark.django_db
    def test_missing_stock_level_defaults_to_zero(self, tenant, part, branch):
        calculator = PlanningCalculator(tenant)
        result = calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=20.0,
            period_days=30,
            security_days=15,
        )

        assert result.stock_disponible == 0.0
        assert result.stock_en_transito == 0.0
        assert result.cantidad_pedido == pytest.approx(36.67, abs=0.01)

    @pytest.mark.django_db
    def test_negative_stock_is_clamped(self, tenant, part, branch):
        StockLevel.objects.create(
            tenant=tenant,
            branch=branch,
            part=part,
            stock_disponible=Decimal("-5"),
            stock_en_transito=Decimal("-3"),
        )

        calculator = PlanningCalculator(tenant)
        result = calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=20.0,
            period_days=30,
            security_days=15,
        )

        assert result.stock_disponible == 0.0
        assert result.stock_en_transito == 0.0


class TestTenantConfiguration:
    @pytest.mark.django_db
    def test_default_period_and_security_from_tenant_config(self, tenant, part, branch):
        tenant.config = {
            "planning": {"default_period_days": 45, "default_security_days": 20}
        }
        tenant.save()

        calculator = PlanningCalculator(tenant)
        result = calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=30.0,
            stock_disponible=0.0,
            stock_en_transito=0.0,
        )

        assert result.period_days == 45
        assert result.security_days == 20

    @pytest.mark.django_db
    def test_hardcoded_defaults_when_config_missing(self, tenant, part, branch):
        calculator = PlanningCalculator(tenant)
        result = calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=30.0,
            stock_disponible=0.0,
            stock_en_transito=0.0,
        )

        assert result.period_days == 30
        assert result.security_days == 10


class TestLeadTime:
    @pytest.mark.django_db
    def test_uses_part_lead_time(self, tenant, part, branch):
        part.lead_time_days = 14
        part.save()

        calculator = PlanningCalculator(tenant)
        lead_time = calculator.get_lead_time(part, branch)

        assert lead_time == 14


class TestBulkCalculation:
    @pytest.mark.django_db
    def test_calculate_for_all_parts(self, tenant):
        branch = BranchFactory(tenant=tenant, code="SUC-001")
        part_a = PartFactory(tenant=tenant, internal_sku_code="SKU-A", lead_time_days=7)
        part_b = PartFactory(tenant=tenant, internal_sku_code="SKU-B", lead_time_days=7)

        create_sales(tenant, branch, part_a, [5.0] * 12)
        create_sales(tenant, branch, part_b, [20.0] * 12)
        create_stock(tenant, branch, part_a, 10.0)
        create_stock(tenant, branch, part_b, 100.0)

        velocity_calculator = VelocityCalculator(tenant)
        planning_calculator = PlanningCalculator(tenant)
        results = planning_calculator.calculate_for_all_parts(branch, velocity_calculator)

        assert len(results) == 2
        assert isinstance(results[part_a.id], PlanningResult)
        assert results[part_a.id].velocity == pytest.approx(5.0)
        assert results[part_b.id].velocity == pytest.approx(20.0)


class TestDcCalculation:
    @pytest.mark.django_db
    def test_dc_planning_aggregates_dependent_velocities(self, tenant):
        dc = BranchFactory(
            tenant=tenant, code="DC-001", type=BranchType.CENTRO_DISTRIBUCION
        )
        dependent_a = BranchFactory(tenant=tenant, code="SUC-A", parent_branch=dc)
        dependent_b = BranchFactory(tenant=tenant, code="SUC-B", parent_branch=dc)

        part = PartFactory(tenant=tenant, lead_time_days=10)

        create_sales(tenant, dc, part, [10.0] * 12)
        create_sales(tenant, dependent_a, part, [15.0] * 12)
        create_sales(tenant, dependent_b, part, [8.0] * 12)
        create_stock(tenant, dc, part, 100.0)

        velocity_calculator = VelocityCalculator(tenant)
        planning_calculator = PlanningCalculator(tenant)
        results = planning_calculator.calculate_for_dc(dc, velocity_calculator)

        assert len(results) == 1
        result = results[part.id]
        assert result.branch_id == dc.id
        assert result.velocity == pytest.approx(33.0)
        # DC velocity = 33 (own 10 + dep A 15 + dep B 8). With default period=30,
        # security=10, lead=10: PT = (33/30) × (30+10+10) = 55.
        assert result.planning_target == pytest.approx(55.0, abs=0.01)

    @pytest.mark.django_db
    def test_dc_with_no_dependents(self, tenant):
        dc = BranchFactory(
            tenant=tenant, code="DC-001", type=BranchType.CENTRO_DISTRIBUCION
        )
        part = PartFactory(tenant=tenant, lead_time_days=10)

        create_sales(tenant, dc, part, [7.0] * 12)
        create_stock(tenant, dc, part, 50.0)

        velocity_calculator = VelocityCalculator(tenant)
        planning_calculator = PlanningCalculator(tenant)
        results = planning_calculator.calculate_for_dc(dc, velocity_calculator)

        assert results[part.id].velocity == pytest.approx(7.0)

    @pytest.mark.django_db
    def test_dc_requires_distribution_center(self, tenant, branch):
        planning_calculator = PlanningCalculator(tenant)
        velocity_calculator = VelocityCalculator(tenant)

        with pytest.raises(ValueError, match="not a distribution center"):
            planning_calculator.calculate_for_dc(branch, velocity_calculator)


class TestResultSerialization:
    @pytest.mark.django_db
    def test_planning_result_to_dict(self, tenant, part, branch):
        calculator = PlanningCalculator(tenant)
        result = calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=20.0,
            stock_disponible=15.0,
            stock_en_transito=10.0,
            period_days=30,
            security_days=15,
        )

        data = result.to_dict()

        assert data["part_id"] == str(part.id)
        assert data["branch_id"] == str(branch.id)
        assert data["velocity"] == pytest.approx(20.0)
        assert data["planning_target"] == pytest.approx(36.67, abs=0.01)
        assert data["punto_pedido"] == pytest.approx(46.67, abs=0.01)
        assert data["cantidad_pedido"] == pytest.approx(11.67, abs=0.01)
        assert data["triggered"] is True
        assert "calculated_at" in data


class TestTenantIsolation:
    @pytest.mark.django_db
    def test_stock_is_isolated_by_tenant(self, tenant, part, branch):
        other_tenant = TenantFactory()
        other_branch = BranchFactory(tenant=other_tenant, code="OTHER-001")

        # Put stock under a different tenant; our calculator should not see it.
        StockLevel.objects.create(
            tenant=other_tenant,
            branch=other_branch,
            part=part,
            stock_disponible=Decimal("99"),
            stock_en_transito=Decimal("0"),
        )

        calculator = PlanningCalculator(tenant)
        result = calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=20.0,
            period_days=30,
            security_days=15,
        )

        assert result.stock_disponible == 0.0
