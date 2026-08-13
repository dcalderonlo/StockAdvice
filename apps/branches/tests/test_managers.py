"""Tests for the Branch manager helpers."""

from __future__ import annotations

import pytest

from apps.core.tests.factories import TenantFactory

from ..models import Branch, BranchType


@pytest.fixture
def tenant():
    return TenantFactory()


@pytest.mark.django_db
def test_active_manager(tenant):
    Branch.objects.create(tenant=tenant, code="SUC-001", name="Active", type=BranchType.SUCURSAL)
    Branch.objects.create(
        tenant=tenant, code="SUC-002", name="Inactive", type=BranchType.SUCURSAL, is_active=False
    )
    assert Branch.objects.active().count() == 1
    assert Branch.objects.active().first().code == "SUC-001"


@pytest.mark.django_db
def test_distribution_centers_manager(tenant):
    Branch.objects.create(tenant=tenant, code="CD-001", name="DC", type=BranchType.CENTRO_DISTRIBUCION)
    Branch.objects.create(tenant=tenant, code="SUC-001", name="Branch", type=BranchType.SUCURSAL)
    assert Branch.objects.distribution_centers().count() == 1
    assert Branch.objects.distribution_centers().first().code == "CD-001"


@pytest.mark.django_db
def test_regular_manager(tenant):
    Branch.objects.create(tenant=tenant, code="CD-001", name="DC", type=BranchType.CENTRO_DISTRIBUCION)
    Branch.objects.create(tenant=tenant, code="SUC-001", name="Branch", type=BranchType.SUCURSAL)
    assert Branch.objects.regular().count() == 1
    assert Branch.objects.regular().first().code == "SUC-001"
