"""Django admin configuration for branches."""

from __future__ import annotations

from django.contrib import admin

from .models import Branch


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "type", "tenant", "parent_branch", "is_active")
    list_filter = ("type", "is_active", "tenant")
    search_fields = ("code", "name")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("parent_branch", "manager", "coordinator")
    fieldsets = (
        (None, {"fields": ("tenant", "code", "name", "type", "is_active")}),
        ("Topology", {"fields": ("parent_branch",)}),
        ("People", {"fields": ("manager", "coordinator")}),
        ("Location", {"fields": ("address",)}),
        ("Metadata", {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)}),
    )
