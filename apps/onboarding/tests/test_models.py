from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.tests.factories import TenantFactory

from ..models import OnboardingState


pytestmark = pytest.mark.django_db


class TestOnboardingStateModel:
    def test_create_onboarding_state(self):
        tenant = TenantFactory()
        state = OnboardingState.objects.create(tenant=tenant, status="not_started")
        assert state.status == "not_started"
        assert state.dms_adapter_type == ""
        assert state.dms_config == {}
        assert state.is_complete() is False

    def test_is_complete_when_live(self):
        tenant = TenantFactory()
        state = OnboardingState.objects.create(tenant=tenant, status="live")
        assert state.is_complete() is True

    def test_status_transitions(self):
        tenant = TenantFactory()
        state = OnboardingState.objects.create(tenant=tenant, status="dms_connecting")
        assert state.status == "dms_connecting"
        state.status = "dms_connected"
        state.save()
        assert state.status == "dms_connected"

    def test_days_since_start(self):
        tenant = TenantFactory()
        state = OnboardingState.objects.create(tenant=tenant)
        assert state.days_since_start() == 0

    def test_is_overdue_after_28_days_without_go_live(self):
        tenant = TenantFactory()
        state = OnboardingState.objects.create(tenant=tenant, status="not_started")
        # Simulate an old creation date by updating the field directly.
        state.created_at = timezone.now() - timedelta(days=30)
        state.save()
        assert state.is_overdue() is True

    def test_is_not_overdue_when_live(self):
        tenant = TenantFactory()
        state = OnboardingState.objects.create(tenant=tenant, status="live")
        state.created_at = timezone.now() - timedelta(days=30)
        state.save()
        assert state.is_overdue() is False
