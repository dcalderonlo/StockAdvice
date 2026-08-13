"""Tests for the DMS adapter factory."""

from __future__ import annotations

import pytest

from apps.catalog.adapters.factory import get_dms_adapter
from apps.catalog.adapters.mock import MockDMSAdapter

from .factories import TenantFactory


@pytest.fixture
def tenant():
    return TenantFactory()


@pytest.mark.django_db
def test_get_mock_adapter(tenant):
    tenant.dms_adapter_type = "mock"
    adapter = get_dms_adapter(tenant)
    assert isinstance(adapter, MockDMSAdapter)


@pytest.mark.django_db
def test_get_adapter_defaults_to_mock_when_blank(tenant):
    tenant.dms_adapter_type = ""
    tenant.dms_config = {}
    adapter = get_dms_adapter(tenant)
    assert isinstance(adapter, MockDMSAdapter)


@pytest.mark.django_db
def test_get_autologica_adapter_raises_not_implemented(tenant):
    tenant.dms_adapter_type = "autologica"
    with pytest.raises(NotImplementedError):
        get_dms_adapter(tenant)


@pytest.mark.django_db
def test_get_unknown_adapter_raises_value_error(tenant):
    tenant.dms_adapter_type = "unknown"
    with pytest.raises(ValueError):
        get_dms_adapter(tenant)
