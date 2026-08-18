"""Tests for the SectorConfiguration model."""

from __future__ import annotations

import pytest

from apps.sector.models import SectorConfiguration


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
                    {"min": 121, "label": "VC2"},
                    {"min": 61, "label": "VC3"},
                    {"min": 31, "label": "VC4"},
                    {"min": 15, "label": "VC5"},
                    {"min": 7, "label": "VC6"},
                    {"min": 4, "label": "VC7"},
                    {"min": 1, "label": "VC8"},
                ],
                "lifecycle_stages": [
                    {"code": "NEW", "name": "New", "max_months": 6},
                    {"code": "ACTIVE", "name": "Active"},
                    {"code": "PRE_OBSOLETE", "name": "Pre-Obsolete", "min_months_no_sales": 12},
                    {"code": "OBSOLETE", "name": "Obsolete", "min_months_no_sales": 24},
                    {
                        "code": "INACTIVE",
                        "name": "Inactive",
                        "min_months_no_sales": 12,
                        "min_stock_zero": True,
                    },
                ],
            },
        },
    )


@pytest.mark.django_db
class TestSectorConfigurationModel:
    def test_create_sector(self):
        sector = SectorConfiguration.objects.create(
            sector_key="pharmaceutical",
            name="Pharmaceutical",
            description="Pharma sector config",
            is_default=False,
        )
        assert sector.sector_key == "pharmaceutical"
        assert sector.name == "Pharmaceutical"
        assert sector.is_default is False

    def test_str(self, automotive_sector):
        assert str(automotive_sector) == "Automotive Aftermarket"

    def test_sector_key_unique(self, automotive_sector):
        with pytest.raises(Exception):
            SectorConfiguration.objects.create(
                sector_key="automotive_aftermarket",
                name="Duplicate",
            )


@pytest.mark.django_db
class TestGetVCLabel:
    def test_vc_boundaries(self, automotive_sector):
        assert automotive_sector.get_vc_label(0) == ""
        assert automotive_sector.get_vc_label(1) == "VC8"
        assert automotive_sector.get_vc_label(3) == "VC8"
        assert automotive_sector.get_vc_label(4) == "VC7"
        assert automotive_sector.get_vc_label(6) == "VC7"
        assert automotive_sector.get_vc_label(7) == "VC6"
        assert automotive_sector.get_vc_label(14) == "VC6"
        assert automotive_sector.get_vc_label(15) == "VC5"
        assert automotive_sector.get_vc_label(30) == "VC5"
        assert automotive_sector.get_vc_label(31) == "VC4"
        assert automotive_sector.get_vc_label(60) == "VC4"
        assert automotive_sector.get_vc_label(61) == "VC3"
        assert automotive_sector.get_vc_label(120) == "VC3"
        assert automotive_sector.get_vc_label(121) == "VC2"
        assert automotive_sector.get_vc_label(250) == "VC2"
        assert automotive_sector.get_vc_label(251) == "VC1"
        assert automotive_sector.get_vc_label(1000) == "VC1"

    def test_unsorted_thresholds_sorted_correctly(self):
        sector = SectorConfiguration.objects.create(
            sector_key="unsorted",
            name="Unsorted",
            config_json={
                "classification": {
                    "vc_thresholds": [
                        {"min": 1, "label": "LOW"},
                        {"min": 100, "label": "HIGH"},
                    ]
                }
            },
        )
        assert sector.get_vc_label(50) == "LOW"
        assert sector.get_vc_label(100) == "HIGH"
        assert sector.get_vc_label(200) == "HIGH"


@pytest.mark.django_db
class TestGetLifecycleStage:
    def test_new_within_max_months(self, automotive_sector):
        assert automotive_sector.get_lifecycle_stage(months_since_first_seen=3) == "NEW"

    def test_active_when_recent_sales(self, automotive_sector):
        assert (
            automotive_sector.get_lifecycle_stage(
                months_since_first_seen=12,
                months_since_last_sale=3,
                has_stock=True,
            )
            == "ACTIVE"
        )

    def test_pre_obsolete_with_stock(self, automotive_sector):
        assert (
            automotive_sector.get_lifecycle_stage(
                months_since_first_seen=24,
                months_since_last_sale=14,
                has_stock=True,
            )
            == "PRE_OBSOLETE"
        )

    def test_inactive_without_stock(self, automotive_sector):
        assert (
            automotive_sector.get_lifecycle_stage(
                months_since_first_seen=24,
                months_since_last_sale=14,
                has_stock=False,
            )
            == "INACTIVE"
        )

    def test_obsolete_long_no_sales(self, automotive_sector):
        assert (
            automotive_sector.get_lifecycle_stage(
                months_since_first_seen=36,
                months_since_last_sale=26,
                has_stock=True,
            )
            == "OBSOLETE"
        )

    def test_default_active_when_no_stages_configured(self):
        sector = SectorConfiguration.objects.create(
            sector_key="empty",
            name="Empty",
            config_json={},
        )
        assert sector.get_lifecycle_stage() == "ACTIVE"


@pytest.mark.django_db
class TestDefaultManager:
    def test_default_returns_flagged_sector(self, automotive_sector):
        default = SectorConfiguration.objects.default()
        assert default == automotive_sector

    def test_default_returns_none_when_no_default(self):
        SectorConfiguration.objects.all().delete()
        assert SectorConfiguration.objects.default() is None
