"""Tests for demand overrides (WU-13)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.accounts.models import User
from apps.catalog.models import DemandOverride, DemandOverrideType
from apps.catalog.overrides import (
    OVERRIDE_TYPE_DESCRIPTIONS,
    OverrideService,
    get_override_prompt_message,
)
from apps.catalog.planning import PlanningCalculator
from apps.core.tests.factories import TenantFactory
from apps.inventory.tests.factories import BranchFactory, PartFactory


@pytest.fixture
def tenant():
    return TenantFactory()


@pytest.fixture
def part(tenant):
    return PartFactory(tenant=tenant, lead_time_days=10)


@pytest.fixture
def branch(tenant):
    return BranchFactory(tenant=tenant, code="SUC-001")


@pytest.fixture
def user(tenant):
    return User.objects.create_user(email="manager@example.com", tenant=tenant)


@pytest.fixture
def service(tenant):
    return OverrideService(tenant)


@pytest.mark.django_db
class TestCreateOverrides:
    def test_create_persistent_override(self, service, part, branch, user):
        override = service.create_override(
            part=part,
            branch=branch,
            override_value=Decimal("25.0000"),
            override_type=DemandOverrideType.PERSISTENT,
            user=user,
            notes="Promotional season",
        )

        assert override.override_type == DemandOverrideType.PERSISTENT
        assert override.override_value == Decimal("25.0000")
        assert override.branch == branch
        assert override.created_by == user
        assert override.notes == "Promotional season"

    def test_create_per_run_override(self, service, part, branch, user):
        override = service.create_override(
            part=part,
            branch=branch,
            override_value=Decimal("40.0000"),
            override_type=DemandOverrideType.PER_RUN,
            user=user,
            run_id="run-2026-08-14",
        )

        assert override.override_type == DemandOverrideType.PER_RUN
        assert override.run_id == "run-2026-08-14"

    def test_create_with_expiry_override(self, service, part, branch, user):
        expires = date.today() + timedelta(days=7)
        override = service.create_override(
            part=part,
            branch=branch,
            override_value=Decimal("15.0000"),
            override_type=DemandOverrideType.WITH_EXPIRY,
            user=user,
            expires_at=expires,
        )

        assert override.override_type == DemandOverrideType.WITH_EXPIRY
        assert override.expires_at == expires

    def test_with_expiry_requires_expires_at(self, service, part, branch, user):
        with pytest.raises(ValueError, match="expires_at"):
            service.create_override(
                part=part,
                branch=branch,
                override_value=Decimal("15.0000"),
                override_type=DemandOverrideType.WITH_EXPIRY,
                user=user,
            )

    def test_per_run_requires_run_id(self, service, part, branch, user):
        with pytest.raises(ValueError, match="run_id"):
            service.create_override(
                part=part,
                branch=branch,
                override_value=Decimal("15.0000"),
                override_type=DemandOverrideType.PER_RUN,
                user=user,
            )

    def test_negative_override_value_rejected(self, service, part, branch, user):
        with pytest.raises(ValueError, match="negative"):
            service.create_override(
                part=part,
                branch=branch,
                override_value=Decimal("-5.0000"),
                override_type=DemandOverrideType.PERSISTENT,
                user=user,
            )


@pytest.mark.django_db
class TestPersistentUniqueness:
    def test_persistent_override_uniqueness(self, service, part, branch, user):
        first = service.create_override(
            part=part,
            branch=branch,
            override_value=Decimal("20.0000"),
            override_type=DemandOverrideType.PERSISTENT,
            user=user,
        )

        second = service.create_override(
            part=part,
            branch=branch,
            override_value=Decimal("30.0000"),
            override_type=DemandOverrideType.PERSISTENT,
            user=user,
        )

        assert first.id == second.id
        assert second.override_value == Decimal("30.0000")
        assert DemandOverride.objects.filter(
            tenant=part.tenant,
            part=part,
            branch=branch,
            override_type=DemandOverrideType.PERSISTENT,
        ).count() == 1


@pytest.mark.django_db
class TestActiveOverridePriority:
    def test_active_override_priority(self, service, part, branch, user):
        today = date.today()
        persistent = service.create_override(
            part=part,
            branch=branch,
            override_value=Decimal("10.0000"),
            override_type=DemandOverrideType.PERSISTENT,
            user=user,
        )
        service.create_override(
            part=part,
            branch=branch,
            override_value=Decimal("5.0000"),
            override_type=DemandOverrideType.PER_RUN,
            user=user,
            run_id="run-today",
        )
        with_expiry = service.create_override(
            part=part,
            branch=branch,
            override_value=Decimal("20.0000"),
            override_type=DemandOverrideType.WITH_EXPIRY,
            user=user,
            expires_at=today + timedelta(days=5),
        )

        active = service.get_active_override(part, branch, run_date=today)
        assert active is not None
        assert active.id == with_expiry.id

        # After the with-expiry override expires, persistent wins.
        active_later = service.get_active_override(
            part, branch, run_date=today + timedelta(days=10)
        )
        assert active_later is not None
        assert active_later.id == persistent.id

    def test_expired_override_ignored(self, service, part, branch, user):
        today = date.today()
        service.create_override(
            part=part,
            branch=branch,
            override_value=Decimal("20.0000"),
            override_type=DemandOverrideType.WITH_EXPIRY,
            user=user,
            expires_at=today - timedelta(days=1),
        )

        active = service.get_active_override(part, branch, run_date=today)
        assert active is None

    def test_per_run_only_applies_to_specific_run(self, service, part, branch, user):
        service.create_override(
            part=part,
            branch=branch,
            override_value=Decimal("8.0000"),
            override_type=DemandOverrideType.PER_RUN,
            user=user,
            run_id="run-a",
        )

        assert (
            service.get_active_override(part, branch, run_id="run-a") is not None
        )
        assert service.get_active_override(part, branch, run_id="run-b") is None
        assert service.get_active_override(part, branch) is None


@pytest.mark.django_db
class TestPlanningIntegration:
    def test_planning_uses_override(self, service, part, branch, user):
        service.create_override(
            part=part,
            branch=branch,
            override_value=Decimal("30.0000"),
            override_type=DemandOverrideType.PERSISTENT,
            user=user,
        )

        calculator = PlanningCalculator(part.tenant)
        result = calculator.calculate_for_part(
            part=part,
            branch=branch,
            stock_disponible=0.0,
            stock_en_transito=0.0,
            period_days=30,
            security_days=0,
        )

        # velocity should come from the override, not from calculated (zero) velocity.
        assert result.velocity == pytest.approx(30.0)
        assert result.planning_target == pytest.approx(40.0, abs=0.01)

    def test_planning_falls_back_to_velocity_when_no_override(
        self, service, part, branch, user
    ):
        calculator = PlanningCalculator(part.tenant)
        result = calculator.calculate_for_part(
            part=part,
            branch=branch,
            velocity=12.0,
            stock_disponible=0.0,
            stock_en_transito=0.0,
            period_days=30,
            security_days=0,
        )

        assert result.velocity == pytest.approx(12.0)


@pytest.mark.django_db
class TestPromptMessage:
    def test_override_prompt_message(self):
        message = get_override_prompt_message()

        assert "Persistent" in message
        assert "Per-run" in message
        assert "With expiry" in message
        assert OVERRIDE_TYPE_DESCRIPTIONS["persistent"] in message
        assert OVERRIDE_TYPE_DESCRIPTIONS["per_run"] in message
        assert OVERRIDE_TYPE_DESCRIPTIONS["with_expiry"] in message


@pytest.mark.django_db
class TestCleanup:
    def test_cleanup_expired_overrides(self, service, part, branch, user):
        today = date.today()
        expired = service.create_override(
            part=part,
            branch=branch,
            override_value=Decimal("20.0000"),
            override_type=DemandOverrideType.WITH_EXPIRY,
            user=user,
            expires_at=today - timedelta(days=2),
        )
        service.create_override(
            part=part,
            branch=branch,
            override_value=Decimal("25.0000"),
            override_type=DemandOverrideType.WITH_EXPIRY,
            user=user,
            expires_at=today + timedelta(days=2),
        )

        deleted = service.cleanup_expired_overrides()

        assert deleted == 1
        assert not DemandOverride.objects.filter(id=expired.id).exists()


@pytest.mark.django_db
class TestTenantIsolation:
    def test_override_is_isolated_by_tenant(self, service, part, branch, user):
        other_tenant = TenantFactory()
        other_branch = BranchFactory(tenant=other_tenant, code="OTHER-001")
        other_user = User.objects.create_user(
            email="other@example.com", tenant=other_tenant
        )
        other_part = PartFactory(tenant=other_tenant, internal_sku_code="OTHER-SKU")

        service.create_override(
            part=part,
            branch=branch,
            override_value=Decimal("10.0000"),
            override_type=DemandOverrideType.PERSISTENT,
            user=user,
        )

        other_service = OverrideService(other_tenant)
        other_service.create_override(
            part=other_part,
            branch=other_branch,
            override_value=Decimal("99.0000"),
            override_type=DemandOverrideType.PERSISTENT,
            user=other_user,
        )

        active = service.get_active_override(part, branch)
        assert active is not None
        assert active.override_value == Decimal("10.0000")

        other_active = other_service.get_active_override(other_part, other_branch)
        assert other_active is not None
        assert other_active.override_value == Decimal("99.0000")
