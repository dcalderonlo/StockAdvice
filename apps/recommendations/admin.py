from __future__ import annotations

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.utils.safestring import mark_safe

from apps.core.models import AuditLog

from .models import Recommendation
from .services import ApprovalService


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
        "audit_log_preview",
    )
    ordering = ["-created_at"]
    actions = ["approve_selected", "reject_selected", "handle_selected"]

    @admin.display(description="Audit log")
    def audit_log_preview(self, obj: Recommendation) -> str:
        entries = AuditLog.objects.for_entity("recommendation", obj.id)[:10]
        if not entries:
            return "No audit log entries."
        rows = [
            f"{entry.created_at.isoformat()} — {entry.action} by {entry.user}"
            for entry in entries
        ]
        return mark_safe("<br>".join(rows))

    def _bulk_approval_action(self, request, queryset, action: str):
        service = ApprovalService(request.user.tenant)
        transition_map = {
            "approve": service.approve_bulk,
            "reject": service.reject_bulk,
            "handle": service.handle_bulk,
        }
        try:
            updated = transition_map[action](list(queryset), request.user)
        except PermissionDenied as exc:
            self.message_user(request, f"Permission denied: {exc}", level="error")
            return
        self.message_user(
            request,
            f"{len(updated)} recommendation(s) {action}d.",
            level="success",
        )

    @admin.action(description="Approve selected pending recommendations")
    def approve_selected(self, request, queryset):
        self._bulk_approval_action(request, queryset, "approve")

    @admin.action(description="Reject selected pending recommendations")
    def reject_selected(self, request, queryset):
        self._bulk_approval_action(request, queryset, "reject")

    @admin.action(description="Mark selected pending recommendations as handled")
    def handle_selected(self, request, queryset):
        self._bulk_approval_action(request, queryset, "handle")
