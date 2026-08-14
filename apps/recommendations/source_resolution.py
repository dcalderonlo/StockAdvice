"""Recommendation source resolution service.

Determines the source(s) for a replenishment recommendation, prioritising
inter-branch transfers over external supplier orders. A branch can only transfer
up to its excess stock = max(0, stock_actual - Punto de Pedido), ensuring the
source branch never falls below its own PP.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import structlog
from django.db import transaction

from apps.branches.models import Branch
from apps.catalog.planning import PlanningCalculator
from apps.catalog.services import VelocityCalculator
from apps.core.models import Tenant
from apps.inventory.models import StockLevel

from .models import Recommendation

if TYPE_CHECKING:
    from apps.catalog.models import Part

logger = structlog.get_logger(__name__)


class SourceResolutionService:
    """Resolve recommendation sources: inter-branch transfer, external supplier, or mixed."""

    def __init__(self, tenant: Tenant):
        self.tenant = tenant
        self.velocity_calculator = VelocityCalculator(tenant)
        self.planning_calculator = PlanningCalculator(tenant)

    @transaction.atomic
    def resolve_sources(self, recommendation: Recommendation) -> Recommendation:
        """Determine source(s) for ``recommendation`` and persist the result."""
        destination = recommendation.branch
        part = recommendation.part
        needed = recommendation.quantity

        candidates = self._find_candidate_source_branches(destination, part)
        candidate_excess = []
        for candidate in candidates:
            excess = self._compute_excess_for_branch(part, candidate)
            if excess > 0:
                candidate_excess.append((candidate, excess))

        # DC topology: parent DC is checked first, then other branches by excess.
        candidate_excess = self._sort_candidates_by_priority(destination, candidate_excess)
        allocations = self._greedy_allocate(needed, candidate_excess)

        total_allocated = sum(qty for _, qty in allocations)

        if len(allocations) == 0:
            # No internal excess available: external supplier only.
            source_type = "external_supplier"
            source_branch = None
            is_partial = False
            partial_gap = Decimal("0")
            source_breakdown = [
                {
                    "source_type": "external_supplier",
                    "source_branch": None,
                    "quantity": str(needed),
                }
            ]
        else:
            is_partial = total_allocated < needed
            partial_gap = max(Decimal("0"), needed - total_allocated)

            source_breakdown = []
            for branch, qty in allocations:
                source_breakdown.append(
                    {
                        "source_type": "inter_branch",
                        "source_branch": str(branch.id),
                        "quantity": str(qty),
                    }
                )
            if partial_gap > 0:
                source_breakdown.append(
                    {
                        "source_type": "external_supplier",
                        "source_branch": None,
                        "quantity": str(partial_gap),
                    }
                )

            # Use the largest allocation as the primary source for backward
            # compatibility with the simple source_type/source_branch fields.
            source_type = "inter_branch"
            source_branch = allocations[0][0]

        recommendation.source_type = source_type
        recommendation.source_branch = source_branch
        recommendation.source_breakdown = source_breakdown
        recommendation.is_partial = is_partial
        recommendation.partial_gap = partial_gap
        recommendation.save()

        logger.info(
            "source_resolution.done",
            recommendation_id=str(recommendation.id),
            destination_branch=destination.code,
            part=part.internal_sku_code,
            allocations=len(allocations),
            is_partial=is_partial,
            partial_gap=str(partial_gap),
        )
        return recommendation

    def _find_candidate_source_branches(
        self, destination: Branch, part: "Part"
    ) -> list[Branch]:
        """Return active branches (except destination) that hold stock of ``part``."""
        branch_ids_with_stock = StockLevel.objects.filter(
            tenant=self.tenant,
            part=part,
            stock_disponible__gt=0,
        ).values_list("branch_id", flat=True)

        return list(
            Branch.objects.filter(
                tenant=self.tenant,
                id__in=branch_ids_with_stock,
                is_active=True,
            ).exclude(id=destination.id)
        )

    def _compute_excess_for_branch(self, part: "Part", branch: Branch) -> Decimal:
        """Excess stock available for transfer from ``branch``.

        Uses the validated Phase 0 spike formula exactly:
        excess_stock = max(0, stock_actual - Punto de Pedido).
        """
        try:
            stock_level = StockLevel.objects.get(
                tenant=self.tenant, branch=branch, part=part
            )
        except StockLevel.DoesNotExist:
            return Decimal("0")

        velocity_result = self.velocity_calculator.calculate_for_part(part, branch)
        planning_result = self.planning_calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=velocity_result.velocity,
            stock_disponible=float(stock_level.stock_disponible),
            stock_en_transito=float(stock_level.stock_en_transito),
        )

        excess = PlanningCalculator.calculate_excess_stock(
            planning_result.stock_disponible + planning_result.stock_en_transito,
            planning_result.punto_pedido,
        )
        return Decimal(str(excess))

    @staticmethod
    def _sort_candidates_by_priority(
        destination: Branch,
        candidates: list[tuple[Branch, Decimal]],
    ) -> list[tuple[Branch, Decimal]]:
        """Sort candidates so the parent DC is first, then by excess descending."""
        parent_dc_id = destination.parent_branch_id

        def sort_key(item: tuple[Branch, Decimal]) -> tuple[int, Decimal]:
            branch, excess = item
            is_parent_dc = 1 if parent_dc_id and branch.id == parent_dc_id else 0
            return (is_parent_dc, excess)

        candidates.sort(key=sort_key, reverse=True)
        return candidates

    @staticmethod
    def _greedy_allocate(
        needed: Decimal,
        candidates: list[tuple[Branch, Decimal]],
    ) -> list[tuple[Branch, Decimal]]:
        """Allocate ``needed`` quantity greedily from candidates with most excess first."""
        allocations: list[tuple[Branch, Decimal]] = []
        remaining = needed
        for branch, excess in candidates:
            if remaining <= 0:
                break
            take = min(excess, remaining)
            if take > 0:
                allocations.append((branch, take))
                remaining -= take
        return allocations
