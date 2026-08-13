"""Tests for the inventory ingestion service."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.catalog.models import Part
from apps.inventory.models import StockEnTransito, StockLevel, StockMovement
from apps.inventory.services import InventoryIngestionService

from .factories import BranchFactory, PartFactory, TenantFactory


@pytest.fixture
def tenant():
    return TenantFactory()


@pytest.fixture
def branch(tenant):
    return BranchFactory(tenant=tenant, code="SUC-001")


@pytest.fixture
def parts(tenant):
    return [PartFactory(tenant=tenant, internal_sku_code=f"SKU-{i:04d}") for i in range(1, 6)]


@pytest.mark.django_db
def test_sync_stock_creates_stock_levels(branch, parts):
    service = InventoryIngestionService(branch.tenant)
    updated = service.sync_stock(branch.code)

    assert updated > 0
    assert StockLevel.objects.filter(tenant=branch.tenant, branch=branch).count() > 0

    level = StockLevel.objects.get(tenant=branch.tenant, branch=branch, part=parts[0])
    assert level.stock_disponible >= 0
    assert level.last_synced_at is not None


@pytest.mark.django_db
def test_sync_stock_missing_sku_logged_but_not_crash(branch, tenant):
    # Catalog contains SKU-0001, but mock stock data includes many SKUs.
    # Create only one part so most DMS SKUs are missing locally.
    PartFactory(tenant=tenant, internal_sku_code="SKU-0001")
    service = InventoryIngestionService(tenant)

    updated = service.sync_stock(branch.code)

    assert updated >= 1


@pytest.mark.django_db
def test_sync_sales_records_negative_sale_movements(branch, parts):
    service = InventoryIngestionService(branch.tenant)
    since = date.today() - timedelta(days=400)
    recorded = service.sync_sales(branch.code, since)

    assert recorded > 0
    movement = StockMovement.objects.filter(
        tenant=branch.tenant,
        branch=branch,
    ).first()
    assert movement is not None
    assert movement.quantity < 0


@pytest.mark.django_db
def test_sync_sales_idempotent(branch, parts):
    service = InventoryIngestionService(branch.tenant)
    since = date.today() - timedelta(days=400)
    service.sync_sales(branch.code, since)
    first_count = StockMovement.objects.filter(
        tenant=branch.tenant, branch=branch
    ).count()

    service.sync_sales(branch.code, since)
    second_count = StockMovement.objects.filter(
        tenant=branch.tenant, branch=branch
    ).count()

    assert first_count == second_count


@pytest.mark.django_db
def test_sync_purchase_orders_updates_stock_en_transito(branch, parts):
    service = InventoryIngestionService(branch.tenant)
    service.sync_purchase_orders(branch.code)

    assert StockEnTransito.objects.filter(
        tenant=branch.tenant, destination_branch=branch
    ).exists()

    level = StockLevel.objects.get(tenant=branch.tenant, branch=branch, part=parts[0])
    assert level.stock_en_transito > 0


@pytest.mark.django_db
def test_get_or_create_stock_level_returns_existing(branch, parts):
    service = InventoryIngestionService(branch.tenant)
    existing = StockLevel.objects.create(
        tenant=branch.tenant,
        branch=branch,
        part=parts[0],
        stock_disponible=Decimal("7"),
    )
    fetched = service.get_or_create_stock_level(branch, parts[0])
    assert fetched == existing
    assert fetched.stock_disponible == Decimal("7")


@pytest.mark.django_db
def test_run_full_sync_updates_all_branches(tenant):
    branches = [BranchFactory(tenant=tenant, code=code) for code in ["SUC-001", "SUC-002"]]
    for branch in branches:
        PartFactory(tenant=tenant, internal_sku_code="SKU-0001")

    service = InventoryIngestionService(tenant)
    results = service.run_full_sync()

    assert results["branches"] == 2
    assert results["stock_levels"] > 0


@pytest.mark.django_db
def test_record_movement_from_purchase(branch, parts):
    service = InventoryIngestionService(branch.tenant)
    movement = service.record_movement_from_purchase(
        branch=branch,
        part=parts[0],
        quantity=Decimal("20"),
        movement_date=date.today(),
        ref="PO-123",
    )
    assert movement.quantity == Decimal("20")
    assert movement.external_reference == "PO-123"
    assert movement.is_inflow() is True
