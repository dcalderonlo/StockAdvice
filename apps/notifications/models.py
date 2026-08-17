"""Notification model for email and in-app alerts."""

from __future__ import annotations

import uuid

from django.db import models
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import TenantAwareModel

from .enums import NotificationChannel, NotificationType


class Notification(TenantAwareModel):
    """A single notification delivered (or attempted) to a user."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
    type = models.CharField(max_length=50, choices=NotificationType.choices)
    channel = models.CharField(max_length=20, choices=NotificationChannel.choices)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    related_object_type = models.CharField(max_length=50, blank=True)
    related_object_id = models.UUIDField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "read_at"]),
            models.Index(fields=["tenant", "created_at"]),
        ]
        ordering = ["-created_at"]

    def mark_as_read(self) -> None:
        """Idempotently mark the notification as read now."""
        if self.read_at is None:
            self.read_at = timezone.now()
            self.save(update_fields=["read_at", "updated_at"])

    def __str__(self) -> str:
        status = "read" if self.read_at else "unread"
        return f"{self.type} for {self.user_id} ({status})"
