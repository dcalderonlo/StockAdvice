"""Tests for Django-Q2 schedule registration."""

from __future__ import annotations

import pytest
from django.core.management import call_command
from django_q.models import Schedule

from apps.core.tests.factories import TenantFactory
from apps.inventory.tests.factories import BranchFactory

from ..schedules import setup_default_schedules


@pytest.mark.django_db
def test_setup_default_schedules_creates_expected_entries():
    tenant = TenantFactory()
    branch = BranchFactory(tenant=tenant)

    setup_default_schedules(tenant)

    assert Schedule.objects.filter(name=f"replenishment-{branch.id}").exists()
    assert Schedule.objects.filter(name=f"classification-{tenant.id}").exists()
    assert Schedule.objects.filter(name="notification-dispatch").exists()
    assert Schedule.objects.filter(name="override-cleanup").exists()

    replenishment = Schedule.objects.get(name=f"replenishment-{branch.id}")
    assert replenishment.func == "apps.scheduling.jobs.scheduled_replenishment_run"
    assert replenishment.schedule_type == Schedule.WEEKLY


@pytest.mark.django_db
def test_setup_schedules_management_command():
    tenant = TenantFactory()
    BranchFactory(tenant=tenant)

    call_command("setup_schedules")

    assert Schedule.objects.count() == 4
    assert Schedule.objects.filter(name=f"classification-{tenant.id}").exists()
