from django.contrib import admin

from .models import OnboardingState


@admin.register(OnboardingState)
class OnboardingStateAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "status",
        "dms_adapter_type",
        "sales_backfill_count",
        "manager_assigned",
        "go_live_at",
        "created_at",
    )
    list_filter = ("status", "dms_adapter_type")
    search_fields = ("tenant__name", "tenant__slug")
    readonly_fields = ("created_at", "updated_at")
