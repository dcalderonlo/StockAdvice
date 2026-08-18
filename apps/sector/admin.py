from __future__ import annotations

from django.contrib import admin

from .models import SectorConfiguration


@admin.register(SectorConfiguration)
class SectorConfigurationAdmin(admin.ModelAdmin):
    list_display = ("sector_key", "name", "is_default", "updated_at")
    list_filter = ("is_default",)
    search_fields = ("sector_key", "name")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("sector_key", "name", "description", "is_default")}),
        ("Configuration", {"fields": ("config_json",)}),
        ("Metadata", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
