"""Tests for inventory models."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.inventory.models import (
    StockEnTransito,
    StockEnTransitoStatus,
    StockLevel,
    StockMovement,
    StockMovementType,
)

from .factories import BranchFactory, PartFactory, TenantFactory


@pytest.fixture
def tenant():
    return TenantFactory()


@pytest.fixture
def branch(tenant):
    return BranchFactory(tenant=tenant)


@pytest.fixture
def part(tenant):
    return PartFactory(tenant=tenant)


@pytest.mark.django_db
def test_stock_level_total_stock(branch, part):
    level = StockLevel.objects.create(
        tenant=branch.tenant,
        branch=branch,
        part=part,
        stock_disponible=Decimal("15"),
        stock_en_transito=Decimal("10"),
    )
    assert level.total_stock == Decimal("25")


@pytest.mark.django_db
def test_stock_level_unique_per_tenant_branch_part(branch, part):
    StockLevel.objects.create(
        tenant=branch.tenant,
        branch=branch,
        part=part,
        stock_disponible=Decimal("5"),
    )
    with pytest.raises(Exception):
        StockLevel.objects.create(
            tenant=branch.tenant,
            branch=branch,
            part=part,
            stock_disponible=Decimal("3"),
        )


@pytest.mark.django_db
def test_stock_level_negative_stock_disponible_raises(branch, part):
    level = StockLevel(
        tenant=branch.tenant,
        branch=branch,
        part=part,
        stock_disponible=Decimal("-1"),
    )
    with pytest.raises(ValidationError):
        level.full_clean()


@pytest.mark.django_db
def test_stock_movement_outflow_sale(branch, part):
    movement = StockMovement.objects.create(
        tenant=branch.tenant,
        branch=branch,
        part=part,
        movement_type=StockMovementType.SALE,
        quantity=Decimal("-5"),
        movement_date="2026-08-01",
    )
    assert movement.is_outflow() is True
    assert movement.is_inflow() is False


@pytest.mark.django_db
def test_stock_movement_inflow_purchase(branch, part):
    movement = StockMovement.objects.create(
        tenant=branch.tenant,
        branch=branch,
        part=part,
        movement_type=StockMovementType.PURCHASE,
        quantity=Decimal("12"),
        movement_date="2026-08-01",
    )
    assert movement.is_inflow() is True
    assert movement.is_outflow() is False


@pytest.mark.django_db
def test_stock_movement_transfer_out_is_outflow(branch, part):
    movement = StockMovement.objects.create(
        tenant=branch.tenant,
        branch=branch,
        part=part,
        movement_type=StockMovementType.TRANSFER_OUT,
        quantity=Decimal("3"),
        movement_date="2026-08-01",
    )
    assert movement.is_outflow() is True


@pytest.mark.django_db
def test_stock_movement_return_is_inflow(branch, part):
    movement = StockMovement.objects.create(
        tenant=branch.tenant,
        branch=branch,
        part=part,
        movement_type=StockMovementType.RETURN,
        quantity=Decimal("-2"),
        movement_date="2026-08-01",
    )
    assert movement.is_inflow() is True


@pytest.mark.django_db
def test_stock_en_transito_mark_received_updates_stock_level(branch, part):
    destination = BranchFactory(tenant=branch.tenant, code="DEST-001")
    level = StockLevel.objects.create(
        tenant=branch.tenant,
        branch=destination,
        part=part,
        stock_disponible=Decimal("5"),
        stock_en_transito=Decimal("10"),
    )
    transfer = StockEnTransito.objects.create(
        tenant=branch.tenant,
        source_branch=branch,
        destination_branch=destination,
        part=part,
        quantity=Decimal("10"),
        expected_arrival="2026-08-20",
    )

    transfer.mark_received()

    level.refresh_from_db()
    assert level.stock_disponible == Decimal("15")
    assert level.stock_en_transito == Decimal("0")
    assert transfer.status == StockEnTransitoStatus.RECEIVED
    assert transfer.actual_arrival is not None


@pytest.mark.django_db
def test_stock_en_transito_mark_received_partial_quantity(branch, part):
    destination = BranchFactory(tenant=branch.tenant, code="DEST-002")
    level = StockLevel.objects.create(
        tenant=branch.tenant,
        branch=destination,
        part=part,
        stock_disponible=Decimal("5"),
        stock_en_transito=Decimal("10"),
    )
    transfer = StockEnTransito.objects.create(
        tenant=branch.tenant,
        source_branch=branch,
        destination_branch=destination,
        part=part,
        quantity=Decimal("10"),
        expected_arrival="2026-08-20",
    )

    transfer.mark_received(quantity=Decimal("7"))

    level.refresh_from_db()
    assert level.stock_disponible == Decimal("12")
    assert level.stock_en_transito == Decimal("0")


@pytest.mark.django_db
def test_stock_en_transito_same_source_destination_invalid(branch, part):
    transfer = StockEnTransito(
        tenant=branch.tenant,
        source_branch=branch,
        destination_branch=branch,
        part=part,
        quantity=Decimal("5"),
        expected_arrival="2026-08-20",
    )
    with pytest.raises(ValidationError):
        transfer.full_clean()


@pytest.mark.django_db
def test_stock_en_transito_zero_quantity_invalid(branch, part):
    destination = BranchFactory(tenant=branch.tenant, code="DEST-003")
    transfer = StockEnTransito(
        tenant=branch.tenant,
        source_branch=branch,
        destination_branch=destination,
        part=part,
        quantity=Decimal("0"),
        expected_arrival="2026-08-20",
    )
    with pytest.raises(ValidationError):
        transfer.full_clean()
