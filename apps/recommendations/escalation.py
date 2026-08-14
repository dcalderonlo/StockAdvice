"""Escalation service for recommendations.

Threshold-based escalation moves recommendations from branch manager to
coordinator, and from coordinator to gerente when thresholds remain exceeded.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import structlog
from django.utils import timezone

from apps.core.models import AuditLog, Tenant

from .enums import EscalationLevel
from .models import Recommendation

if TYPE_CHECKING:
    from apps.accounts.models import User

logger = structlog.get_logger(__name__)

DEFAULT_THRESHOLDS = {
    "value_threshold": Decimal("10000.00"),
    "volume_threshold": Decimal("100.00"),
    "impact_threshold": Decimal("1.00"),
}


def get_escalation_thresholds(tenant: Tenant) -> dict[str, Decimal]:
    """Return escalation thresholds from tenant config, with defaults."""
    config = tenant.config or {}
    escalation = config.get("escalation", {}) if isinstance(config, dict) else {}
    return {
        key: Decimal(str(escalation.get(key, default)))
        for key, default in DEFAULT_THRESHOLDS.items()
    }


class EscalationService:
    """Checks recommendations against tenant thresholds and escalates as needed."""

    def __init__(self, tenant: Tenant):
        self.tenant = tenant

    def _compute_recommendation_value(self, recommendation: Recommendation) -> Decimal:
        """Estimate the monetary value of the recommendation.

        For v1 we use quantity as a proxy because pricing data is not yet
        available. When unit cost is introduced, this should become
        ``quantity * unit_cost``.
        """
        return Decimal(str(recommendation.quantity))

    def _exceeds_thresholds(
        self, recommendation: Recommendation, thresholds: dict[str, Decimal]
    ) -> tuple[bool, str]:
        """Return (exceeded, reason) when any threshold is crossed."""
        value = self._compute_recommendation_value(recommendation)
        volume = Decimal(str(recommendation.quantity))

        if value > thresholds["value_threshold"]:
            return True, (
                f"Value {value} exceeds threshold "
                f"{thresholds['value_threshold']}"
            )
        if volume > thresholds["volume_threshold"]:
            return True, (
                f"Volume {volume} exceeds threshold "
                f"{thresholds['volume_threshold']}"
            )
        # Impact threshold is a placeholder until WU-13+ introduces an
        # explicit impact score; skip for now.
        return False, ""

    def check_and_escalate(
        self, recommendation: Recommendation
    ) -> Recommendation:
        """Compare recommendation against thresholds and escalate if needed."""
        thresholds = get_escalation_thresholds(self.tenant)
        exceeded, reason = self._exceeds_thresholds(recommendation, thresholds)

        if not exceeded:
            return recommendation

        if recommendation.escalation_level == EscalationLevel.NONE:
            return self._escalate_to_level(
                recommendation, EscalationLevel.COORDINATOR, reason
            )
        if recommendation.escalation_level == EscalationLevel.COORDINATOR:
            return self._escalate_to_level(
                recommendation, EscalationLevel.GERENTE, reason
            )

        # Gerente is the highest level; no further escalation.
        return recommendation

    def escalate_to_coordinator(
        self, recommendation: Recommendation, reason: str, user: User | None = None
    ) -> Recommendation:
        """Manually escalate a recommendation to the coordinator level."""
        if user is not None:
            recommendation.escalated_by = user
        return self._escalate_to_level(
            recommendation, EscalationLevel.COORDINATOR, reason
        )

    def escalate_to_gerente(
        self, recommendation: Recommendation, reason: str, user: User | None = None
    ) -> Recommendation:
        """Manually escalate a recommendation to the gerente level."""
        if user is not None:
            recommendation.escalated_by = user
        return self._escalate_to_level(
            recommendation, EscalationLevel.GERENTE, reason
        )

    def _escalate_to_level(
        self,
        recommendation: Recommendation,
        level: str,
        reason: str,
    ) -> Recommendation:
        """Persist the escalation and create an audit log entry."""
        previous_level = recommendation.escalation_level
        recommendation.escalation_level = level
        recommendation.escalation_reason = reason
        recommendation.escalated_at = timezone.now()
        recommendation.save()

        AuditLog.objects.create(
            tenant=self.tenant,
            user=recommendation.escalated_by,
            role_used=None,
            action=f"escalate_to_{level}",
            entity_type="recommendation",
            entity_id=recommendation.id,
            metadata={
                "previous_level": previous_level,
                "new_level": level,
                "reason": reason,
            },
        )

        logger.info(
            "recommendation.escalated",
            recommendation_id=str(recommendation.id),
            from_level=previous_level,
            to_level=level,
            reason=reason,
        )
        return recommendation
