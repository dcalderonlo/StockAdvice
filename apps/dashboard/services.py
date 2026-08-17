"""Dashboard aggregator: aggregates data for role-scoped dashboard views."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from django.db import models

from apps.accounts.models import User
from apps.branches.models import Branch
from apps.catalog.models import Part
from apps.core.models import Tenant
from apps.inventory.models import StockLevel
from apps.recommendations.models import Recommendation, RecommendationState


class DashboardAggregator:
    """Aggregates data for the branch manager dashboard.

    Use:
        aggregator = DashboardAggregator(tenant, branch=branch)
        overview = aggregator.get_overview()
    """

    def __init__(self, tenant: Tenant, branch: Optional[Branch] = None):
        self.tenant = tenant
        self.branch = branch  # None means tenant-wide

    def get_kpi_tiles(self) -> dict:
        """Return KPI tiles for the dashboard."""
        if self.branch:
            return self._get_branch_kpis(self.branch)
        return self._get_tenant_kpis()

    def _get_branch_kpis(self, branch: Branch) -> dict:
        pending_recs = Recommendation.objects.filter(
            tenant=self.tenant,
            branch=branch,
            state=RecommendationState.PENDING,
        ).count()

        stock_qs = StockLevel.objects.filter(tenant=self.tenant, branch=branch)
        total_stock = stock_qs.aggregate(
            total=models.Sum("stock_disponible")
        )["total"] or Decimal("0")

        active_parts = stock_qs.exclude(stock_disponible=0).count()

        return {
            "branch_code": branch.code,
            "branch_name": branch.name,
            "pending_recommendations": pending_recs,
            "total_stock_units": float(total_stock),
            "active_parts": active_parts,
            "triggered_parts": 0,  # populated by get_stock_health
        }

    def _get_tenant_kpis(self) -> dict:
        return {
            "total_branches": Branch.objects.filter(
                tenant=self.tenant, is_active=True
            ).count(),
            "total_recommendations_pending": Recommendation.objects.filter(
                tenant=self.tenant, state=RecommendationState.PENDING,
            ).count(),
            "total_recommendations_approved": Recommendation.objects.filter(
                tenant=self.tenant, state=RecommendationState.APPROVED,
            ).count(),
            "total_recommendations_partial": Recommendation.objects.filter(
                tenant=self.tenant,
                state=RecommendationState.PENDING,
                is_partial=True,
            ).count(),
        }

    def get_pending_recommendations(self) -> list[Recommendation]:
        """Return pending recommendations (limit 50)."""
        qs = Recommendation.objects.filter(
            tenant=self.tenant, state=RecommendationState.PENDING,
        ).select_related("branch", "part").order_by("-created_at")
        if self.branch:
            qs = qs.filter(branch=self.branch)
        return list(qs[:50])

    def get_stock_health(self) -> list[dict]:
        """Return stock health per part: stock vs PP, flagged if low.

        Uses PlanningCalculator from WU-08. Limit 50 parts.
        """
        from apps.catalog.planning import PlanningCalculator
        from apps.catalog.services import VelocityCalculator

        planning = PlanningCalculator(self.tenant)
        velocity = VelocityCalculator(self.tenant)

        stock_qs = StockLevel.objects.filter(tenant=self.tenant)
        if self.branch:
            stock_qs = stock_qs.filter(branch=self.branch)
        stock_qs = stock_qs.select_related("part", "branch")[:50]

        results = []
        for sl in stock_qs:
            v = velocity.calculate_for_part(sl.part, sl.branch).velocity
            p = planning.calculate_for_part(
                part=sl.part, branch=sl.branch, velocity=v
            )
            results.append({
                "part_code": sl.part.internal_sku_code,
                "part_description": sl.part.description,
                "branch_code": sl.branch.code,
                "stock_disponible": float(sl.stock_disponible),
                "stock_en_transito": float(sl.stock_en_transito),
                "punto_pedido": float(p.punto_pedido),
                "planning_target": float(p.planning_target),
                "cantidad_pedido": float(p.cantidad_pedido),
                "triggered": p.triggered,
            })
        return results

    def get_overview(self) -> dict:
        """Combined overview: KPIs + pending list + stock health."""
        kpis = self.get_kpi_tiles()
        # Auto-populate triggered_parts from stock_health
        if self.branch:
            stock_health = self.get_stock_health()
            kpis["triggered_parts"] = sum(1 for s in stock_health if s["triggered"])
        return {
            "kpis": kpis,
            "pending_recommendations": [
                {
                    "id": str(r.id),
                    "part_code": r.part.internal_sku_code,
                    "part_description": r.part.description,
                    "branch_code": r.branch.code,
                    "quantity": float(r.quantity),
                    "created_at": r.created_at.isoformat(),
                    "is_partial": r.is_partial,
                    "source_type": r.source_type,
                }
                for r in self.get_pending_recommendations()
            ],
            "stock_health": self.get_stock_health(),
        }
