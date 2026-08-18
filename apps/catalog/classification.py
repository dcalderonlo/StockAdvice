"""Classification engine: Volume Class + Lifecycle Stage derivation.

This module ports the validated Phase 0 spike logic to Django. It reads
``StockMovement`` records, computes annual sales and time-since-last-sale,
and persists ``ClassificationResult`` snapshots.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from django.db import models
from django.utils import timezone

from apps.core.models import Tenant
from apps.inventory.models import StockLevel, StockMovement, StockMovementType

from .models import ClassificationResult, LifecycleStage, Part

if TYPE_CHECKING:
    from apps.branches.models import Branch

logger = structlog.get_logger(__name__)


def volume_class(annual_sales: int, sector_config=None) -> str:
    """Volume Class (VC1–VC8) based on annual sales volume.

    When ``sector_config`` is provided, the label is resolved from the sector's
    configured VC thresholds. Otherwise, the hardcoded Phase 0 spike / proposal
    thresholds are used:
      VC1 > 250, VC2 121–250, VC3 61–120, VC4 31–60,
      VC5 15–30, VC6 7–14, VC7 4–6, VC8 1–3.
    Zero annual sales return an empty string (cold-start).
    """
    if sector_config is not None:
        return sector_config.get_vc_label(annual_sales)
    if annual_sales >= 251:
        return "VC1"
    if annual_sales >= 121:
        return "VC2"
    if annual_sales >= 61:
        return "VC3"
    if annual_sales >= 31:
        return "VC4"
    if annual_sales >= 15:
        return "VC5"
    if annual_sales >= 7:
        return "VC6"
    if annual_sales >= 4:
        return "VC7"
    if annual_sales >= 1:
        return "VC8"
    return ""


def lifecycle_stage(
    months_since_first_seen: int | None = None,
    months_since_last_sale: int | None = None,
    has_stock: bool = False,
    sector_config=None,
) -> str:
    """Return a lifecycle stage code based on age and sales history.

    When ``sector_config`` is provided, the rules are read from the sector's
    configured lifecycle stages. Otherwise, the hardcoded default automotive
    rules are used.
    """
    if sector_config is not None:
        return sector_config.get_lifecycle_stage(
            months_since_first_seen=months_since_first_seen,
            months_since_last_sale=months_since_last_sale,
            has_stock=has_stock,
        )

    # Hardcoded automotive fallback (matches default sector configuration).
    if months_since_last_sale is not None and months_since_last_sale >= 24:
        return "OBSOLETE"
    if months_since_last_sale is not None and months_since_last_sale >= 12:
        return "PRE_OBSOLETE" if has_stock else "INACTIVE"
    if months_since_first_seen is not None and months_since_first_seen <= 6:
        return "NEW"
    return "ACTIVE"


def new_subtype(first_six_month_sales: int) -> str:
    """New-part sub-code based on sales in the first six months.

    N1: > 15 sales, N2: 4–15 sales, N3: 0–3 sales.
    """
    if first_six_month_sales > 15:
        return "N1"
    if first_six_month_sales >= 4:
        return "N2"
    return "N3"


class ClassificationEngine:
    """Derives Volume Class and Lifecycle Stage for parts in a tenant."""

    def __init__(
        self,
        tenant: Tenant,
        today: date | None = None,
        sector_config=None,
    ):
        self.tenant = tenant
        self.today = today or date.today()
        self.sector_config = sector_config

    def _get_sector_config(self):
        """Return the sector configuration to use for classification.

        Caches the lookup on the engine instance so repeated calls within a
        classification pass use the same configuration snapshot.
        """
        if self.sector_config is None:
            self.sector_config = self.tenant.get_sector_config()
        return self.sector_config

    def _sale_movements(
        self, part: Part, branch: "Branch | None" = None
    ) -> models.QuerySet[StockMovement]:
        """Return SALE movements for the part, optionally scoped to a branch.

        Movements dated in the future relative to ``self.today`` are ignored;
        the engine only classifies from historical data.
        """
        qs = StockMovement.objects.filter(
            tenant=self.tenant,
            part=part,
            movement_type=StockMovementType.SALE,
            movement_date__lte=self.today,
        )
        if branch is not None:
            qs = qs.filter(branch=branch)
        return qs

    def _annual_sales(self, movements: models.QuerySet[StockMovement]) -> int:
        """Sum of sale quantities in the trailing 365 days."""
        one_year_ago = self.today - timedelta(days=365)
        total = (
            movements.filter(movement_date__gte=one_year_ago).aggregate(
                total=models.Sum("quantity")
            )["total"]
            or Decimal("0")
        )
        return int(abs(total))

    def _first_six_month_sales(
        self, part: Part, movements: models.QuerySet[StockMovement]
    ) -> int:
        """Sum of sale quantities in the first six months after ``created_at``."""
        entry_date = part.created_at.date()
        window_end = entry_date + timedelta(days=180)
        cutoff = min(window_end, self.today)
        total = (
            movements.filter(
                movement_date__gte=entry_date, movement_date__lte=cutoff
            ).aggregate(total=models.Sum("quantity"))["total"]
            or Decimal("0")
        )
        return int(abs(total))

    def _months_since_first_seen(self, part: Part) -> int:
        """Whole months since the part was created."""
        entry_date = part.created_at.date()
        return (
            self.today.year - entry_date.year
        ) * 12 + (self.today.month - entry_date.month)

    def _has_stock(self, part: Part, branch: "Branch | None" = None) -> bool:
        """Return True if the part has any positive stock disponible."""
        qs = StockLevel.objects.filter(tenant=self.tenant, part=part)
        if branch is not None:
            qs = qs.filter(branch=branch)
        total = qs.aggregate(total=models.Sum("stock_disponible"))["total"] or Decimal(
            "0"
        )
        return total > 0

    def _determine_stage(
        self,
        part: Part,
        movements: models.QuerySet[StockMovement],
        branch: "Branch | None",
    ) -> tuple[LifecycleStage, str]:
        """Return the lifecycle stage and subcode for a part.

        Logic follows the material-aligned interpretation:
          - Special flags override everything.
          - Never-sold parts <= 6 months old are New (N3).
          - Never-sold parts > 6 months old with no stock are Inactive.
          - Never-sold parts > 6 months old with stock are Active (OBS-N is not
            modelled as a distinct stage in this WU).
          - > 24 months without sales → Obsolete (OBS-R).
          - > 12 months without sales with stock → Pre-Obsolete (OBS-P).
          - > 12 months without sales without stock → Inactive.
          - <= 6 months since entry → New (N1/N2/N3).
          - Otherwise → Active.
        """
        special_flags = part.special_flags or {}
        if special_flags.get("is_campaign"):
            return LifecycleStage.SPECIAL_CAMPAIGN, "NS-C"
        if special_flags.get("is_non_stock"):
            return LifecycleStage.SPECIAL_NON_STOCK, "NS-NS"

        months_since_first_seen = self._months_since_first_seen(part)
        last_sale = movements.order_by("-movement_date").first()

        if last_sale is None:
            # Never sold.
            if months_since_first_seen <= 6:
                return LifecycleStage.NEW, new_subtype(0)
            if not self._has_stock(part, branch):
                return LifecycleStage.INACTIVE, "INACT"
            return LifecycleStage.ACTIVE, ""

        days_since_last_sale = (self.today - last_sale.movement_date).days

        if days_since_last_sale > 730:
            return LifecycleStage.OBSOLETE, "OBS-R"

        has_stock = self._has_stock(part, branch)
        if days_since_last_sale > 365:
            if not has_stock:
                return LifecycleStage.INACTIVE, "INACT"
            return LifecycleStage.PRE_OBSOLETE, "OBS-P"

        if months_since_first_seen <= 6:
            first_six_month_sales = self._first_six_month_sales(part, movements)
            return LifecycleStage.NEW, new_subtype(first_six_month_sales)

        return LifecycleStage.ACTIVE, ""

    def classify_part(
        self, part: Part, branch: "Branch | None" = None
    ) -> ClassificationResult:
        """Classify a single part and persist the result."""
        movements = self._sale_movements(part, branch)
        stage, subcode = self._determine_stage(part, movements, branch)

        annual_sales = self._annual_sales(movements)

        last_sale = movements.order_by("-movement_date").first()
        days_since_last_sale = (
            (self.today - last_sale.movement_date).days if last_sale else None
        )
        months_since_first_seen = self._months_since_first_seen(part)

        vc = ""
        if stage not in (
            LifecycleStage.SPECIAL_CAMPAIGN,
            LifecycleStage.SPECIAL_NON_STOCK,
        ):
            vc = volume_class(annual_sales, sector_config=self._get_sector_config())

        result, _ = ClassificationResult.objects.update_or_create(
            tenant=self.tenant,
            part=part,
            branch=branch,
            classifier_version="1.0",
            defaults={
                "volume_class": vc,
                "lifecycle_stage": stage,
                "lifecycle_subcode": subcode,
                "annual_sales": annual_sales,
                "days_since_last_sale": days_since_last_sale,
                "months_since_first_seen": months_since_first_seen,
                "classified_at": timezone.now(),
                "special_flags": part.special_flags or {},
            },
        )
        return result

    def classify_all_parts(
        self, branch: "Branch | None" = None
    ) -> list[ClassificationResult]:
        """Classify every active part in the tenant, optionally scoped to a branch."""
        results: list[ClassificationResult] = []
        qs = Part.objects.filter(tenant=self.tenant, is_active=True).order_by("id")
        for part in qs.iterator():
            results.append(self.classify_part(part, branch=branch))
        return results

    def classify_tenant(
        self,
        tenant: Tenant | None = None,
    ) -> dict[UUID, ClassificationResult]:
        """Classify all active parts across all branches for the tenant.

        Returns a mapping of ``part_id`` to the tenant-wide classification.
        """
        target_tenant = tenant or self.tenant
        engine = ClassificationEngine(target_tenant, today=self.today)
        results: dict[UUID, ClassificationResult] = {}
        for part in (
            Part.objects.filter(tenant=target_tenant, is_active=True).order_by("id").iterator()
        ):
            results[part.id] = engine.classify_part(part, branch=None)
        return results
