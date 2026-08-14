"""Recommendation model and state machine."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import models
from django.utils import timezone

from apps.core.models import TenantAwareModel

from .enums import EscalationLevel, RecommendationState

if TYPE_CHECKING:
    from apps.accounts.models import User


class InvalidTransitionError(Exception):
    """Raised when a recommendation state transition is not allowed."""


class AlreadyDecidedError(InvalidTransitionError):
    """Raised when a recommendation in a terminal/decided state is modified illegally."""


class Recommendation(TenantAwareModel):
    """A replenishment recommendation for a part at a branch.

    Snapshot fields (current_stock, punto_pedido, planning_target, velocity,
    classification) are frozen at generation time so the recommendation remains
    traceable even if the underlying data changes later.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.CASCADE,
        related_name="recommendations",
    )
    part = models.ForeignKey(
        "catalog.Part",
        on_delete=models.CASCADE,
        related_name="recommendations",
    )
    state = models.CharField(
        max_length=20,
        choices=RecommendationState.choices,
        default=RecommendationState.PENDING,
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    source_type = models.CharField(
        max_length=20,
        default="external_supplier",
        help_text="Placeholder for WU-10 source resolution (transfer/supplier).",
    )
    source_branch = models.ForeignKey(
        "branches.Branch",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="source_for_recommendations",
    )
    is_partial = models.BooleanField(
        default=False,
        help_text="True when internal sources cannot cover the full recommended quantity.",
    )
    partial_gap = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        default=Decimal("0"),
        help_text="Quantity still needed after allocating all available internal excess stock.",
    )
    source_breakdown = models.JSONField(
        default=list,
        blank=True,
        help_text="Multi-source allocation: list of {source_type, source_branch, quantity}.",
    )
    current_stock = models.DecimalField(max_digits=12, decimal_places=2)
    punto_pedido = models.DecimalField(max_digits=12, decimal_places=2)
    planning_target = models.DecimalField(max_digits=12, decimal_places=2)
    explanation = models.TextField(blank=True)
    classification = models.CharField(max_length=100, blank=True)
    velocity = models.DecimalField(max_digits=12, decimal_places=2)
    assigned_approver = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_recommendations",
        help_text="Default approver (branch manager); escalation may reassign in WU-12.",
    )
    escalation_level = models.CharField(
        max_length=20,
        choices=EscalationLevel.choices,
        default=EscalationLevel.NONE,
        help_text="Current escalation level for this recommendation.",
    )
    escalation_reason = models.TextField(
        blank=True,
        help_text="Why this recommendation was escalated (threshold crossed, etc.).",
    )
    escalated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the recommendation was last escalated.",
    )
    escalated_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="escalated_recommendations",
        help_text="User who manually escalated the recommendation (system escalations leave this null).",
    )
    decided_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="decided_recommendations",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_notes = models.TextField(blank=True)
    run_date = models.DateField(
        default=date.today,
        db_index=True,
        help_text="Run date used for idempotency and rejection reopening rules.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "branch", "part"],
                condition=models.Q(state=RecommendationState.PENDING),
                name="unique_pending_recommendation_per_part",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "branch", "state"]),
            models.Index(fields=["state"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.branch.code} / {self.part.internal_sku_code} [{self.state}]"

    def is_pending(self) -> bool:
        return self.state == RecommendationState.PENDING

    def is_decided(self) -> bool:
        return self.state in (
            RecommendationState.APPROVED,
            RecommendationState.REJECTED,
            RecommendationState.HANDLED,
            RecommendationState.ORDERED,
        )

    def can_transition_to(self, new_state: str) -> bool:
        valid_transitions = {
            RecommendationState.PENDING: {
                RecommendationState.APPROVED,
                RecommendationState.REJECTED,
                RecommendationState.HANDLED,
            },
            RecommendationState.APPROVED: {
                RecommendationState.ORDERED,
                RecommendationState.HANDLED,
            },
            RecommendationState.REJECTED: {
                RecommendationState.PENDING,
            },
            RecommendationState.HANDLED: {
                RecommendationState.PENDING,
            },
            RecommendationState.ORDERED: set(),
        }
        return new_state in valid_transitions.get(self.state, set())

    def transition_to(self, new_state: str, user: "User", notes: str | None = None) -> "Recommendation":
        if not self.can_transition_to(new_state):
            raise InvalidTransitionError(
                f"Cannot transition from {self.state} to {new_state}"
            )

        self.state = new_state
        self.decided_by = user
        self.decided_at = timezone.now()
        self.decision_notes = notes or ""
        self.save()
        return self

    @property
    def coverage_days_after_fulfillment(self) -> Decimal:
        """Projected coverage after the recommended quantity is received.

        Uses the material-aligned approximation: coverage = (stock + quantity)
        / velocity * 30 days. Returns 0 when velocity is zero to avoid division
        by zero.
        """
        velocity = self.velocity
        if velocity <= 0:
            return Decimal("0")
        projected_stock = self.current_stock + self.quantity
        return Decimal(str(projected_stock / velocity * 30)).quantize(
            Decimal("0.01")
        )
