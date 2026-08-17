"""Notification service for email and in-app alerts."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from apps.accounts.models import User

from .enums import NotificationChannel, NotificationType
from .models import Notification

if TYPE_CHECKING:
    from apps.core.models import Tenant

logger = structlog.get_logger(__name__)


class NotificationService:
    """Create notifications and dispatch email/in-app alerts for a tenant."""

    def __init__(self, tenant: Tenant):
        self.tenant = tenant

    def send_email_notification(
        self,
        user: User,
        notification_type: str,
        subject: str,
        body: str,
        related_object_type: str | None = None,
        related_object_id=None,
    ) -> Notification:
        """Create an EMAIL notification and attempt to send it."""
        notification = Notification.objects.create(
            tenant=self.tenant,
            user=user,
            type=notification_type,
            channel=NotificationChannel.EMAIL,
            subject=subject,
            body=body,
            related_object_type=related_object_type or "",
            related_object_id=related_object_id,
        )
        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=getattr(
                    settings, "DEFAULT_FROM_EMAIL", "noreply@stockadvice.local"
                ),
                recipient_list=[user.email],
                fail_silently=False,
            )
            notification.sent_at = timezone.now()
            notification.save(update_fields=["sent_at", "updated_at"])
            logger.info(
                "notification.email_sent",
                notification_id=str(notification.id),
                user_id=str(user.id),
                type=notification_type,
            )
        except Exception as e:
            notification.error = str(e)
            notification.save(update_fields=["error", "updated_at"])
            logger.warning(
                "notification.email_failed",
                notification_id=str(notification.id),
                error=str(e),
            )
        return notification

    def send_in_app_notification(
        self,
        user: User,
        notification_type: str,
        subject: str,
        body: str,
        related_object_type: str | None = None,
        related_object_id=None,
    ) -> Notification:
        """Create an IN_APP notification record (no email sent)."""
        notification = Notification.objects.create(
            tenant=self.tenant,
            user=user,
            type=notification_type,
            channel=NotificationChannel.IN_APP,
            subject=subject,
            body=body,
            related_object_type=related_object_type or "",
            related_object_id=related_object_id,
        )
        logger.info(
            "notification.in_app_created",
            notification_id=str(notification.id),
            user_id=str(user.id),
            type=notification_type,
        )
        return notification

    def send_notification(
        self,
        user: User,
        notification_type: str,
        subject: str,
        body: str,
        related_object_type: str | None = None,
        related_object_id=None,
    ) -> list[Notification]:
        """Send via both EMAIL and IN_APP channels.

        Email creation is throttled to one per (user, notification_type) per
        hour so high-volume runs do not flood inboxes. The IN_APP record is
        always created.
        """
        from .throttling import should_send_email_now

        results = []
        if should_send_email_now(notification_type, user):
            results.append(
                self.send_email_notification(
                    user,
                    notification_type,
                    subject,
                    body,
                    related_object_type,
                    related_object_id,
                )
            )
        else:
            logger.info(
                "notification.email_throttled",
                user_id=str(user.id),
                type=notification_type,
            )

        results.append(
            self.send_in_app_notification(
                user,
                notification_type,
                subject,
                body,
                related_object_type,
                related_object_id,
            )
        )
        return results

    def mark_as_read(self, notification_id) -> bool:
        """Mark a tenant-scoped notification as read by its id."""
        try:
            notification = Notification.objects.get(
                id=notification_id, tenant=self.tenant
            )
        except Notification.DoesNotExist:
            return False

        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at", "updated_at"])
        return True

    def get_unread_for_user(self, user: User):
        """Return unread IN_APP notifications for a user in this tenant."""
        return Notification.objects.filter(
            tenant=self.tenant,
            user=user,
            channel=NotificationChannel.IN_APP,
            read_at__isnull=True,
        ).order_by("-created_at")
