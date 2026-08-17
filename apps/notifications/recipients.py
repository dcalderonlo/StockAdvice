"""Recipient resolution and notification rendering for recommendation events."""

from __future__ import annotations

from apps.accounts.models import Role, User
from apps.recommendations.models import Recommendation


SUBJECT_TEMPLATES = {
    "new_recommendation": "New replenishment recommendation for {part_code}",
    "escalated_to_coordinator": "Recommendation escalated to coordinator ({part_code})",
    "escalated_to_gerente": "Cross-coordinator recommendation requires gerente approval ({part_code})",
    "approved": "Recommendation approved ({part_code})",
    "rejected": "Recommendation rejected ({part_code})",
    "partial_fulfillment": "Partial fulfillment: {gap} units still needed ({part_code})",
    "cross_coordinator_pending": "Cross-coordinator transfer pending gerente approval ({part_code})",
    "override_created": "Demand override created for {part_code}",
    "override_expired": "Demand override expired for {part_code}",
}


def _gerentes_for_tenant(tenant) -> list[User]:
    """Return all users with the gerente role for the given tenant."""
    return list(
        User.objects.filter(
            tenant=tenant,
            user_roles__role__name=Role.GERENTE,
        )
        .distinct()
        .order_by("email")
    )


def get_recipients_for_recommendation(
    recommendation: Recommendation, event_type: str
) -> list[User]:
    """Resolve the list of User recipients for a recommendation event."""
    tenant = recommendation.tenant
    branch = recommendation.branch
    recipients: list[User] = []

    if event_type in (
        "new_recommendation",
        "partial_fulfillment",
        "cross_coordinator_pending",
    ):
        if branch.manager_id:
            recipients.append(branch.manager)
        if branch.coordinator_id:
            recipients.append(branch.coordinator)
        if event_type in ("partial_fulfillment", "cross_coordinator_pending"):
            recipients.extend(_gerentes_for_tenant(tenant))
        return list(set(recipients))

    if event_type == "escalated_to_coordinator":
        return [branch.coordinator] if branch.coordinator_id else []

    if event_type == "escalated_to_gerente":
        return _gerentes_for_tenant(tenant)

    if event_type in ("approved", "rejected"):
        return [recommendation.decided_by] if recommendation.decided_by else []

    return []


def render_notification_body(recommendation: Recommendation, event_type: str) -> str:
    """Render a human-readable body for the notification."""
    part = recommendation.part
    branch = recommendation.branch
    part_code = part.internal_sku_code
    return (
        f"Event: {event_type}\n"
        f"Part: {part_code} ({part.description})\n"
        f"Branch: {branch.code} ({branch.name})\n"
        f"Quantity: {recommendation.quantity}\n"
        f"State: {recommendation.state}\n"
        f"See: /recommendations/{recommendation.id}/"
    )
