"""Scheduled run bookkeeping for background jobs."""

from __future__ import annotations

import uuid

from django.db import models

from apps.core.models import Tenant


class ScheduledRun(models.Model):
    """Tracks completed background jobs and enforces idempotency.

    The unique constraint on ``(tenant, run_type, run_date, branch)`` guarantees
    that a replenishment run is only recorded once per branch/date and that a
    classification pass is only recorded once per tenant/month.
    """

    RUN_TYPE_CHOICES = [
        ("replenishment", "Replenishment"),
        ("classification", "Classification"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="scheduled_runs",
    )
    run_type = models.CharField(max_length=20, choices=RUN_TYPE_CHOICES)
    branch = models.ForeignKey(
        "branches.Branch",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="scheduled_runs",
    )
    run_date = models.CharField(max_length=20)
    recommendations_count = models.IntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "run_type", "run_date", "branch"],
                name="unique_scheduled_run",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "run_type", "run_date"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        scope = f"@{self.branch.code}" if self.branch else "tenant-wide"
        return f"{self.run_type} {self.run_date} {scope}"
