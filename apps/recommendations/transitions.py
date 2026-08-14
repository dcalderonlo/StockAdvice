"""Atomic state transitions for recommendations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from .enums import RecommendationState
from .models import AlreadyDecidedError, InvalidTransitionError, Recommendation

if TYPE_CHECKING:
    from apps.accounts.models import User


@transaction.atomic
def transition_recommendation(
    recommendation: Recommendation,
    new_state: str,
    user: "User",
    notes: str | None = None,
) -> Recommendation:
    """Atomically transition a recommendation to a new state.

    Args:
        recommendation: The recommendation to update.
        new_state: Target state from ``RecommendationState``.
        user: The user performing the transition.
        notes: Optional free-text decision notes.

    Returns:
        The updated recommendation instance.

    Raises:
        InvalidTransitionError: If the transition is not allowed.
        AlreadyDecidedError: If the recommendation is in a terminal/decided
            state and the requested transition is not permitted.
    """
    # Lock the row to avoid concurrent state mutations.
    locked = (
        Recommendation.objects.select_for_update()
        .filter(pk=recommendation.pk)
        .first()
    )
    if locked is None:
        raise Recommendation.DoesNotExist(
            f"Recommendation {recommendation.pk} no longer exists"
        )

    if not locked.can_transition_to(new_state):
        if locked.state == RecommendationState.ORDERED:
            raise AlreadyDecidedError(
                "Ordered recommendations are terminal and cannot be changed"
            )
        if (
            locked.state == RecommendationState.APPROVED
            and new_state == RecommendationState.PENDING
        ):
            raise AlreadyDecidedError(
                "Approved recommendations cannot return to pending; "
                "reject or handle first"
            )
        raise InvalidTransitionError(
            f"Cannot transition from {locked.state} to {new_state}"
        )

    locked.transition_to(new_state, user, notes=notes)
    return locked
