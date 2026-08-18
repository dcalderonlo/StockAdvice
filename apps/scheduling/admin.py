from __future__ import annotations

from django.contrib import admin

from .models import ScheduledRun


@admin.register(ScheduledRun)
class ScheduledRunAdmin(admin.ModelAdmin):
    list_display = ("run_type", "tenant", "branch", "run_date", "recommendations_count", "completed_at")
    list_filter = ("run_type", "tenant", "run_date")
    search_fields = ("branch__code", "tenant__name")
    readonly_fields = ("created_at",)
