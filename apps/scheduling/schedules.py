"""Helper to register default Django-Q2 schedules for a tenant."""

from __future__ import annotations

from django_q.models import Schedule

from apps.branches.models import Branch
from apps.core.models import Tenant

from .jobs import (
    scheduled_classification_pass,
    scheduled_notification_dispatch,
    scheduled_override_cleanup,
    scheduled_replenishment_run,
)


def setup_default_schedules(tenant: Tenant) -> None:
    """Set up default recurring schedules for a tenant.

    - Replenishment: weekly for each active branch.
    - Classification: monthly for the tenant.
    - Notification dispatch: every 15 minutes (shared, tenant-agnostic).
    - Override cleanup: daily (shared, tenant-agnostic).
    """
    for branch in Branch.objects.filter(tenant=tenant, is_active=True):
        Schedule.objects.get_or_create(
            name=f"replenishment-{branch.id}",
            defaults={
                "func": "apps.scheduling.jobs.scheduled_replenishment_run",
                "args": f'["{branch.id}"]',
                "schedule_type": Schedule.WEEKLY,
                "repeats": -1,
            },
        )

    Schedule.objects.get_or_create(
        name=f"classification-{tenant.id}",
        defaults={
            "func": "apps.scheduling.jobs.scheduled_classification_pass",
            "args": f'["{tenant.id}"]',
            "schedule_type": Schedule.MONTHLY,
            "repeats": -1,
        },
    )

    Schedule.objects.get_or_create(
        name="notification-dispatch",
        defaults={
            "func": "apps.scheduling.jobs.scheduled_notification_dispatch",
            "args": "[]",
            "schedule_type": Schedule.MINUTES,
            "minutes": 15,
            "repeats": -1,
        },
    )

    Schedule.objects.get_or_create(
        name="override-cleanup",
        defaults={
            "func": "apps.scheduling.jobs.scheduled_override_cleanup",
            "args": "[]",
            "schedule_type": Schedule.DAILY,
            "repeats": -1,
        },
    )
