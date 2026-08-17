"""Django admin configuration for notifications."""

from django.contrib import admin

from .enums import NotificationChannel, NotificationType
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "type",
        "channel",
        "subject",
        "created_at",
        "read_at",
        "sent_at",
    )
    list_filter = (
        "type",
        "channel",
        "tenant",
        ("read_at", admin.EmptyFieldListFilter),
    )
    search_fields = ("user__email", "subject", "body")
    readonly_fields = (
        "tenant",
        "user",
        "type",
        "channel",
        "subject",
        "body",
        "related_object_type",
        "related_object_id",
        "sent_at",
        "read_at",
        "error",
        "created_at",
        "updated_at",
    )
