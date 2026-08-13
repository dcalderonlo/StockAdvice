"""Tests for CrossReference relationships."""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from apps.core.tests.factories import TenantFactory

from ..models import CrossReference, CrossReferenceType, Part


@pytest.fixture
def tenant():
    return TenantFactory()


@pytest.mark.django_db
def test_create_cross_reference(tenant):
    source = Part.objects.create(tenant=tenant, internal_sku_code="SKU-A", description="A")
    target = Part.objects.create(tenant=tenant, internal_sku_code="SKU-B", description="B")
    ref = CrossReference.objects.create(
        tenant=tenant,
        source_part=source,
        target_part=target,
        type=CrossReferenceType.SUBSTITUTABLE,
    )
    assert ref.source_part == source
    assert ref.target_part == target
    assert ref.type == CrossReferenceType.SUBSTITUTABLE


@pytest.mark.django_db
def test_external_target_code(tenant):
    source = Part.objects.create(tenant=tenant, internal_sku_code="SKU-A", description="A")
    ref = CrossReference.objects.create(
        tenant=tenant,
        source_part=source,
        external_target_code="EXT-123",
        type=CrossReferenceType.ALTERNATIVE_MANUFACTURER,
    )
    assert ref.target_part is None
    assert ref.external_target_code == "EXT-123"
    assert ref.target == "EXT-123"


@pytest.mark.django_db
def test_cross_reference_requires_target_or_external_code(tenant):
    source = Part.objects.create(tenant=tenant, internal_sku_code="SKU-A", description="A")
    ref = CrossReference(
        tenant=tenant,
        source_part=source,
        type=CrossReferenceType.SUCCESSOR,
    )
    with pytest.raises(ValidationError):
        ref.full_clean()


@pytest.mark.django_db
def test_cross_reference_rejects_both_targets(tenant):
    source = Part.objects.create(tenant=tenant, internal_sku_code="SKU-A", description="A")
    target = Part.objects.create(tenant=tenant, internal_sku_code="SKU-B", description="B")
    ref = CrossReference(
        tenant=tenant,
        source_part=source,
        target_part=target,
        external_target_code="EXT-123",
        type=CrossReferenceType.SUCCESSOR,
    )
    with pytest.raises(ValidationError):
        ref.full_clean()


@pytest.mark.django_db
def test_cross_reference_rejects_self_reference(tenant):
    source = Part.objects.create(tenant=tenant, internal_sku_code="SKU-A", description="A")
    ref = CrossReference(
        tenant=tenant,
        source_part=source,
        target_part=source,
        type=CrossReferenceType.SUCCESSOR,
    )
    with pytest.raises(ValidationError):
        ref.full_clean()
