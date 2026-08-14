"""Tests for the sync_inventory management command."""

from __future__ import annotations

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.inventory.models import StockLevel

from .factories import BranchFactory, PartFactory, TenantFactory


@pytest.fixture
def tenant():
    return TenantFactory()


@pytest.mark.django_db
def test_sync_inventory_all_branches(tenant):
    BranchFactory(tenant=tenant, code="SUC-001")
    BranchFactory(tenant=tenant, code="SUC-002")
    PartFactory(tenant=tenant, internal_sku_code="SKU-0001")

    call_command("sync_inventory", tenant=tenant.slug)

    assert StockLevel.objects.filter(tenant=tenant).exists()


@pytest.mark.django_db
def test_sync_inventory_single_branch(tenant):
    branch = BranchFactory(tenant=tenant, code="SUC-001")
    BranchFactory(tenant=tenant, code="SUC-002")
    PartFactory(tenant=tenant, internal_sku_code="SKU-0001")

    call_command("sync_inventory", branch=branch.code, tenant=tenant.slug)

    assert StockLevel.objects.filter(tenant=tenant, branch=branch).exists()


@pytest.mark.django_db
def test_sync_inventory_unknown_branch(tenant):
    with pytest.raises(CommandError):
        call_command("sync_inventory", branch="NOPE", tenant=tenant.slug)
