"""Recommendation generation service."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import UUID

import structlog
from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.accounts.models import Role, User
from apps.branches.models import Branch, BranchType
from apps.catalog.classification import ClassificationEngine
from apps.catalog.models import ClassificationResult, LifecycleStage, Part
from apps.catalog.planning import PlanningCalculator
from apps.catalog.services import VelocityCalculator
from apps.core.models import AuditLog, Tenant

from .enums import RecommendationState
from .escalation import EscalationService
from .models import InvalidTransitionError, Recommendation
from .permissions import assert_can_approve, get_active_role, is_cross_coordinator
from .source_resolution import SourceResolutionService
from .transitions import transition_recommendation

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
        self.source_resolution = SourceResolutionService(tenant)
        self.escalation_service = EscalationService(tenant)

    def generate_for_branch(
        self, branch: Branch, run_date: date | None = None
    ) -> list[Recommendation]:
        """Generate recommendations for all active parts in a branch."""
        run_date = run_date or date.today()
        parts = Part.objects.filter(tenant=self.tenant, is_active=True).order_by("id")
        recommendations: list[Recommendation] = []

        for part in parts.iterator():
            rec = self._maybe_generate_for_part(part, branch, run_date)
            if rec is not None:
                recommendations.append(rec)

        logger.info(
            "recommendation.generation.branch_done",
            branch=branch.code,
            count=len(recommendations),
            run_date=run_date.isoformat(),
        )
        return recommendations

    def generate_for_tenant(
        self, run_date: date | None = None
    ) -> dict[UUID, list[Recommendation]]:
        """Generate recommendations for every active branch in the tenant."""
        run_date = run_date or date.today()
        branches = Branch.objects.filter(
            tenant=self.tenant, is_active=True
        ).order_by("code")
        results: dict[UUID, list[Recommendation]] = {}
        for branch in branches.iterator():
            results[branch.id] = self.generate_for_branch(branch, run_date=run_date)
        return results

    def generate_for_dc(
        self, distribution_center: Branch, run_date: date | None = None
    ) -> list[Recommendation]:
        """Generate recommendations for a distribution center.

        The DC's planning velocity is its own historical sales rate plus the
        sum of the historical sales rates of all dependent branches.
        """
        if distribution_center.type != BranchType.CENTRO_DISTRIBUCION:
            raise ValueError(
                f"Branch {distribution_center.code} is not a distribution center"
            )

        run_date = run_date or date.today()
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
                part, distribution_center, total_velocity, run_date
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
        self.source_resolution.resolve_sources(recommendation)
        self.escalation_service.check_and_escalate(recommendation)
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
        self,
        part: Part,
        branch: Branch,
        run_date: date,
    ) -> Optional[Recommendation]:
        """Generate a recommendation for a single part if triggered."""
        if self._recommendation_exists_for_run(branch, part, run_date):
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
            run_date=run_date,
        )

    def _maybe_generate_with_velocity(
        self,
        part: Part,
        branch: Branch,
        velocity: float,
        run_date: date,
    ) -> Optional[Recommendation]:
        """Generate a recommendation using a pre-computed velocity."""
        if self._recommendation_exists_for_run(branch, part, run_date):
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
            run_date=run_date,
        )

    def _recommendation_exists_for_run(
        self, branch: Branch, part: Part, run_date: date
    ) -> bool:
        """Return True when any recommendation exists for this part/run.

        Prevents duplicate or re-opened recommendations within the same run,
        including rejected recommendations that must stay closed until the
        next run.
        """
        return Recommendation.objects.filter(
            tenant=self.tenant,
            branch=branch,
            part=part,
            run_date=run_date,
        ).exists()

    @transaction.atomic
    def _create_recommendation(
        self,
        branch: Branch,
        part: Part,
        planning_result,
        classification: ClassificationResult,
        velocity: float,
        run_date: date,
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
            assigned_approver=branch.manager,
            run_date=run_date,
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

        self.source_resolution.resolve_sources(rec)
        self.escalation_service.check_and_escalate(rec)

        from apps.notifications.triggers import notify_new_recommendation

        notify_new_recommendation(rec)

        logger.info(
            "recommendation.created",
            branch=branch.code,
            part=part.internal_sku_code,
            quantity=str(rec.quantity),
            pp=str(rec.punto_pedido),
            source_type=rec.source_type,
            is_partial=rec.is_partial,
            escalation_level=rec.escalation_level,
        )
        return rec


class ApprovalService:
    """User-facing approval actions for recommendations.

    Each action validates permissions, delegates the state transition to the
    existing ``transition_recommendation`` helper from WU-09, and records an
    immutable ``AuditLog`` entry.
    """

    _ACTION_TO_STATE = {
        "approve": RecommendationState.APPROVED,
        "reject": RecommendationState.REJECTED,
        "handle": RecommendationState.HANDLED,
        "mark_ordered": RecommendationState.ORDERED,
    }

    def __init__(self, tenant: Tenant):
        self.tenant = tenant

    def _role_for_log(self, role_name: str | None) -> Role | None:
        if role_name is None:
            return None
        try:
            return Role.objects.get(name=role_name)
        except Role.DoesNotExist:
            return None

    @transaction.atomic
    def _transition_and_log(
        self,
        recommendation: Recommendation,
        user: User,
        action: str,
        target_state: str,
        notes: str | None = None,
    ) -> Recommendation:
        assert_can_approve(user, recommendation)
        role_used_name = get_active_role(user, self.tenant)
        before_state = recommendation.state

        rec = transition_recommendation(recommendation, target_state, user, notes)

        from apps.notifications.triggers import notify_decided

        decision_map = {
            "approve": "approved",
            "reject": "rejected",
            "handle": "handled",
            "mark_ordered": "ordered",
        }
        notify_decided(rec, user, decision_map[action])

        AuditLog.objects.create(
            tenant=self.tenant,
            user=user,
            role_used=self._role_for_log(role_used_name),
            action=action,
            entity_type="recommendation",
            entity_id=rec.id,
            metadata={
                "before_state": before_state,
                "after_state": rec.state,
                "notes": notes or "",
            },
        )

        logger.info(
            f"recommendation.{action}",
            recommendation_id=str(rec.id),
            user_id=str(user.id),
            role_used=role_used_name,
            before_state=before_state,
            after_state=rec.state,
        )
        return rec

    def _is_cross_coordinator(self, recommendation: Recommendation) -> bool:
        """Return True when the recommendation crosses coordinator boundaries."""
        return is_cross_coordinator(recommendation)

    def approve_cross_coordinator_transfer(
        self, recommendation: Recommendation, user: User, notes: str | None = None
    ) -> Recommendation:
        """Approve a transfer that crosses coordinator scopes.

        Only a gerente may approve cross-coordinator transfers. Both source
        and destination coordinators are notified via the audit log.
        """
        if Role.GERENTE not in user.get_role_names():
            raise PermissionDenied(
                "Cross-coordinator transfers require gerente approval."
            )
        rec = self.approve_recommendation(recommendation, user, notes)
        role_used_name = get_active_role(user, self.tenant)
        AuditLog.objects.create(
            tenant=self.tenant,
            user=user,
            role_used=self._role_for_log(role_used_name),
            action="cross_coordinator_notified",
            entity_type="recommendation",
            entity_id=rec.id,
            metadata={
                "source_branch_id": str(recommendation.source_branch_id),
                "destination_branch_id": str(recommendation.branch_id),
                "source_coordinator_id": (
                    str(recommendation.source_branch.coordinator_id)
                    if recommendation.source_branch
                    else None
                ),
                "destination_coordinator_id": str(recommendation.branch.coordinator_id),
            },
        )
        logger.info(
            "recommendation.cross_coordinator_approved",
            recommendation_id=str(rec.id),
            user_id=str(user.id),
            source_branch_id=str(recommendation.source_branch_id),
            destination_branch_id=str(recommendation.branch_id),
        )
        return rec

    def approve_recommendation(
        self, recommendation: Recommendation, user: User, notes: str | None = None
    ) -> Recommendation:
        assert_can_approve(user, recommendation)
        if self._is_cross_coordinator(recommendation):
            if Role.GERENTE not in user.get_role_names():
                raise PermissionDenied(
                    "Cross-coordinator transfers require gerente approval."
                )
        return self._transition_and_log(
            recommendation, user, "approve", RecommendationState.APPROVED, notes
        )

    def reject_recommendation(
        self, recommendation: Recommendation, user: User, notes: str | None = None
    ) -> Recommendation:
        return self._transition_and_log(
            recommendation, user, "reject", RecommendationState.REJECTED, notes
        )

    def mark_handled(
        self, recommendation: Recommendation, user: User, notes: str | None = None
    ) -> Recommendation:
        return self._transition_and_log(
            recommendation, user, "handle", RecommendationState.HANDLED, notes
        )

    def mark_ordered(
        self, recommendation: Recommendation, user: User, notes: str | None = None
    ) -> Recommendation:
        return self._transition_and_log(
            recommendation, user, "mark_ordered", RecommendationState.ORDERED, notes
        )

    @transaction.atomic
    def approve_bulk(
        self, recommendations: list[Recommendation], user: User, notes: str | None = None
    ) -> list[Recommendation]:
        return self._bulk_transition(
            recommendations, user, self.approve_recommendation, "approve", notes
        )

    @transaction.atomic
    def reject_bulk(
        self, recommendations: list[Recommendation], user: User, notes: str | None = None
    ) -> list[Recommendation]:
        return self._bulk_transition(
            recommendations, user, self.reject_recommendation, "reject", notes
        )

    @transaction.atomic
    def handle_bulk(
        self, recommendations: list[Recommendation], user: User, notes: str | None = None
    ) -> list[Recommendation]:
        return self._bulk_transition(
            recommendations, user, self.mark_handled, "handle", notes
        )

    def _bulk_transition(
        self,
        recommendations: list[Recommendation],
        user: User,
        transition_fn,
        action: str,
        notes: str | None = None,
    ) -> list[Recommendation]:
        updated: list[Recommendation] = []
        for rec in recommendations:
            if rec.state != RecommendationState.PENDING:
                logger.warning(
                    "recommendation.bulk.skip",
                    recommendation_id=str(rec.id),
                    state=rec.state,
                    action=action,
                )
                continue
            try:
                updated_rec = transition_fn(rec, user, notes)
                updated.append(updated_rec)
            except PermissionDenied:
                logger.warning(
                    "recommendation.bulk.permission_denied",
                    recommendation_id=str(rec.id),
                    action=action,
                )
                continue
        return updated
