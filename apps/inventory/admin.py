"""Django admin configuration for inventory models."""

from __future__ import annotations

from django.contrib import admin

from .models import StockEnTransito, StockLevel, StockMovement


@admin.register(StockLevel)
class StockLevelAdmin(admin.ModelAdmin):
    list_display = (
        "branch",
        "part",
        "stock_disponible",
        "stock_en_transito",
        "total_stock",
        "last_synced_at",
    )
    list_filter = ("branch", "last_synced_at")
    search_fields = ("part__internal_sku_code", "part__description")
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Total stock")
    def total_stock(self, obj: StockLevel) -> float:
        return obj.total_stock


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        "movement_date",
        "branch",
        "part",
        "movement_type",
        "quantity",
        "source",
    )
    list_filter = ("movement_type", "movement_date", "branch")
    search_fields = ("part__internal_sku_code", "external_reference")
    readonly_fields = ("created_at",)
    date_hierarchy = "movement_date"


@admin.register(StockEnTransito)
class StockEnTransitoAdmin(admin.ModelAdmin):
    list_display = (
        "source_branch",
        "destination_branch",
        "part",
        "quantity",
        "status",
        "expected_arrival",
    )
    list_filter = ("status", "expected_arrival", "destination_branch")
    search_fields = ("part__internal_sku_code", "external_reference")
    readonly_fields = ("created_at", "updated_at")
    actions = ["mark_received"]

    @admin.action(description="Mark selected transfers as received")
    def mark_received(self, request, queryset):
        for transfer in queryset.filter(status__in=("pending", "in_transit")):
            transfer.mark_received()
