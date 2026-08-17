"""Throttling and digest helpers for notification dispatch.

These helpers are designed to be called by ``NotificationService`` or by
future digest/scheduler code. They are intentionally decoupled from the
service so that scheduling and batching logic can be built on top without
rewiring the core trigger functions.
"""

from datetime import timedelta

import structlog
from django.utils import timezone

logger = structlog.get_logger(__name__)


def should_send_email_now(notification_type: str, user) -> bool:
    """Throttle: don't send more than 1 email per (user, type) per hour.

    Returns ``True`` if it has been more than one hour since the last email
    of this type was sent to this user.
    """
    from apps.notifications.models import Notification, NotificationChannel

    one_hour_ago = timezone.now() - timedelta(hours=1)
    recent = Notification.objects.filter(
        tenant=user.tenant,
        user=user,
        type=notification_type,
        channel=NotificationChannel.EMAIL,
        sent_at__gte=one_hour_ago,
    ).exists()
    return not recent


def digest_pending_notifications(user, notification_type: str) -> dict | None:
    """Return a digest of pending notifications of a type for a user.

    Pending means EMAIL-channel notifications that have not yet been sent.
    Returns ``None`` when no pending notifications exist.
    """
    from apps.notifications.models import Notification, NotificationChannel

    pending = Notification.objects.filter(
        tenant=user.tenant,
        user=user,
        type=notification_type,
        channel=NotificationChannel.EMAIL,
        sent_at__isnull=True,
    ).order_by("created_at")

    if not pending.exists():
        return None

    items = list(pending)
    subject = (
        f"{items[0].subject} (and {len(items) - 1} more)"
        if len(items) > 1
        else items[0].subject
    )
    return {
        "subject": subject,
        "body": "\n---\n".join(item.body for item in items),
        "count": len(items),
    }
