"""Tests for the scheduling models."""

from __future__ import annotations

import pytest
from django.db import IntegrityError

from apps.core.tests.factories import TenantFactory
from apps.inventory.tests.factories import BranchFactory

from ..models import ScheduledRun


@pytest.mark.django_db
def test_scheduled_run_str():
    tenant = TenantFactory()
    run = ScheduledRun.objects.create(
        tenant=tenant,
        run_type="classification",
        run_date="2026-08",
        recommendations_count=12,
    )
    assert str(run) == "classification 2026-08 tenant-wide"


@pytest.mark.django_db
def test_scheduled_run_unique_constraint():
    tenant = TenantFactory()
    branch = BranchFactory(tenant=tenant)
    ScheduledRun.objects.create(
        tenant=tenant,
        run_type="replenishment",
        branch=branch,
        run_date="2026-08-17",
        recommendations_count=5,
    )
    with pytest.raises(IntegrityError):
        ScheduledRun.objects.create(
            tenant=tenant,
            run_type="replenishment",
            branch=branch,
            run_date="2026-08-17",
            recommendations_count=5,
        )
