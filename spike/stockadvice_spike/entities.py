"""Plain Python dataclasses for the Phase 0 spike.

These are intentionally simplified stand-ins for the Django models that will be
introduced in Phase 1. They keep the algorithm readable and testable without any
framework or database dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List


@dataclass(frozen=True)
class Part:
    """A catalog item (repuesto / spare part).

    In v1 this will become a Django model with cross-references, tenant_id, etc.
    """

    internal_sku_code: str
    primary_mfr_code: str
    description: str
    lead_time_days: int = 10
    # Lifecycle / special flags are simplified for the spike.
    is_non_stock: bool = False


@dataclass(frozen=True)
class StockLevel:
    """Live stock snapshot for a Part at a Branch."""

    part: Part
    branch_code: str
    stock_disponible: float  # physically available
    stock_en_transito: float  # inbound, not yet available


@dataclass(frozen=True)
class SalesMovement:
    """Monthly sales quantity for a Part at a Branch.

    `month_index` is 0 for the oldest month in the 12-month window and 11 for the
    most recent. This lets velocity weight recent months more heavily.
    """

    part: Part
    branch_code: str
    month_index: int  # 0..11, where 11 is the most recent month
    quantity: int
    period_start: date | None = None


@dataclass(frozen=True)
class BranchConfig:
    """Simplified branch-level planning parameters.

    In v1 these will live in Branch.config_json / Tenant.config_json.
    """

    branch_code: str
    period_days: int = 30
    security_days: int = 10


@dataclass(frozen=True)
class PlanningResult:
    """Derived planning metrics for one Part / Branch combination."""

    part: Part
    branch_code: str
    velocity: float  # weighted average units per month
    annual_sales: int  # sum of the 12-month sales history
    volume_class: str  # VC1..VC8
    planning_target: float
    punto_pedido: float
    stock_disponible: float
    stock_en_transito: float
    cantidad_pedido: float
    excess_stock: float


@dataclass(frozen=True)
class RecommendationSource:
    """Where a recommended quantity should come from."""

    source_type: str  # "transfer" | "supplier" | "no_action"
    source_branch_code: str | None = None
    quantity: float = 0.0
    reason: str = ""


@dataclass(frozen=True)
class Recommendation:
    """A concrete replenishment suggestion produced by the engine."""

    part: Part
    destination_branch_code: str
    quantity: float
    primary_source: RecommendationSource
    fill_sources: List[RecommendationSource] = field(default_factory=list)
    planning_result: PlanningResult | None = None
    is_partial: bool = False
    partial_gap: float = 0.0
