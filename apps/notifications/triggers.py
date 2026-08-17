"""Event triggers that fire notifications for recommendation lifecycle events."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from apps.accounts.models import Role, User
from apps.catalog.models import DemandOverride
from apps.recommendations.models import Recommendation

from .enums import NotificationType
from .recipients import (
    SUBJECT_TEMPLATES,
    get_recipients_for_recommendation,
    render_notification_body,
)
from .services import NotificationService

if TYPE_CHECKING:
    from apps.core.models import Tenant

logger = structlog.get_logger(__name__)


def _gerentes_for_tenant(tenant: "Tenant") -> list[User]:
    """Return all users with the gerente role for the given tenant."""
    return list(
        User.objects.filter(
            tenant=tenant,
            user_roles__role__name=Role.GERENTE,
        )
        .distinct()
        .order_by("email")
    )


def notify_new_recommendation(recommendation: Recommendation) -> None:
    """Trigger when a new recommendation is created."""
    service = NotificationService(recommendation.tenant)
    recipients = get_recipients_for_recommendation(recommendation, "new_recommendation")

    subject_template = SUBJECT_TEMPLATES["new_recommendation"]
    subject = subject_template.format(part_code=recommendation.part.internal_sku_code)
    body = render_notification_body(recommendation, "new_recommendation")

    for recipient in recipients:
        service.send_notification(
            user=recipient,
            notification_type=NotificationType.NEW_RECOMMENDATION,
            subject=subject,
            body=body,
            related_object_type="recommendation",
            related_object_id=recommendation.id,
        )

    logger.info(
        "trigger.new_recommendation",
        recommendation_id=str(recommendation.id),
        recipients=len(recipients),
    )


def notify_escalated(
    recommendation: Recommendation, previous_level: str, new_level: str
) -> None:
    """Trigger when a recommendation is escalated."""
    event_type = (
        "escalated_to_coordinator"
        if new_level == "coordinator"
        else "escalated_to_gerente"
    )

    service = NotificationService(recommendation.tenant)
    recipients = get_recipients_for_recommendation(recommendation, event_type)

    subject_template = SUBJECT_TEMPLATES[event_type]
    subject = subject_template.format(part_code=recommendation.part.internal_sku_code)
    body = render_notification_body(recommendation, event_type)
    body += f"\nPrevious level: {previous_level}\nNew level: {new_level}"

    for recipient in recipients:
        service.send_notification(
            user=recipient,
            notification_type=NotificationType.RECOMMENDATION_ESCALATED,
            subject=subject,
            body=body,
            related_object_type="recommendation",
            related_object_id=recommendation.id,
        )

    logger.info(
        "trigger.escalated",
        recommendation_id=str(recommendation.id),
        new_level=new_level,
        recipients=len(recipients),
    )


def notify_decided(recommendation: Recommendation, user: User, decision: str) -> None:
    """Trigger when a recommendation is approved/rejected/handled/ordered."""
    if decision not in ("approved", "rejected", "handled", "ordered"):
        return

    event_type = "rejected" if decision == "rejected" else "approved"
    notification_type = (
        NotificationType.RECOMMENDATION_REJECTED
        if decision == "rejected"
        else NotificationType.RECOMMENDATION_APPROVED
    )

    service = NotificationService(recommendation.tenant)
    recipients = get_recipients_for_recommendation(recommendation, event_type)

    subject_template = SUBJECT_TEMPLATES.get(event_type, SUBJECT_TEMPLATES["approved"])
    subject = subject_template.format(part_code=recommendation.part.internal_sku_code)
    body = render_notification_body(recommendation, event_type)
    body += f"\nDecided by: {user.email}\nDecision: {decision}"

    for recipient in recipients:
        service.send_notification(
            user=recipient,
            notification_type=notification_type,
            subject=subject,
            body=body,
            related_object_type="recommendation",
            related_object_id=recommendation.id,
        )

    logger.info(
        "trigger.decided",
        recommendation_id=str(recommendation.id),
        decision=decision,
        recipients=len(recipients),
    )


def notify_partial_fulfillment(recommendation: Recommendation) -> None:
    """Trigger when source resolution detects partial fulfillment."""
    service = NotificationService(recommendation.tenant)
    recipients = get_recipients_for_recommendation(recommendation, "partial_fulfillment")

    subject_template = SUBJECT_TEMPLATES["partial_fulfillment"]
    subject = subject_template.format(
        part_code=recommendation.part.internal_sku_code,
        gap=recommendation.partial_gap,
    )
    body = render_notification_body(recommendation, "partial_fulfillment")
    body += f"\nGap: {recommendation.partial_gap} units still needed"

    for recipient in recipients:
        service.send_notification(
            user=recipient,
            notification_type=NotificationType.PARTIAL_FULFILLMENT,
            subject=subject,
            body=body,
            related_object_type="recommendation",
            related_object_id=recommendation.id,
        )

    logger.info(
        "trigger.partial_fulfillment",
        recommendation_id=str(recommendation.id),
        recipients=len(recipients),
    )


def notify_cross_coordinator_pending(recommendation: Recommendation) -> None:
    """Trigger when a cross-coordinator transfer requires gerente approval."""
    service = NotificationService(recommendation.tenant)
    recipients = get_recipients_for_recommendation(
        recommendation, "cross_coordinator_pending"
    )

    subject_template = SUBJECT_TEMPLATES["cross_coordinator_pending"]
    subject = subject_template.format(part_code=recommendation.part.internal_sku_code)
    body = render_notification_body(recommendation, "cross_coordinator_pending")

    for recipient in recipients:
        service.send_notification(
            user=recipient,
            notification_type=NotificationType.CROSS_COORDINATOR_PENDING,
            subject=subject,
            body=body,
            related_object_type="recommendation",
            related_object_id=recommendation.id,
        )

    logger.info(
        "trigger.cross_coordinator_pending",
        recommendation_id=str(recommendation.id),
        recipients=len(recipients),
    )


def notify_override_created(override: DemandOverride) -> None:
    """Trigger when a demand override is created.

    Notifies gerentes only; the creator already knows they created it.
    """
    service = NotificationService(override.tenant)
    subject_template = SUBJECT_TEMPLATES["override_created"]
    subject = subject_template.format(part_code=override.part.internal_sku_code)
    body = (
        f"Override type: {override.override_type}\n"
        f"Override value: {override.override_value}\n"
        f"Expires at: {override.expires_at or 'never'}\n"
        f"Notes: {override.notes or ''}"
    )

    recipients = _gerentes_for_tenant(override.tenant)
    for recipient in recipients:
        service.send_notification(
            user=recipient,
            notification_type=NotificationType.OVERRIDE_CREATED,
            subject=subject,
            body=body,
            related_object_type="demand_override",
            related_object_id=override.id,
        )

    logger.info(
        "trigger.override_created",
        override_id=str(override.id),
        recipients=len(recipients),
    )


def notify_override_expired(override: DemandOverride) -> None:
    """Trigger when a with-expiry override expires.

    Notifies the original creator and all gerentes.
    """
    service = NotificationService(override.tenant)
    subject_template = SUBJECT_TEMPLATES["override_expired"]
    subject = subject_template.format(part_code=override.part.internal_sku_code)
    body = (
        f"Override expired.\n"
        f"Original override value: {override.override_value}\n"
        f"Expired at: {override.expires_at}\n"
        f"System will now use calculated velocity for this part."
    )

    recipients: list[User] = []
    if override.created_by:
        recipients.append(override.created_by)
    recipients.extend(_gerentes_for_tenant(override.tenant))

    for recipient in recipients:
        service.send_notification(
            user=recipient,
            notification_type=NotificationType.OVERRIDE_EXPIRED,
            subject=subject,
            body=body,
            related_object_type="demand_override",
            related_object_id=override.id,
        )

    logger.info(
        "trigger.override_expired",
        override_id=str(override.id),
        recipients=len(recipients),
    )
