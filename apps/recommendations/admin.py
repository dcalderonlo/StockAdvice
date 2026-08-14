from __future__ import annotations

from django.contrib import admin

from .models import Recommendation


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = (
        "branch",
        "part",
        "state",
        "quantity",
        "source_type",
        "source_branch",
        "is_partial",
        "partial_gap",
        "current_stock",
        "punto_pedido",
        "created_at",
        "decided_at",
    )
    list_filter = ("state", "source_type", "is_partial", "tenant", "branch")
    search_fields = ("part__internal_sku_code", "part__description", "explanation")
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "decided_at",
        "coverage_days_after_fulfillment",
    )
    ordering = ["-created_at"]
