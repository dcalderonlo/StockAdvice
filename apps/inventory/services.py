"""Inventory ingestion and synchronization services."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import structlog
from django.db import transaction
from django.utils import timezone

from apps.branches.models import Branch
from apps.catalog.adapters.exceptions import DMSError
from apps.catalog.adapters.factory import get_dms_adapter
from apps.catalog.models import Part
from apps.core.models import Tenant

from .models import (
    StockEnTransito,
    StockEnTransitoStatus,
    StockLevel,
    StockMovement,
    StockMovementType,
)

logger = structlog.get_logger(__name__)


class InventoryIngestionService:
    """Reads inventory data from a tenant's DMS adapter and persists it locally."""

    def __init__(self, tenant: Tenant):
        self.tenant = tenant
        self.adapter = get_dms_adapter(tenant)

    def run_full_sync(self) -> dict[str, int]:
        """Sync stock, sales, and purchase orders for all active branches."""
        results = {"branches": 0, "stock_levels": 0, "movements": 0}
        branches = Branch.objects.filter(tenant=self.tenant, is_active=True)

        for branch in branches:
            logger.info(
                "ingestion.branch.start",
                tenant=str(self.tenant.id),
                branch=branch.code,
            )
            results["branches"] += 1
            results["stock_levels"] += self.sync_stock(branch.code)
            results["movements"] += self.sync_sales(
                branch.code, since_date=date.today() - timedelta(days=400)
            )
            self.sync_purchase_orders(branch.code)
            logger.info(
                "ingestion.branch.done",
                tenant=str(self.tenant.id),
                branch=branch.code,
            )

        return results

    def sync_stock(self, branch_code: str) -> int:
        """Read available stock from the DMS and persist to StockLevel."""
        try:
            stock_data = self.adapter.read_stock(branch_code)
        except DMSError as e:
            logger.error(
                "ingestion.stock.dms_error",
                branch=branch_code,
                error=str(e),
            )
            raise

        branch = Branch.objects.get(tenant=self.tenant, code=branch_code)
        updated = 0

        for sku, qty in stock_data.items():
            try:
                part = Part.objects.get(tenant=self.tenant, internal_sku_code=sku)
            except Part.DoesNotExist:
                logger.warning(
                    "ingestion.stock.sku_not_found",
                    sku=sku,
                    branch=branch_code,
                )
                continue

            stock_level, _ = StockLevel.objects.update_or_create(
                tenant=self.tenant,
                branch=branch,
                part=part,
                defaults={
                    "stock_disponible": Decimal(str(qty)),
                    "last_synced_at": timezone.now(),
                },
            )
            updated += 1
            logger.debug(
                "ingestion.stock.updated",
                branch=branch_code,
                sku=sku,
                quantity=stock_level.stock_disponible,
            )

        logger.info(
            "ingestion.stock.done",
            branch=branch_code,
            updated=updated,
        )
        return updated

    def sync_sales(self, branch_code: str, since_date: date) -> int:
        """Read historical monthly sales from the DMS and record SALE movements."""
        try:
            sales_data = self.adapter.read_sales(branch_code, since_date)
        except DMSError as e:
            logger.error(
                "ingestion.sales.dms_error",
                branch=branch_code,
                error=str(e),
            )
            raise

        return self.import_sales({branch_code: sales_data})

    def import_sales(self, sales_data: dict[str, dict[str, list[float]]]) -> int:
        """Record SALE movements from raw DMS sales data.

        ``sales_data`` maps branch code -> SKU -> list of monthly sales (most
        recent first). Parts and branches are matched within the tenant.
        Returns the number of movements recorded.
        """
        today = date.today()
        recorded = 0

        for branch_code, sku_sales in sales_data.items():
            try:
                branch = Branch.objects.get(tenant=self.tenant, code=branch_code)
            except Branch.DoesNotExist:
                logger.warning(
                    "ingestion.sales.branch_not_found",
                    branch=branch_code,
                )
                continue

            for sku, monthly_sales in sku_sales.items():
                try:
                    part = Part.objects.get(tenant=self.tenant, internal_sku_code=sku)
                except Part.DoesNotExist:
                    logger.warning(
                        "ingestion.sales.sku_not_found",
                        sku=sku,
                        branch=branch_code,
                    )
                    continue

                # Monthly sales are returned most recent first. Walk backwards
                # from today so each list index maps to a concrete month.
                for i, qty in enumerate(monthly_sales):
                    movement_date = today - timedelta(days=30 * i)
                    qty_decimal = Decimal(str(qty))
                    if qty_decimal == 0:
                        continue

                    self.record_movement_from_sale(
                        branch=branch,
                        part=part,
                        quantity=-qty_decimal,
                        movement_date=movement_date,
                    )
                    recorded += 1

            logger.info(
                "ingestion.sales.done",
                branch=branch_code,
                recorded=recorded,
            )

        return recorded

    def sync_purchase_orders(self, branch_code: str) -> None:
        """Read in-transit purchase orders from the DMS and update StockLevel."""
        try:
            orders = self.adapter.read_purchase_orders(branch_code)
        except DMSError as e:
            logger.error(
                "ingestion.purchase_orders.dms_error",
                branch=branch_code,
                error=str(e),
            )
            raise

        branch = Branch.objects.get(tenant=self.tenant, code=branch_code)
        transit_total: dict[Part, Decimal] = {}

        for order in orders:
            sku = order.get("sku")
            quantity = Decimal(str(order.get("quantity", 0)))
            expected_date = order.get("expected_date") or date.today()

            if not sku or quantity <= 0:
                continue

            try:
                part = Part.objects.get(tenant=self.tenant, internal_sku_code=sku)
            except Part.DoesNotExist:
                logger.warning(
                    "ingestion.purchase_orders.sku_not_found",
                    sku=sku,
                    branch=branch_code,
                )
                continue

            transit_total[part] = transit_total.get(part, Decimal("0")) + quantity

            StockEnTransito.objects.update_or_create(
                tenant=self.tenant,
                destination_branch=branch,
                part=part,
                external_reference=order.get("external_reference", ""),
                defaults={
                    "source_branch": branch,
                    "quantity": quantity,
                    "status": StockEnTransitoStatus.PENDING,
                    "expected_arrival": expected_date,
                },
            )

        for part, total in transit_total.items():
            stock_level, _ = StockLevel.objects.update_or_create(
                tenant=self.tenant,
                branch=branch,
                part=part,
                defaults={
                    "stock_en_transito": total,
                    "last_synced_at": timezone.now(),
                },
            )
            logger.debug(
                "ingestion.purchase_orders.updated",
                branch=branch_code,
                sku=part.internal_sku_code,
                transit=stock_level.stock_en_transito,
            )

        logger.info(
            "ingestion.purchase_orders.done",
            branch=branch_code,
            orders=len(orders),
        )

    def get_or_create_stock_level(self, branch: Branch, part: Part) -> StockLevel:
        """Return the StockLevel for a branch/part, creating it if necessary."""
        stock_level, _ = StockLevel.objects.get_or_create(
            tenant=self.tenant,
            branch=branch,
            part=part,
            defaults={
                "stock_disponible": Decimal("0"),
                "stock_en_transito": Decimal("0"),
            },
        )
        return stock_level

    @transaction.atomic
    def record_movement_from_sale(
        self,
        branch: Branch,
        part: Part,
        quantity: Decimal,
        movement_date: date,
    ) -> StockMovement:
        """Record a SALE movement (negative quantity for outflow).

        Calling this twice for the same branch/part/date is idempotent: the
        existing movement is returned and the quantity is updated.
        """
        movement, _ = StockMovement.objects.update_or_create(
            tenant=self.tenant,
            branch=branch,
            part=part,
            movement_type=StockMovementType.SALE,
            movement_date=movement_date,
            source="dms",
            external_reference="",
            defaults={"quantity": quantity},
        )
        return movement

    @transaction.atomic
    def record_movement_from_purchase(
        self,
        branch: Branch,
        part: Part,
        quantity: Decimal,
        movement_date: date,
        ref: str = "",
        notes: str = "",
    ) -> StockMovement:
        """Record a PURCHASE movement (positive quantity for inflow)."""
        movement, _ = StockMovement.objects.update_or_create(
            tenant=self.tenant,
            branch=branch,
            part=part,
            movement_type=StockMovementType.PURCHASE,
            movement_date=movement_date,
            source="dms",
            external_reference=ref,
            defaults={"quantity": quantity, "notes": notes},
        )
        return movement
