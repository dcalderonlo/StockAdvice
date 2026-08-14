"""Test factories for inventory-related models."""

from __future__ import annotations

import factory

from apps.branches.models import Branch, BranchType
from apps.catalog.models import Part
from apps.core.models import Tenant


class TenantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tenant
        django_get_or_create = ("slug",)

    name = factory.Sequence(lambda n: f"Tenant {n}")
    slug = factory.Sequence(lambda n: f"tenant-{n}")
    sector = Tenant.Sector.AUTOMOTIVE
    is_active = True
    dms_adapter_type = "mock"


class BranchFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Branch
        django_get_or_create = ("tenant", "code")

    tenant = factory.SubFactory(TenantFactory)
    code = factory.Sequence(lambda n: f"SUC-{n:03d}")
    name = factory.Sequence(lambda n: f"Branch {n}")
    type = BranchType.SUCURSAL
    is_active = True


class PartFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Part
        django_get_or_create = ("tenant", "internal_sku_code")

    tenant = factory.SubFactory(TenantFactory)
    internal_sku_code = factory.Sequence(lambda n: f"SKU-{n:04d}")
    primary_manufacturer_code = factory.Sequence(lambda n: f"MFR-{n:04d}")
    description = factory.Sequence(lambda n: f"Part {n}")
    category = "Brake System"
    unit_of_measure = "PCS"
    lead_time_days = 7
    is_active = True
