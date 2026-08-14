"""Tests for the classification engine and ClassificationResult model."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.catalog.classification import ClassificationEngine, new_subtype, volume_class
from apps.catalog.models import ClassificationResult, LifecycleStage, Part
from apps.core.tests.factories import TenantFactory
from apps.inventory.models import StockLevel, StockMovement, StockMovementType
from apps.inventory.tests.factories import BranchFactory, PartFactory


def make_date(days_ago: int) -> date:
    """Return a date ``days_ago`` days before today."""
    return date.today() - timedelta(days=days_ago)


def create_sale(
    tenant,
    branch,
    part: Part,
    quantity: float,
    movement_date: date,
) -> StockMovement:
    """Create a single SALE movement."""
    return StockMovement.objects.create(
        tenant=tenant,
        branch=branch,
        part=part,
        movement_type=StockMovementType.SALE,
        quantity=Decimal(str(-quantity)),
        movement_date=movement_date,
    )


def create_stock(tenant, branch, part: Part, disponible: float) -> StockLevel:
    """Create a StockLevel record for the given branch/part."""
    return StockLevel.objects.create(
        tenant=tenant,
        branch=branch,
        part=part,
        stock_disponible=Decimal(str(disponible)),
        stock_en_transito=Decimal("0"),
    )


def create_part(tenant, sku: str, description: str, created_at: datetime) -> Part:
    """Create a part with an explicit ``created_at`` value."""
    part = Part.objects.create(
        tenant=tenant,
        internal_sku_code=sku,
        description=description,
    )
    part.created_at = created_at
    part.save()
    return part


@pytest.fixture
def tenant():
    return TenantFactory()


@pytest.fixture
def branch(tenant):
    return BranchFactory(tenant=tenant, code="SUC-001")


@pytest.fixture
def part(tenant):
    return PartFactory(tenant=tenant)


class TestVolumeClass:
    @pytest.mark.parametrize(
        "sales,expected",
        [
            (0, ""),
            (1, "VC8"),
            (3, "VC8"),
            (4, "VC7"),
            (6, "VC7"),
            (7, "VC6"),
            (14, "VC6"),
            (15, "VC5"),
            (30, "VC5"),
            (31, "VC4"),
            (60, "VC4"),
            (61, "VC3"),
            (120, "VC3"),
            (121, "VC2"),
            (250, "VC2"),
            (251, "VC1"),
            (1000, "VC1"),
        ],
    )
    def test_volume_class_boundaries(self, sales: int, expected: str) -> None:
        assert volume_class(sales) == expected


class TestNewSubtype:
    def test_n1_high_velocity(self):
        assert new_subtype(16) == "N1"
        assert new_subtype(100) == "N1"

    def test_n2_moderate_velocity(self):
        assert new_subtype(4) == "N2"
        assert new_subtype(15) == "N2"

    def test_n3_low_velocity(self):
        assert new_subtype(0) == "N3"
        assert new_subtype(3) == "N3"


@pytest.mark.django_db
class TestLifecycleStage:
    def test_new_high_velocity(self, tenant, branch):
        part = create_part(
            tenant,
            "SKU-NEW-HV",
            "New high velocity",
            timezone.make_aware(datetime(2026, 1, 1)),
        )
        engine = ClassificationEngine(tenant, today=date(2026, 7, 1))
        # 18 sales in first 6 months (entry + 180 days), all before engine.today.
        for day in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180]:
            create_sale(tenant, branch, part, 1, date(2026, 1, 1) + timedelta(days=day))

        result = engine.classify_part(part, branch=branch)

        assert result.lifecycle_stage == LifecycleStage.NEW
        assert result.lifecycle_subcode == "N1"

    def test_new_moderate_velocity(self, tenant, branch):
        part = create_part(
            tenant,
            "SKU-NEW-MV",
            "New moderate velocity",
            timezone.make_aware(datetime(2026, 1, 1)),
        )
        engine = ClassificationEngine(tenant, today=date(2026, 5, 1))
        for day in [10, 40, 70, 100]:
            create_sale(tenant, branch, part, 1, date(2026, 1, 1) + timedelta(days=day))

        result = engine.classify_part(part, branch=branch)

        assert result.lifecycle_stage == LifecycleStage.NEW
        assert result.lifecycle_subcode == "N2"

    def test_new_low_velocity(self, tenant, branch):
        part = create_part(
            tenant,
            "SKU-NEW-LV",
            "New low velocity",
            timezone.make_aware(datetime(2026, 1, 1)),
        )
        engine = ClassificationEngine(tenant, today=date(2026, 5, 1))
        create_sale(tenant, branch, part, 1, date(2026, 2, 1))

        result = engine.classify_part(part, branch=branch)

        assert result.lifecycle_stage == LifecycleStage.NEW
        assert result.lifecycle_subcode == "N3"

    def test_new_no_sales(self, tenant, branch):
        part = create_part(
            tenant,
            "SKU-NEW-NS",
            "New no sales",
            timezone.make_aware(datetime(2026, 1, 1)),
        )
        engine = ClassificationEngine(tenant, today=date(2026, 5, 1))

        result = engine.classify_part(part, branch=branch)

        assert result.lifecycle_stage == LifecycleStage.NEW
        assert result.lifecycle_subcode == "N3"
        assert result.volume_class == ""

    def test_active_with_volume_class(self, tenant, branch):
        part = create_part(
            tenant,
            "SKU-ACTIVE",
            "Active part",
            timezone.make_aware(datetime(2025, 1, 1)),
        )
        engine = ClassificationEngine(tenant, today=date(2026, 5, 1))
        create_sale(tenant, branch, part, 300, engine.today - timedelta(days=30))

        result = engine.classify_part(part, branch=branch)

        assert result.lifecycle_stage == LifecycleStage.ACTIVE
        assert result.volume_class == "VC1"

    def test_pre_obsolete_with_stock(self, tenant, branch):
        part = create_part(
            tenant,
            "SKU-PRE-OBS",
            "Pre-obsolete part",
            timezone.make_aware(datetime(2024, 1, 1)),
        )
        create_stock(tenant, branch, part, 10.0)
        create_sale(tenant, branch, part, 1, make_date(400))
        engine = ClassificationEngine(tenant, today=date.today())

        result = engine.classify_part(part, branch=branch)

        assert result.lifecycle_stage == LifecycleStage.PRE_OBSOLETE
        assert result.lifecycle_subcode == "OBS-P"

    def test_obsolete_no_sales_over_24_months(self, tenant, branch):
        part = create_part(
            tenant,
            "SKU-OBS",
            "Obsolete part",
            timezone.make_aware(datetime(2022, 1, 1)),
        )
        create_stock(tenant, branch, part, 10.0)
        create_sale(tenant, branch, part, 1, make_date(800))
        engine = ClassificationEngine(tenant, today=date.today())

        result = engine.classify_part(part, branch=branch)

        assert result.lifecycle_stage == LifecycleStage.OBSOLETE
        assert result.lifecycle_subcode == "OBS-R"

    def test_inactive_no_sales_no_stock(self, tenant, branch):
        part = create_part(
            tenant,
            "SKU-INACT",
            "Inactive part",
            timezone.make_aware(datetime(2024, 1, 1)),
        )
        create_sale(tenant, branch, part, 1, make_date(400))
        engine = ClassificationEngine(tenant, today=date.today())

        result = engine.classify_part(part, branch=branch)

        assert result.lifecycle_stage == LifecycleStage.INACTIVE
        assert result.lifecycle_subcode == "INACT"

    def test_inactive_never_sold_no_stock(self, tenant, branch):
        part = create_part(
            tenant,
            "SKU-INACT-NS",
            "Inactive never sold",
            timezone.make_aware(datetime(2024, 1, 1)),
        )
        engine = ClassificationEngine(tenant, today=date.today())

        result = engine.classify_part(part, branch=branch)

        assert result.lifecycle_stage == LifecycleStage.INACTIVE


@pytest.mark.django_db
class TestSpecialFlags:
    def test_campaign_flag(self, tenant, branch, part):
        part.special_flags = {"is_campaign": True, "campaign_notes": "Recall batch 1"}
        part.save()
        engine = ClassificationEngine(tenant)

        result = engine.classify_part(part, branch=branch)

        assert result.lifecycle_stage == LifecycleStage.SPECIAL_CAMPAIGN
        assert result.lifecycle_subcode == "NS-C"
        assert result.volume_class == ""

    def test_non_stock_flag(self, tenant, branch, part):
        part.special_flags = {"is_non_stock": True}
        part.save()
        engine = ClassificationEngine(tenant)

        result = engine.classify_part(part, branch=branch)

        assert result.lifecycle_stage == LifecycleStage.SPECIAL_NON_STOCK
        assert result.lifecycle_subcode == "NS-NS"
        assert result.volume_class == ""


@pytest.mark.django_db
class TestClassificationEngine:
    def test_idempotency(self, tenant, branch):
        part = create_part(
            tenant,
            "SKU-IDEM",
            "Idempotency part",
            timezone.make_aware(datetime(2025, 1, 1)),
        )
        create_sale(tenant, branch, part, 300, make_date(30))
        engine = ClassificationEngine(tenant)

        first = engine.classify_part(part, branch=branch)
        second = engine.classify_part(part, branch=branch)

        assert first.id == second.id
        assert first.lifecycle_stage == second.lifecycle_stage
        assert first.volume_class == second.volume_class

    def test_tenant_isolation(self, tenant, branch, part):
        other_tenant = TenantFactory()
        other_branch = BranchFactory(tenant=other_tenant, code="SUC-OTHER")
        create_sale(other_tenant, other_branch, part, 300, make_date(30))

        engine = ClassificationEngine(tenant)
        result = engine.classify_part(part, branch=branch)

        assert result.lifecycle_stage == LifecycleStage.NEW
        assert result.annual_sales == 0

    def test_classify_all_parts(self, tenant, branch):
        part_a = create_part(
            tenant,
            "SKU-A",
            "Part A",
            timezone.make_aware(datetime(2025, 1, 1)),
        )
        part_b = create_part(
            tenant,
            "SKU-B",
            "Part B",
            timezone.make_aware(datetime(2025, 1, 1)),
        )
        create_sale(tenant, branch, part_a, 300, make_date(30))
        create_sale(tenant, branch, part_b, 1, make_date(30))

        engine = ClassificationEngine(tenant)
        results = engine.classify_all_parts(branch=branch)

        assert len(results) == 2
        assert ClassificationResult.objects.filter(tenant=tenant, branch=branch).count() == 2

    def test_classify_tenant_org_wide(self, tenant):
        branch_a = BranchFactory(tenant=tenant, code="SUC-A")
        branch_b = BranchFactory(tenant=tenant, code="SUC-B")
        part = create_part(
            tenant,
            "SKU-ORG",
            "Org-wide part",
            timezone.make_aware(datetime(2025, 1, 1)),
        )
        create_sale(tenant, branch_a, part, 150, make_date(30))
        create_sale(tenant, branch_b, part, 150, make_date(30))

        engine = ClassificationEngine(tenant)
        results = engine.classify_tenant()

        assert len(results) == 1
        assert results[part.id].annual_sales == 300
        assert results[part.id].volume_class == "VC1"
        assert results[part.id].branch is None

    def test_annual_sales_trailing_year_only(self, tenant, branch):
        part = create_part(
            tenant,
            "SKU-TRAIL",
            "Trailing year part",
            timezone.make_aware(datetime(2023, 1, 1)),
        )
        create_sale(tenant, branch, part, 1000, make_date(400))
        create_sale(tenant, branch, part, 10, make_date(30))
        engine = ClassificationEngine(tenant, today=date.today())

        result = engine.classify_part(part, branch=branch)

        assert result.annual_sales == 10
        assert result.volume_class == "VC6"


@pytest.mark.django_db
class TestClassificationResultManager:
    def test_latest_for_part(self, tenant, branch, part):
        engine = ClassificationEngine(tenant)
        result = engine.classify_part(part, branch=branch)

        latest = ClassificationResult.objects.latest_for_part(part, branch=branch)
        assert latest == result

    def test_active_parts_excludes_obsolete(self, tenant, branch):
        obsolete = create_part(
            tenant,
            "SKU-OBS",
            "Obsolete",
            timezone.make_aware(datetime(2022, 1, 1)),
        )
        active = create_part(
            tenant,
            "SKU-ACT",
            "Active",
            timezone.make_aware(datetime(2025, 1, 1)),
        )
        create_sale(tenant, branch, obsolete, 1, make_date(800))
        create_sale(tenant, branch, active, 300, make_date(30))

        engine = ClassificationEngine(tenant)
        engine.classify_part(obsolete, branch=branch)
        engine.classify_part(active, branch=branch)

        active_ids = list(ClassificationResult.objects.active_parts(tenant))
        assert active.id in active_ids
        assert obsolete.id not in active_ids

    def test_stale(self, tenant, branch, part):
        engine = ClassificationEngine(tenant)
        result = engine.classify_part(part, branch=branch)
        result.classified_at = timezone.now() - timedelta(days=40)
        result.save()

        stale = ClassificationResult.objects.stale(days=35)
        assert result in stale


@pytest.mark.django_db
class TestClassifyPartsCommand:
    def test_classify_all(self, tenant, branch):
        part = create_part(
            tenant,
            "SKU-CMD",
            "Command test part",
            timezone.make_aware(datetime(2025, 1, 1)),
        )
        create_sale(tenant, branch, part, 300, make_date(30))

        from django.core.management import call_command

        call_command("classify_parts", tenant=tenant.slug)

        result = ClassificationResult.objects.get(tenant=tenant, part=part)
        assert result.lifecycle_stage == LifecycleStage.ACTIVE
        assert result.volume_class == "VC1"

    def test_classify_single_part(self, tenant, branch):
        part = create_part(
            tenant,
            "SKU-SINGLE",
            "Single part",
            timezone.make_aware(datetime(2025, 1, 1)),
        )
        create_sale(tenant, branch, part, 50, make_date(30))

        from django.core.management import call_command

        call_command("classify_parts", tenant=tenant.slug, part="SKU-SINGLE")

        result = ClassificationResult.objects.get(tenant=tenant, part=part)
        assert result.volume_class == "VC4"

    def test_skips_recent_without_force(self, tenant, branch):
        part = create_part(
            tenant,
            "SKU-RECENT",
            "Recent part",
            timezone.make_aware(datetime(2025, 1, 1)),
        )
        create_sale(tenant, branch, part, 300, make_date(30))
        engine = ClassificationEngine(tenant)
        engine.classify_part(part, branch=branch)

        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        call_command("classify_parts", tenant=tenant.slug, stdout=out)

        assert "skipped" in out.getvalue().lower()
