"""Onboarding state model for tracking tenant onboarding progress."""

from __future__ import annotations

import uuid

from django.db import models
from django.utils import timezone

from apps.core.models import Tenant


class OnboardingState(models.Model):
    """Per-tenant onboarding progress tracker.

    The onboarding flow is: DMS connection -> sales backfill -> branch manager
    assignment -> test replenishment run -> go-live. This model persists the
    current step, configuration, and timestamps so the checklist view can
    display progress and detect stalled onboardings.
    """

    STATUS_CHOICES = [
        ("not_started", "Not started"),
        ("dms_connecting", "DMS connecting"),
        ("dms_connected", "DMS connected"),
        ("sales_backfilling", "Sales backfilling"),
        ("backfill_complete", "Backfill complete"),
        ("manager_assigning", "Manager assigning"),
        ("test_running", "Test run in progress"),
        ("live", "Live"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name="onboarding",
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="not_started",
    )
    dms_adapter_type = models.CharField(max_length=50, blank=True)
    dms_config = models.JSONField(default=dict, blank=True)
    dms_connected_at = models.DateTimeField(null=True, blank=True)
    dms_test_status = models.CharField(max_length=20, blank=True)
    sales_backfilled_until = models.DateField(null=True, blank=True)
    sales_backfill_count = models.IntegerField(default=0)
    manager_assigned = models.BooleanField(default=False)
    test_run_completed_at = models.DateTimeField(null=True, blank=True)
    test_run_recommendations_count = models.IntegerField(default=0)
    go_live_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.tenant.name} onboarding ({self.status})"

    def is_complete(self) -> bool:
        return self.status == "live"

    def days_since_start(self) -> int:
        if not self.created_at:
            return 0
        return (timezone.now() - self.created_at).days

    def is_overdue(self) -> bool:
        # Target: <=28 days from kickoff to first live run.
        return self.days_since_start() > 28 and not self.is_complete()
