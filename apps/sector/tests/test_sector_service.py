"""Tests for SectorConfigurationService and Tenant.get_sector_config()."""

from __future__ import annotations

import pytest

from apps.core.tests.factories import TenantFactory
from apps.sector.models import SectorConfiguration
from apps.sector.services import SectorConfigurationService


@pytest.fixture
def automotive_sector():
    SectorConfiguration.objects.filter(sector_key="automotive_aftermarket").delete()
    return SectorConfiguration.objects.create(
        sector_key="automotive_aftermarket",
        name="Automotive Aftermarket",
        is_default=True,
        config_json={
            "terminology": {
                "part_label": "Part",
                "supplier_label": "Supplier",
                "warehouse_label": "Warehouse",
            },
            "classification": {
                "vc_thresholds": [
                    {"min": 251, "label": "VC1"},
                    {"min": 1, "label": "VC8"},
                ],
                "lifecycle_stages": [
                    {"code": "NEW", "name": "New", "max_months": 6},
                    {"code": "ACTIVE", "name": "Active"},
                ],
            },
            "notification_settings": {"email_enabled": True},
        },
    )


@pytest.fixture
def pharmaceutical_sector():
    return SectorConfiguration.objects.create(
        sector_key="pharmaceutical",
        name="Pharmaceutical",
        is_default=False,
        config_json={
            "terminology": {
                "part_label": "Product",
                "supplier_label": "Vendor",
                "warehouse_label": "Pharmacy",
            },
            "classification": {
                "vc_thresholds": [
                    {"min": 501, "label": "P1"},
                    {"min": 1, "label": "P2"},
                ],
                "lifecycle_stages": [
                    {"code": "STABLE", "name": "Stable"},
                ],
            },
        },
    )


@pytest.mark.django_db
class TestSectorConfigurationService:
    def test_get_sector_for_tenant_uses_config_key(
        self, automotive_sector, pharmaceutical_sector
    ):
        tenant = TenantFactory(config={"sector_key": "pharmaceutical"})
        service = SectorConfigurationService(tenant)
        sector = service.get_sector_for_tenant()
        assert sector == pharmaceutical_sector

    def test_get_sector_defaults_to_automotive(self, automotive_sector):
        tenant = TenantFactory(config={})
        service = SectorConfigurationService(tenant)
        sector = service.get_sector()
        assert sector == automotive_sector

    def test_get_sector_falls_back_to_default_when_key_missing(
        self, automotive_sector, pharmaceutical_sector
    ):
        tenant = TenantFactory(config={"sector_key": "unknown"})
        service = SectorConfigurationService(tenant)
        sector = service.get_sector()
        assert sector == automotive_sector

    def test_get_terminology(self, automotive_sector):
        tenant = TenantFactory()
        service = SectorConfigurationService(tenant)
        terminology = service.get_terminology()
        assert terminology["part_label"] == "Part"
        assert terminology["supplier_label"] == "Supplier"

    def test_get_vc_thresholds(self, automotive_sector):
        tenant = TenantFactory()
        service = SectorConfigurationService(tenant)
        thresholds = service.get_vc_thresholds()
        assert len(thresholds) == 2
        assert thresholds[0]["label"] == "VC1"

    def test_get_lifecycle_stages(self, automotive_sector):
        tenant = TenantFactory()
        service = SectorConfigurationService(tenant)
        stages = service.get_lifecycle_stages()
        assert len(stages) == 2
        assert stages[0]["code"] == "NEW"


@pytest.mark.django_db
class TestTenantGetSectorConfig:
    def test_returns_configured_sector(
        self, automotive_sector, pharmaceutical_sector
    ):
        tenant = TenantFactory(config={"sector_key": "pharmaceutical"})
        assert tenant.get_sector_config() == pharmaceutical_sector

    def test_defaults_to_automotive_when_no_config(self, automotive_sector):
        tenant = TenantFactory(config={})
        assert tenant.get_sector_config() == automotive_sector

    def test_falls_back_to_default_when_sector_missing(
        self, automotive_sector
    ):
        tenant = TenantFactory(config={"sector_key": "hardware"})
        assert tenant.get_sector_config() == automotive_sector

    def test_returns_none_when_no_sectors_exist(self):
        SectorConfiguration.objects.all().delete()
        tenant = TenantFactory(config={})
        assert tenant.get_sector_config() is None
