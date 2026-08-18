"""Tests for the scheduled background jobs."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model

from apps.core.tests.factories import TenantFactory
from apps.inventory.tests.factories import BranchFactory
from apps.notifications.enums import NotificationChannel, NotificationType
from apps.notifications.models import Notification

from ..jobs import (
    scheduled_classification_pass,
    scheduled_notification_dispatch,
    scheduled_override_cleanup,
    scheduled_replenishment_run,
)
from ..models import ScheduledRun

User = get_user_model()


@pytest.mark.django_db
@patch("apps.scheduling.jobs.RecommendationGenerator")
def test_scheduled_replenishment_run_is_idempotent(generator_class):
    branch = BranchFactory()
    generator = MagicMock()
    generator.generate_for_branch.return_value = [object(), object()]
    generator_class.return_value = generator

    count = scheduled_replenishment_run(str(branch.id), "2026-08-17")
    assert count == 2
    assert ScheduledRun.objects.count() == 1

    second_count = scheduled_replenishment_run(str(branch.id), "2026-08-17")
    assert second_count == 2
    assert generator.generate_for_branch.call_count == 1
    assert ScheduledRun.objects.count() == 1


@pytest.mark.django_db
@patch("apps.scheduling.jobs.ClassificationEngine")
def test_scheduled_classification_pass_is_idempotent(engine_class):
    tenant = TenantFactory()
    engine = MagicMock()
    engine.classify_tenant.return_value = {f"part-{i}": object() for i in range(3)}
    engine_class.return_value = engine

    count = scheduled_classification_pass(str(tenant.id), "2026-08")
    assert count == 3
    assert ScheduledRun.objects.count() == 1

    second_count = scheduled_classification_pass(str(tenant.id), "2026-08")
    assert second_count == 3
    assert engine.classify_tenant.call_count == 1
    assert ScheduledRun.objects.count() == 1


@pytest.mark.django_db
@patch("apps.scheduling.jobs.send_mail")
def test_scheduled_notification_dispatch_sends_pending_email(send_mail):
    tenant = TenantFactory()
    user = User.objects.create_user(email="test@example.com", password="password")
    notification = Notification.objects.create(
        tenant=tenant,
        user=user,
        type=NotificationType.NEW_RECOMMENDATION,
        channel=NotificationChannel.EMAIL,
        subject="Test subject",
        body="Test body",
    )

    sent = scheduled_notification_dispatch()

    assert sent == 1
    send_mail.assert_called_once()
    notification.refresh_from_db()
    assert notification.sent_at is not None


@pytest.mark.django_db
@patch("apps.scheduling.jobs.send_mail")
def test_scheduled_notification_dispatch_records_errors(send_mail):
    tenant = TenantFactory()
    user = User.objects.create_user(email="fail@example.com", password="password")
    notification = Notification.objects.create(
        tenant=tenant,
        user=user,
        type=NotificationType.NEW_RECOMMENDATION,
        channel=NotificationChannel.EMAIL,
        subject="Fail",
        body="Body",
    )
    send_mail.side_effect = RuntimeError("SMTP down")

    sent = scheduled_notification_dispatch()

    assert sent == 0
    notification.refresh_from_db()
    assert notification.sent_at is None
    assert "SMTP down" in notification.error


@pytest.mark.django_db
@patch("apps.scheduling.jobs.OverrideService")
def test_scheduled_override_cleanup_calls_service(override_service_class):
    tenant = TenantFactory()
    service = MagicMock()
    service.cleanup_expired_overrides.return_value = 2
    override_service_class.return_value = service

    total = scheduled_override_cleanup()

    assert total == 2
    override_service_class.assert_called_once_with(tenant)
    service.cleanup_expired_overrides.assert_called_once()
