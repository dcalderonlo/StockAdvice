"""Tests for Part and related catalog models."""

from __future__ import annotations

import pytest

from apps.core.tests.factories import TenantFactory

from ..admin import CatalogCSVImportService
from ..models import Part


@pytest.fixture
def tenant():
    return TenantFactory()


@pytest.mark.django_db
def test_create_part(tenant):
    part = Part.objects.create(
        tenant=tenant,
        internal_sku_code="SKU-0001",
        primary_manufacturer_code="MFR-0001",
        description="Brake pad",
        category="Brake System",
    )
    assert part.internal_sku_code == "SKU-0001"
    assert part.primary_manufacturer_code == "MFR-0001"
    assert part.unit_of_measure == "PCS"
    assert part.lead_time_days == 7
    assert part.is_active is True


@pytest.mark.django_db
def test_unique_sku_per_tenant(tenant):
    Part.objects.create(
        tenant=tenant,
        internal_sku_code="SKU-0001",
        description="First",
    )
    with pytest.raises(Exception):
        Part.objects.create(
            tenant=tenant,
            internal_sku_code="SKU-0001",
            description="Duplicate",
        )


@pytest.mark.django_db
def test_same_sku_different_tenants(tenant):
    tenant2 = TenantFactory()
    Part.objects.create(tenant=tenant, internal_sku_code="SKU-0001", description="First")
    Part.objects.create(tenant=tenant2, internal_sku_code="SKU-0001", description="Second")
    assert Part.objects.filter(internal_sku_code="SKU-0001").count() == 2


@pytest.mark.django_db
def test_alternative_manufacturer_codes(tenant):
    from ..models import CrossReference, CrossReferenceType

    source = Part.objects.create(
        tenant=tenant,
        internal_sku_code="SKU-A",
        primary_manufacturer_code="MFR-A",
        description="Source",
    )
    alt = Part.objects.create(
        tenant=tenant,
        internal_sku_code="SKU-B",
        primary_manufacturer_code="MFR-B",
        description="Alternative",
    )
    CrossReference.objects.create(
        tenant=tenant,
        source_part=source,
        target_part=alt,
        type=CrossReferenceType.ALTERNATIVE_MANUFACTURER,
    )
    assert source.alternative_manufacturer_codes() == ["MFR-B"]


@pytest.mark.django_db
def test_csv_import_service(tenant):
    csv_content = (
        "internal_sku_code,description,primary_manufacturer_code,category,lead_time_days\n"
        "CSV-001,Imported one,MFR-001,Brake,5\n"
        "CSV-002,Imported two,MFR-002,Engine,10\n"
    )
    from io import BytesIO

    result = CatalogCSVImportService.import_csv(tenant, BytesIO(csv_content.encode("utf-8")))
    assert result == {"created": 2, "updated": 0}
    assert Part.objects.filter(tenant=tenant, internal_sku_code="CSV-001").exists()


@pytest.mark.django_db
def test_csv_import_updates_existing(tenant):
    Part.objects.create(
        tenant=tenant,
        internal_sku_code="CSV-001",
        description="Old",
        category="Old",
    )
    csv_content = (
        "internal_sku_code,description,primary_manufacturer_code,category\n"
        "CSV-001,New description,MFR-NEW,Brake\n"
    )
    from io import BytesIO

    result = CatalogCSVImportService.import_csv(tenant, BytesIO(csv_content.encode("utf-8")))
    assert result == {"created": 0, "updated": 1}
    part = Part.objects.get(tenant=tenant, internal_sku_code="CSV-001")
    assert part.description == "New description"
    assert part.category == "Brake"
