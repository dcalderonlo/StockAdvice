"""Velocity calculation service for the catalog.

This module ports the validated Phase 0 spike formulas to Django. It reads
historical sales from ``StockMovement`` records and derives velocity,
stock-turn ratio, coverage days, and projected demand.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import UUID

import structlog
from django.db import models
from django.utils import timezone

from apps.branches.models import Branch, BranchType
from apps.core.models import Tenant
from apps.inventory.models import StockLevel, StockMovement, StockMovementType

if TYPE_CHECKING:
    from apps.catalog.models import Part

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class VelocityResult:
    """Result of a velocity calculation for a Part and/or Branch.

    For org-wide calculations ``branch_id`` is ``None``.
    For distribution-center aggregations ``part_id`` is ``None`` because the
    result represents the DC's total demand across all parts.
    """

    part_id: Optional[UUID]
    branch_id: Optional[UUID]
    velocity: float  # units/month
    annual_sales: float  # units in the calculation window
    stock_turn_ratio: float
    coverage_days: float
    projected_demand: float  # units for the requested period
    period_days: int
    is_cold_start: bool
    last_updated: datetime

    def to_dict(self) -> dict:
        return {
            "part_id": str(self.part_id) if self.part_id else None,
            "branch_id": str(self.branch_id) if self.branch_id else None,
            "velocity": self.velocity,
            "annual_sales": self.annual_sales,
            "stock_turn_ratio": self.stock_turn_ratio,
            "coverage_days": self.coverage_days,
            "projected_demand": self.projected_demand,
            "period_days": self.period_days,
            "is_cold_start": self.is_cold_start,
            "last_updated": self.last_updated.isoformat(),
        }


class VelocityCalculator:
    """Calculates sales velocity, coverage, and projected demand.

    The weighted average uses a linear ramp from 0.5 (oldest month) to 1.5
    (most recent month), exactly as validated in the Phase 0 spike.
    """

    def __init__(self, tenant: Tenant):
        self.tenant = tenant

    @staticmethod
    def _month_sequence(today: date, months: int) -> list[tuple[int, int]]:
        """Return a list of (year, month) tuples from oldest to newest."""
        if months <= 0:
            return []

        # Start with the first day of the current month and walk backwards.
        current_year, current_month = today.year, today.month
        sequence: list[tuple[int, int]] = []
        for offset in range(months - 1, -1, -1):
            year, month = current_year, current_month - offset
            while month <= 0:
                year -= 1
                month += 12
            sequence.append((year, month))
        return sequence

    @staticmethod
    def _weighted_velocity(monthly_sales: list[float]) -> float:
        """Linear weighted average: oldest month = 0.5, newest = 1.5."""
        if not monthly_sales:
            return 0.0

        n = len(monthly_sales)
        weights = [0.5 + (i / max(n - 1, 1)) for i in range(n)]
        weighted_sum = sum(qty * weight for qty, weight in zip(monthly_sales, weights))
        weight_total = sum(weights)
        return weighted_sum / weight_total if weight_total else 0.0

    @staticmethod
    def calculate_stock_turn_ratio(
        annual_sales: float, average_stock_value: float
    ) -> float:
        """Rotación de Stock = annual sales / average stock value."""
        if average_stock_value <= 0:
            return 0.0
        return annual_sales / average_stock_value

    @classmethod
    def calculate_coverage_days(
        cls, annual_sales: float, average_stock_value: float
    ) -> float:
        """Cobertura = 365 / Stock Turn Ratio."""
        str_ratio = cls.calculate_stock_turn_ratio(annual_sales, average_stock_value)
        if str_ratio <= 0:
            return 0.0
        return 365.0 / str_ratio

    @staticmethod
    def calculate_projected_demand(velocity: float, period_days: int) -> float:
        """Projected demand = velocity × (period_days / 30)."""
        if velocity <= 0 or period_days <= 0:
            return 0.0
        return velocity * (period_days / 30.0)

    def _get_monthly_sales(
        self,
        part: "Part",
        branches: models.QuerySet[Branch] | Branch | None,
        months: int,
    ) -> list[float]:
        """Return monthly sales totals (oldest to newest) for the given window."""
        today = date.today()
        month_sequence = self._month_sequence(today, months)
        if not month_sequence:
            return []

        movements = StockMovement.objects.filter(
            tenant=self.tenant,
            part=part,
            movement_type=StockMovementType.SALE,
            movement_date__year__gte=month_sequence[0][0],
            movement_date__year__lte=month_sequence[-1][0],
        )

        if branches is None:
            movements = movements.filter(branch__tenant=self.tenant)
        elif isinstance(branches, Branch):
            movements = movements.filter(branch=branches)
        else:
            movements = movements.filter(branch__in=branches)

        totals: dict[tuple[int, int], Decimal] = {}
        for movement in movements.iterator():
            year_month = (movement.movement_date.year, movement.movement_date.month)
            if year_month not in totals:
                totals[year_month] = Decimal("0")
            # Sales are stored as negative quantities; use the absolute sale amount.
            totals[year_month] += abs(movement.quantity)

        return [
            float(totals.get(year_month, Decimal("0"))) for year_month in month_sequence
        ]

    def _average_stock_value(
        self,
        part: "Part",
        branches: models.QuerySet[Branch] | Branch | None,
    ) -> float:
        """Return the average stock disponible for the given scope."""
        qs = StockLevel.objects.filter(tenant=self.tenant, part=part)
        if branches is None:
            qs = qs.filter(branch__tenant=self.tenant)
        elif isinstance(branches, Branch):
            qs = qs.filter(branch=branches)
        else:
            qs = qs.filter(branch__in=branches)

        avg = qs.aggregate(avg=models.Avg("stock_disponible"))["avg"] or Decimal("0")
        return float(avg)

    def _build_result(
        self,
        part_id: Optional[UUID],
        branch_id: Optional[UUID],
        monthly_sales: list[float],
        average_stock_value: float,
        period_days: int,
    ) -> VelocityResult:
        """Build a ``VelocityResult`` from raw monthly sales."""
        velocity = self._weighted_velocity(monthly_sales)
        annual_sales = sum(monthly_sales)
        str_ratio = self.calculate_stock_turn_ratio(annual_sales, average_stock_value)
        coverage_days = self.calculate_coverage_days(annual_sales, average_stock_value)
        projected_demand = self.calculate_projected_demand(velocity, period_days)
        is_cold_start = not monthly_sales or all(sale == 0 for sale in monthly_sales)

        return VelocityResult(
            part_id=part_id,
            branch_id=branch_id,
            velocity=velocity,
            annual_sales=annual_sales,
            stock_turn_ratio=str_ratio,
            coverage_days=coverage_days,
            projected_demand=projected_demand,
            period_days=period_days,
            is_cold_start=is_cold_start,
            last_updated=timezone.now(),
        )

    def calculate_for_part(
        self,
        part: "Part",
        branch: Optional[Branch] = None,
        months: int = 12,
        period_days: int = 30,
    ) -> VelocityResult:
        """Calculate velocity for a single part, optionally scoped to a branch.

        If ``branch`` is ``None``, sales are aggregated across all branches of
        the tenant and the average stock is computed across those branches.
        """
        monthly_sales = self._get_monthly_sales(part, branch, months)
        average_stock = self._average_stock_value(part, branch)

        return self._build_result(
            part_id=part.id,
            branch_id=branch.id if branch else None,
            monthly_sales=monthly_sales,
            average_stock_value=average_stock,
            period_days=period_days,
        )

    def calculate_for_all_parts(
        self,
        branch: Optional[Branch] = None,
        months: int = 12,
        period_days: int = 30,
    ) -> dict[UUID, VelocityResult]:
        """Calculate velocity for every active part in the tenant.

        Returns a mapping of ``part_id`` to ``VelocityResult``.
        """
        from apps.catalog.models import Part

        parts = Part.objects.filter(tenant=self.tenant, is_active=True).order_by("id")
        results: dict[UUID, VelocityResult] = {}
        for part in parts.iterator():
            results[part.id] = self.calculate_for_part(
                part=part,
                branch=branch,
                months=months,
                period_days=period_days,
            )
        return results

    def calculate_for_dc(
        self,
        distribution_center: Branch,
        months: int = 12,
        period_days: int = 30,
    ) -> VelocityResult:
        """Calculate aggregate velocity for a distribution center.

        The DC's velocity is its own historical sales rate PLUS the sum of the
        historical sales rates of all dependent branches.

        Raises:
            ValueError: If the provided branch is not a distribution center.
        """
        if distribution_center.type != BranchType.CENTRO_DISTRIBUCION:
            raise ValueError(
                f"Branch {distribution_center.code} is not a distribution center"
            )

        dependent_branches = distribution_center.dependent_branches.filter(
            tenant=self.tenant, is_active=True
        )
        branches = [distribution_center] + list(dependent_branches)

        from apps.catalog.models import Part

        today = date.today()
        month_sequence = self._month_sequence(today, months)
        aggregate_monthly_sales = [0.0] * len(month_sequence)
        aggregate_average_stock = 0.0

        for part in Part.objects.filter(tenant=self.tenant, is_active=True).iterator():
            monthly_sales = self._get_monthly_sales(part, branches, months)
            for i, value in enumerate(monthly_sales):
                aggregate_monthly_sales[i] += value
            aggregate_average_stock += self._average_stock_value(part, branches)

        return self._build_result(
            part_id=None,
            branch_id=distribution_center.id,
            monthly_sales=aggregate_monthly_sales,
            average_stock_value=aggregate_average_stock,
            period_days=period_days,
        )
