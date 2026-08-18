"""Tests for sector-aware classification helpers and engine integration."""

from __future__ import annotations

import pytest

from datetime import date

from apps.catalog.classification import (
    ClassificationEngine,
    lifecycle_stage,
    volume_class,
)
from apps.catalog.models import ClassificationResult
from apps.core.tests.factories import TenantFactory
from apps.inventory.models import StockMovement, StockMovementType
from apps.inventory.tests.factories import BranchFactory, PartFactory
from apps.sector.models import SectorConfiguration


@pytest.fixture
def automotive_sector():
    SectorConfiguration.objects.filter(sector_key="automotive_aftermarket").delete()
    return SectorConfiguration.objects.create(
        sector_key="automotive_aftermarket",
        name="Automotive Aftermarket",
        is_default=True,
        config_json={
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


@pytest.fixture
def hardware_sector():
    SectorConfiguration.objects.filter(sector_key="hardware").delete()
    return SectorConfiguration.objects.create(
        sector_key="hardware",
        name="Hardware",
        config_json={
            "classification": {
                "vc_thresholds": [
                    {"min": 501, "label": "HVC1"},
                    {"min": 201, "label": "HVC2"},
                    {"min": 101, "label": "HVC3"},
                    {"min": 1, "label": "HVC4"},
                ],
                "lifecycle_stages": [
                    {"code": "FRESH", "name": "Fresh", "max_months": 3},
                    {"code": "MOVING", "name": "Moving"},
                    {"code": "STALE", "name": "Stale", "min_months_no_sales": 6},
                ],
            },
        },
    )


@pytest.mark.django_db
class TestVolumeClassSectorAware:
    def test_automotive_thresholds(self, automotive_sector):
        assert volume_class(100, sector_config=automotive_sector) == "VC3"
        assert volume_class(250, sector_config=automotive_sector) == "VC2"
        assert volume_class(251, sector_config=automotive_sector) == "VC1"

    def test_hardware_thresholds(self, hardware_sector):
        assert volume_class(50, sector_config=hardware_sector) == "HVC4"
        assert volume_class(100, sector_config=hardware_sector) == "HVC4"
        assert volume_class(101, sector_config=hardware_sector) == "HVC3"
        assert volume_class(500, sector_config=hardware_sector) == "HVC2"
        assert volume_class(501, sector_config=hardware_sector) == "HVC1"

    def test_fallback_when_no_sector(self):
        assert volume_class(100) == "VC3"
        assert volume_class(0) == ""


@pytest.mark.django_db
class TestLifecycleStageSectorAware:
    def test_automotive_rules(self, automotive_sector):
        assert lifecycle_stage(3, 1, True, sector_config=automotive_sector) == "NEW"
        assert lifecycle_stage(12, 3, True, sector_config=automotive_sector) == "ACTIVE"
        assert lifecycle_stage(24, 14, True, sector_config=automotive_sector) == "PRE_OBSOLETE"
        assert lifecycle_stage(24, 14, False, sector_config=automotive_sector) == "INACTIVE"
        assert lifecycle_stage(36, 26, True, sector_config=automotive_sector) == "OBSOLETE"

    def test_hardware_rules(self, hardware_sector):
        assert lifecycle_stage(2, 1, True, sector_config=hardware_sector) == "FRESH"
        assert lifecycle_stage(6, 1, True, sector_config=hardware_sector) == "MOVING"
        assert lifecycle_stage(12, 8, True, sector_config=hardware_sector) == "STALE"

    def test_fallback_when_no_sector(self):
        assert lifecycle_stage(3, 1, True) == "NEW"
        assert lifecycle_stage(12, 3, True) == "ACTIVE"
        assert lifecycle_stage(24, 14, True) == "PRE_OBSOLETE"


@pytest.mark.django_db
class TestClassificationEngineSectorAware:
    def test_engine_uses_tenant_sector_thresholds(
        self, automotive_sector, hardware_sector
    ):
        tenant = TenantFactory(config={"sector_key": "hardware"})
        branch = BranchFactory(tenant=tenant)
        part = PartFactory(tenant=tenant)

        # 150 sales in the last year: automotive would classify as VC2,
        # hardware thresholds classify as HVC3.
        StockMovement.objects.create(
            tenant=tenant,
            branch=branch,
            part=part,
            movement_type=StockMovementType.SALE,
            quantity=-150,
            movement_date=date.today(),
        )

        engine = ClassificationEngine(tenant)
        result = engine.classify_part(part, branch=branch)

        assert result.volume_class == "HVC3"

    def test_engine_falls_back_to_automotive_default(self, automotive_sector):
        tenant = TenantFactory(config={})
        branch = BranchFactory(tenant=tenant)
        part = PartFactory(tenant=tenant)

        StockMovement.objects.create(
            tenant=tenant,
            branch=branch,
            part=part,
            movement_type=StockMovementType.SALE,
            quantity=-150,
            movement_date=date.today(),
        )

        engine = ClassificationEngine(tenant)
        result = engine.classify_part(part, branch=branch)

        assert result.volume_class == "VC2"

    def test_engine_explicit_sector_config_overrides_tenant(
        self, automotive_sector, hardware_sector
    ):
        tenant = TenantFactory(config={"sector_key": "automotive_aftermarket"})
        branch = BranchFactory(tenant=tenant)
        part = PartFactory(tenant=tenant)

        StockMovement.objects.create(
            tenant=tenant,
            branch=branch,
            part=part,
            movement_type=StockMovementType.SALE,
            quantity=-400,
            movement_date=date.today(),
        )

        engine = ClassificationEngine(tenant, sector_config=hardware_sector)
        result = engine.classify_part(part, branch=branch)

        # 400 sales: automotive VC1, hardware HVC2.
        assert result.volume_class == "HVC2"

    def test_existing_tests_unaffected_by_default_sector(self, automotive_sector):
        tenant = TenantFactory()
        branch = BranchFactory(tenant=tenant)
        part = PartFactory(tenant=tenant)

        StockMovement.objects.create(
            tenant=tenant,
            branch=branch,
            part=part,
            movement_type=StockMovementType.SALE,
            quantity=-300,
            movement_date=date.today(),
        )

        engine = ClassificationEngine(tenant)
        result = engine.classify_part(part, branch=branch)

        assert isinstance(result, ClassificationResult)
        assert result.volume_class == "VC1"
