"""Planning calculation engine.

Ports the validated Phase 0 spike formulas to Django. Computes Planning
Target (PT), Reorder Point (PP), Order Quantity (CP), and excess stock
per part per branch. The service is side-effect free: it reads stock levels
but never writes to the database.

Formula baseline (material-aligned, per user decision 2026-08-08):

- Planning Target = (velocity / 30) × (period + security + lead_time)
- Reorder Point   = Planning Target + lead_time (raw numeric addition)
- Order Quantity = max(0, Planning Target − available_stock − in_transit_stock)
- Excess stock       = max(0, current_stock − Reorder Point)

Planning Target INCLUDES lead time. Reorder Point is computed by literally
adding lead time in days to Planning Target in units, matching the source
material's example.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import UUID

import structlog
from django.utils import timezone

from apps.branches.models import Branch, BranchType
from apps.core.models import Tenant
from apps.inventory.models import StockLevel

if TYPE_CHECKING:
    from apps.catalog.models import Part
    from apps.catalog.services import VelocityCalculator

logger = structlog.get_logger(__name__)

DEFAULT_PERIOD_DAYS = 30
DEFAULT_SECURITY_DAYS = 10


@dataclass(frozen=True)
class PlanningResult:
    """Result of planning calculation for a Part at a Branch."""

    part_id: UUID
    branch_id: UUID
    velocity: float  # units/month
    period_days: int
    security_days: int
    lead_time_days: int
    planning_target: float  # units
    reorder_point: float  # units (raw addition per material convention)
    available_stock: float
    in_transit_stock: float
    order_quantity: float  # units to order
    excess_stock: float  # available for inter-branch transfer
    triggered: bool  # True if available_stock <= reorder_point
    calculated_at: datetime

    def to_dict(self) -> dict:
        return {
            "part_id": str(self.part_id),
            "branch_id": str(self.branch_id),
            "velocity": self.velocity,
            "period_days": self.period_days,
            "security_days": self.security_days,
            "lead_time_days": self.lead_time_days,
            "planning_target": self.planning_target,
            "reorder_point": self.reorder_point,
            "available_stock": self.available_stock,
            "in_transit_stock": self.in_transit_stock,
            "order_quantity": self.order_quantity,
            "excess_stock": self.excess_stock,
            "triggered": self.triggered,
            "calculated_at": self.calculated_at.isoformat(),
        }


class PlanningCalculator:
    """Computes planning metrics per part per branch.

    Uses the material-aligned formula (PT INCLUDES lead time, PP = PT +
    lead_time_days raw). All calculations are pure: no database writes.
    """

    def __init__(self, tenant: Tenant):
        self.tenant = tenant

    def _planning_config(self) -> dict:
        """Return the tenant's planning configuration subsection."""
        config = self.tenant.config or {}
        return config.get("planning", {}) if isinstance(config, dict) else {}

    def get_default_period_days(self, branch: Branch) -> int:
        """Return default period_days from tenant config, fallback to 30."""
        value = self._planning_config().get("default_period_days")
        if isinstance(value, int) and value >= 0:
            return value
        return DEFAULT_PERIOD_DAYS

    def get_default_security_days(self, branch: Branch) -> int:
        """Return default security_days from tenant config, fallback to 10."""
        value = self._planning_config().get("default_security_days")
        if isinstance(value, int) and value >= 0:
            return value
        return DEFAULT_SECURITY_DAYS

    def get_lead_time(self, part: "Part", branch: Branch) -> int:
        """Return the lead time to use for a part at a branch.

        Currently only per-part (supplier) lead time is modelled. Per-branch
        default lead time requires a future migration to ``Branch``; when that
        field exists this method will prefer the most specific value available
        (per-supplier over per-branch default) and log when falling back.
        """
        return part.lead_time_days

    @staticmethod
    def _to_float(value: Decimal | float | int | None, default: float = 0.0) -> float:
        """Coerce a stock value to float, treating None as default."""
        if value is None:
            return default
        return float(value)

    @staticmethod
    def _clamp_non_negative(value: float, context: str) -> float:
        """Clamp negative stock values to zero and log a warning."""
        if value < 0:
            logger.warning(
                "planning_negative_stock_clamped",
                context=context,
                raw_value=value,
            )
            return 0.0
        return value

    @classmethod
    def calculate_planning_target(
        cls,
        velocity: float,
        period_days: int,
        security_days: int,
        lead_time_days: int,
    ) -> float:
        """Planning Target = (velocity / 30) × (period + security + lead_time)."""
        if velocity < 0:
            velocity = 0.0
        return (velocity / 30.0) * (period_days + security_days + lead_time_days)

    @classmethod
    def calculate_punto_de_pedido(
        cls, planning_target_value: float, lead_time_days: int
    ) -> float:
        """Punto de Pedido = Planning Target + lead_time_days (raw addition)."""
        return planning_target_value + lead_time_days

    @classmethod
    def calculate_cantidad_de_pedido(
        cls,
        planning_target_value: float,
        available_stock: float,
        in_transit_stock: float,
    ) -> float:
        """Order Quantity = max(0, PT − available − in transit)."""
        return max(
            0.0,
            planning_target_value - available_stock - in_transit_stock,
        )

    @classmethod
    def calculate_excess_stock(
        cls, current_stock: float, reorder_point_value: float
    ) -> float:
        """Excess stock = max(0, current_stock − Reorder Point)."""
        return max(0.0, current_stock - reorder_point_value)

    def _read_stock_levels(
        self, part: "Part", branch: Branch
    ) -> tuple[float, float]:
        """Read disponible and en_transito stock from StockLevel if needed."""
        try:
            sl = StockLevel.objects.get(
                tenant=self.tenant, branch=branch, part=part
            )
        except StockLevel.DoesNotExist:
            logger.info(
                "planning_no_stock_level",
                part_id=str(part.id),
                branch_id=str(branch.id),
            )
            return 0.0, 0.0

        disponible = self._clamp_non_negative(
            self._to_float(sl.available_stock), "available_stock"
        )
        transito = self._clamp_non_negative(
            self._to_float(sl.in_transit_stock), "in_transit_stock"
        )
        return disponible, transito

    def calculate_for_part(
        self,
        part: "Part",
        branch: Branch,
        velocity: Optional[float] = None,
        available_stock: Optional[float] = None,
        in_transit_stock: Optional[float] = None,
        period_days: Optional[int] = None,
        security_days: Optional[int] = None,
        run_date: Optional[date] = None,
        run_id: Optional[str] = None,
    ) -> PlanningResult:
        """Calculate planning metrics for one part at one branch.

        Parameters
        ----------
        velocity:
            Units per month. If ``None`` and no active override exists, the
            value is computed with ``VelocityCalculator``.
        available_stock, in_transit_stock:
            If ``None``, values are read from ``StockLevel``.
        period_days, security_days:
            If ``None``, tenant defaults are used.
        run_date:
            Date used to evaluate WITH_EXPIRY overrides. Defaults to today.
        run_id:
            Identifier used to match PER_RUN overrides.
        """
        period = (
            period_days
            if period_days is not None
            else self.get_default_period_days(branch)
        )
        security = (
            security_days
            if security_days is not None
            else self.get_default_security_days(branch)
        )
        lead_time = self.get_lead_time(part, branch)

        # Active demand overrides take precedence over calculated velocity.
        from apps.catalog.overrides import OverrideService

        override_service = OverrideService(self.tenant)
        active_override = override_service.get_active_override(
            part=part, branch=branch, run_date=run_date, run_id=run_id
        )
        if active_override is not None:
            velocity = float(active_override.override_value)
        elif velocity is None:
            from apps.catalog.services import VelocityCalculator

            velocity_result = VelocityCalculator(self.tenant).calculate_for_part(
                part, branch
            )
            velocity = velocity_result.velocity

        if velocity < 0:
            logger.warning(
                "planning_negative_velocity_clamped",
                part_id=str(part.id),
                raw_velocity=velocity,
            )
            velocity = 0.0

        # Material-aligned formula: PT INCLUDES lead time.
        pt = self.calculate_planning_target(
            velocity=velocity,
            period_days=period,
            security_days=security,
            lead_time_days=lead_time,
        )

        # PP = PT + lead_time_days (raw, matches material example).
        pp = self.calculate_punto_de_pedido(pt, lead_time)

        # Resolve stock (read from DB only when not provided).
        read_disponible, read_transito = None, None
        if available_stock is None or in_transit_stock is None:
            read_disponible, read_transito = self._read_stock_levels(part, branch)

        disponible = (
            self._clamp_non_negative(float(available_stock), "available_stock")
            if available_stock is not None
            else read_disponible
        )
        transito = (
            self._clamp_non_negative(float(in_transit_stock), "in_transit_stock")
            if in_transit_stock is not None
            else read_transito
        )

        current_stock = disponible + transito

        cp = self.calculate_cantidad_de_pedido(pt, disponible, transito)
        excess = self.calculate_excess_stock(current_stock, pp)
        triggered = disponible <= pp

        return PlanningResult(
            part_id=part.id,
            branch_id=branch.id,
            velocity=velocity,
            period_days=period,
            security_days=security,
            lead_time_days=lead_time,
            planning_target=pt,
            reorder_point=pp,
            available_stock=disponible,
            in_transit_stock=transito,
            order_quantity=cp,
            excess_stock=excess,
            triggered=triggered,
            calculated_at=timezone.now(),
        )

    def calculate_for_all_parts(
        self,
        branch: Branch,
        velocity_calculator: "VelocityCalculator",
        period_days: Optional[int] = None,
        security_days: Optional[int] = None,
    ) -> dict[UUID, PlanningResult]:
        """Calculate planning metrics for all active parts at one branch."""
        from apps.catalog.models import Part

        parts = Part.objects.filter(tenant=self.tenant, is_active=True).order_by("id")
        results: dict[UUID, PlanningResult] = {}
        for part in parts.iterator():
            velocity_result = velocity_calculator.calculate_for_part(part, branch)
            results[part.id] = self.calculate_for_part(
                part=part,
                branch=branch,
                velocity=velocity_result.velocity,
                period_days=period_days,
                security_days=security_days,
            )
        return results

    def calculate_for_dc(
        self,
        distribution_center: Branch,
        velocity_calculator: "VelocityCalculator",
        period_days: Optional[int] = None,
        security_days: Optional[int] = None,
    ) -> dict[UUID, PlanningResult]:
        """Calculate planning for a distribution center.

        The DC serves its own sales plus the sales of all dependent branches,
        so the planning velocity for each part is the DC's own velocity plus
        the sum of each dependent branch's velocity for that part.

        Raises:
            ValueError: If ``distribution_center`` is not a distribution center.
        """
        if distribution_center.type != BranchType.DISTRIBUTION_CENTER:
            raise ValueError(
                f"Branch {distribution_center.code} is not a distribution center"
            )

        from apps.catalog.models import Part

        dependent_branches = list(
            distribution_center.dependent_branches.filter(
                tenant=self.tenant, is_active=True
            )
        )

        results: dict[UUID, PlanningResult] = {}
        for part in Part.objects.filter(tenant=self.tenant, is_active=True).order_by(
            "id"
        ):
            own_velocity = velocity_calculator.calculate_for_part(
                part, distribution_center
            ).velocity
            dependent_velocity = sum(
                velocity_calculator.calculate_for_part(part, dep).velocity
                for dep in dependent_branches
            )
            total_velocity = own_velocity + dependent_velocity

            results[part.id] = self.calculate_for_part(
                part=part,
                branch=distribution_center,
                velocity=total_velocity,
                period_days=period_days,
                security_days=security_days,
            )
        return results
