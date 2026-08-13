from __future__ import annotations

from django.contrib import admin

from .models import AuditLog, Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sector", "is_active", "created_at")
    list_filter = ("is_active", "sector")
    search_fields = ("name", "slug")
    readonly_fields = ("slug",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("user", "action", "entity_type", "role_used", "created_at")
    list_filter = ("action", "entity_type")
    search_fields = ("user__email",)
    readonly_fields = (
        "user",
        "role_used",
        "action",
        "entity_type",
        "entity_id",
        "metadata",
        "created_at",
    )
