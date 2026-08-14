"""Recommendation generation service."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import UUID

import structlog
from django.db import transaction

from apps.branches.models import Branch, BranchType
from apps.catalog.classification import ClassificationEngine
from apps.catalog.models import ClassificationResult, LifecycleStage, Part
from apps.catalog.planning import PlanningCalculator
from apps.catalog.services import VelocityCalculator
from apps.core.models import Tenant

from .enums import RecommendationState
from .models import InvalidTransitionError, Recommendation

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)

# Lifecycle stages / subcodes that exclude a part from automatic replenishment.
_EXCLUDED_STAGES = {
    LifecycleStage.OBSOLETE,
    LifecycleStage.SPECIAL_NON_STOCK,
}


def _to_decimal(value: float) -> Decimal:
    return Decimal(str(value))


class RecommendationGenerator:
    """Generates replenishment recommendations for a tenant.

    The generator is intentionally conservative for WU-09:

    - Source resolution is deferred to WU-10; every recommendation uses the
      ``external_supplier`` placeholder for ``source_type``.
    - Cold-start SKUs and SKUs classified as OBS-R or NS-NS are skipped.
    - Only one pending recommendation per (branch, part) is allowed.
    """

    def __init__(self, tenant: Tenant):
        self.tenant = tenant
        self.velocity_calculator = VelocityCalculator(tenant)
        self.classification_engine = ClassificationEngine(tenant)
        self.planning_calculator = PlanningCalculator(tenant)

    def generate_for_branch(self, branch: Branch) -> list[Recommendation]:
        """Generate recommendations for all active parts in a branch."""
        parts = Part.objects.filter(tenant=self.tenant, is_active=True).order_by("id")
        recommendations: list[Recommendation] = []

        for part in parts.iterator():
            rec = self._maybe_generate_for_part(part, branch)
            if rec is not None:
                recommendations.append(rec)

        logger.info(
            "recommendation.generation.branch_done",
            branch=branch.code,
            count=len(recommendations),
        )
        return recommendations

    def generate_for_tenant(self) -> dict[UUID, list[Recommendation]]:
        """Generate recommendations for every active branch in the tenant."""
        branches = Branch.objects.filter(
            tenant=self.tenant, is_active=True
        ).order_by("code")
        results: dict[UUID, list[Recommendation]] = {}
        for branch in branches.iterator():
            results[branch.id] = self.generate_for_branch(branch)
        return results

    def generate_for_dc(self, distribution_center: Branch) -> list[Recommendation]:
        """Generate recommendations for a distribution center.

        The DC's planning velocity is its own historical sales rate plus the
        sum of the historical sales rates of all dependent branches.
        """
        if distribution_center.type != BranchType.CENTRO_DISTRIBUCION:
            raise ValueError(
                f"Branch {distribution_center.code} is not a distribution center"
            )

        dependent_branches = list(
            distribution_center.dependent_branches.filter(
                tenant=self.tenant, is_active=True
            )
        )

        parts = Part.objects.filter(tenant=self.tenant, is_active=True).order_by("id")
        recommendations: list[Recommendation] = []

        for part in parts.iterator():
            own_velocity = self.velocity_calculator.calculate_for_part(
                part, distribution_center
            ).velocity
            dependent_velocity = sum(
                self.velocity_calculator.calculate_for_part(part, dep).velocity
                for dep in dependent_branches
            )
            total_velocity = own_velocity + dependent_velocity

            rec = self._maybe_generate_with_velocity(
                part, distribution_center, total_velocity
            )
            if rec is not None:
                recommendations.append(rec)

        return recommendations

    def recalculate_recommendation(
        self, recommendation: Recommendation
    ) -> Recommendation | None:
        """Refresh an existing pending recommendation with current data.

        If the part no longer triggers a recommendation, the pending row is
        removed so stale alerts do not accumulate.
        """
        if recommendation.state != RecommendationState.PENDING:
            raise InvalidTransitionError(
                "Only pending recommendations can be recalculated"
            )

        branch = recommendation.branch
        part = recommendation.part

        if branch.type == BranchType.CENTRO_DISTRIBUCION:
            velocity = self._dc_velocity_for_part(part, branch)
        else:
            velocity = self.velocity_calculator.calculate_for_part(part, branch).velocity

        if velocity <= 0:
            recommendation.delete()
            return None

        classification = self.classification_engine.classify_part(part, branch)
        if self._should_skip_part(classification):
            recommendation.delete()
            return None

        planning_result = self.planning_calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=velocity,
        )

        if not planning_result.triggered or planning_result.cantidad_pedido <= 0:
            recommendation.delete()
            return None

        classification_label = self._classification_label(classification)
        recommendation.quantity = _to_decimal(planning_result.cantidad_pedido)
        recommendation.current_stock = _to_decimal(planning_result.stock_disponible)
        recommendation.punto_pedido = _to_decimal(planning_result.punto_pedido)
        recommendation.planning_target = _to_decimal(planning_result.planning_target)
        recommendation.velocity = _to_decimal(velocity)
        recommendation.classification = classification_label
        recommendation.explanation = (
            f"Stock {planning_result.stock_disponible:.1f} ≤ PP "
            f"{planning_result.punto_pedido:.1f}. "
            f"Recommended {planning_result.cantidad_pedido:.1f} units. "
            f"Class: {classification_label}."
        )
        recommendation.save()
        return recommendation

    def _dc_velocity_for_part(self, part: Part, distribution_center: Branch) -> float:
        """Return the aggregate DC velocity for a single part."""
        dependent_branches = list(
            distribution_center.dependent_branches.filter(
                tenant=self.tenant, is_active=True
            )
        )
        own_velocity = self.velocity_calculator.calculate_for_part(
            part, distribution_center
        ).velocity
        dependent_velocity = sum(
            self.velocity_calculator.calculate_for_part(part, dep).velocity
            for dep in dependent_branches
        )
        return own_velocity + dependent_velocity

    def _should_skip_part(self, classification: ClassificationResult) -> bool:
        """Return True for parts excluded from automatic recommendations."""
        if classification.lifecycle_stage in _EXCLUDED_STAGES:
            return True
        return False

    @staticmethod
    def _classification_label(classification: ClassificationResult) -> str:
        return (
            f"{classification.volume_class or 'N/A'} "
            f"{classification.lifecycle_subcode or classification.lifecycle_stage}"
        ).strip()

    def _maybe_generate_for_part(
        self, part: Part, branch: Branch
    ) -> Optional[Recommendation]:
        """Generate a recommendation for a single part if triggered."""
        existing = Recommendation.objects.filter(
            tenant=self.tenant,
            branch=branch,
            part=part,
            state=RecommendationState.PENDING,
        ).first()
        if existing:
            return None

        velocity_result = self.velocity_calculator.calculate_for_part(part, branch)
        if velocity_result.is_cold_start:
            logger.info(
                "recommendation.skipped.cold_start",
                branch=branch.code,
                part=part.internal_sku_code,
            )
            return None

        classification = self.classification_engine.classify_part(part, branch)
        if self._should_skip_part(classification):
            logger.info(
                "recommendation.skipped.lifecycle",
                branch=branch.code,
                part=part.internal_sku_code,
                lifecycle_stage=classification.lifecycle_stage,
                lifecycle_subcode=classification.lifecycle_subcode,
            )
            return None

        planning_result = self.planning_calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=velocity_result.velocity,
        )

        if not planning_result.triggered or planning_result.cantidad_pedido <= 0:
            return None

        return self._create_recommendation(
            branch=branch,
            part=part,
            planning_result=planning_result,
            classification=classification,
            velocity=velocity_result.velocity,
        )

    def _maybe_generate_with_velocity(
        self,
        part: Part,
        branch: Branch,
        velocity: float,
    ) -> Optional[Recommendation]:
        """Generate a recommendation using a pre-computed velocity."""
        existing = Recommendation.objects.filter(
            tenant=self.tenant,
            branch=branch,
            part=part,
            state=RecommendationState.PENDING,
        ).first()
        if existing:
            return None

        if velocity <= 0:
            logger.info(
                "recommendation.skipped.cold_start",
                branch=branch.code,
                part=part.internal_sku_code,
            )
            return None

        classification = self.classification_engine.classify_part(part, branch)
        if self._should_skip_part(classification):
            logger.info(
                "recommendation.skipped.lifecycle",
                branch=branch.code,
                part=part.internal_sku_code,
                lifecycle_stage=classification.lifecycle_stage,
                lifecycle_subcode=classification.lifecycle_subcode,
            )
            return None

        planning_result = self.planning_calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=velocity,
        )

        if not planning_result.triggered or planning_result.cantidad_pedido <= 0:
            return None

        return self._create_recommendation(
            branch=branch,
            part=part,
            planning_result=planning_result,
            classification=classification,
            velocity=velocity,
        )

    @transaction.atomic
    def _create_recommendation(
        self,
        branch: Branch,
        part: Part,
        planning_result,
        classification: ClassificationResult,
        velocity: float,
    ) -> Recommendation:
        """Persist a new recommendation for a triggered part."""
        # Defensive duplicate check inside the transaction. The partial unique
        # index is the authoritative guard, but this raises a clearer error.
        if (
            Recommendation.objects.filter(
                tenant=self.tenant,
                branch=branch,
                part=part,
                state=RecommendationState.PENDING,
            )
            .select_for_update()
            .exists()
        ):
            raise Recommendation.DoesNotExist("Pending recommendation already exists")

        classification_label = self._classification_label(classification)

        explanation = (
            f"Stock {planning_result.stock_disponible:.1f} ≤ PP "
            f"{planning_result.punto_pedido:.1f}. "
            f"Recommended {planning_result.cantidad_pedido:.1f} units. "
            f"Class: {classification_label}."
        )

        rec = Recommendation.objects.create(
            tenant=self.tenant,
            branch=branch,
            part=part,
            state=RecommendationState.PENDING,
            quantity=_to_decimal(planning_result.cantidad_pedido),
            source_type="external_supplier",
            source_branch=None,
            current_stock=_to_decimal(planning_result.stock_disponible),
            punto_pedido=_to_decimal(planning_result.punto_pedido),
            planning_target=_to_decimal(planning_result.planning_target),
            explanation=explanation,
            classification=classification_label,
            velocity=_to_decimal(velocity),
        )

        logger.info(
            "recommendation.created",
            branch=branch.code,
            part=part.internal_sku_code,
            quantity=str(rec.quantity),
            pp=str(rec.punto_pedido),
        )
        return rec
