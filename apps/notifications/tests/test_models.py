"""Tests for the Notification model."""

from __future__ import annotations

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.core.tests.factories import TenantFactory

from ..enums import NotificationChannel, NotificationType
from ..models import Notification


@pytest.fixture
def tenant():
    return TenantFactory()


@pytest.fixture
def user(tenant):
    return User.objects.create_user(
        email="user@example.com", password="secret", tenant=tenant
    )


@pytest.mark.django_db
def test_notification_creation(user, tenant):
    notification = Notification.objects.create(
        tenant=tenant,
        user=user,
        type=NotificationType.NEW_RECOMMENDATION,
        channel=NotificationChannel.IN_APP,
        subject="Test subject",
        body="Test body",
        related_object_type="recommendation",
    )
    assert notification.user == user
    assert notification.tenant == tenant
    assert notification.type == NotificationType.NEW_RECOMMENDATION
    assert notification.channel == NotificationChannel.IN_APP
    assert notification.subject == "Test subject"
    assert notification.body == "Test body"
    assert notification.related_object_type == "recommendation"
    assert notification.read_at is None
    assert notification.sent_at is None
    assert notification.error == ""


@pytest.mark.django_db
def test_mark_as_read_sets_read_at(user, tenant):
    notification = Notification.objects.create(
        tenant=tenant,
        user=user,
        type=NotificationType.NEW_RECOMMENDATION,
        channel=NotificationChannel.IN_APP,
        subject="Test",
        body="Body",
    )
    before = timezone.now()
    notification.mark_as_read()
    after = timezone.now()

    assert notification.read_at is not None
    assert before <= notification.read_at <= after

    # Idempotent: second call should not change read_at
    first_read_at = notification.read_at
    notification.mark_as_read()
    assert notification.read_at == first_read_at


@pytest.mark.django_db
def test_str_representation(user, tenant):
    unread = Notification.objects.create(
        tenant=tenant,
        user=user,
        type=NotificationType.NEW_RECOMMENDATION,
        channel=NotificationChannel.IN_APP,
        subject="Test",
        body="Body",
    )
    assert str(unread) == f"new_recommendation for {user.id} (unread)"

    read = Notification.objects.create(
        tenant=tenant,
        user=user,
        type=NotificationType.RECOMMENDATION_ESCALATED,
        channel=NotificationChannel.EMAIL,
        subject="Test",
        body="Body",
        read_at=timezone.now(),
    )
    assert str(read) == f"recommendation_escalated for {user.id} (read)"


@pytest.mark.django_db
def test_notification_type_choices():
    values = {choice[0] for choice in NotificationType.choices}
    expected = {
        "new_recommendation",
        "recommendation_escalated",
        "recommendation_approved",
        "recommendation_rejected",
        "partial_fulfillment",
        "cross_coordinator_pending",
        "override_created",
        "override_expired",
    }
    assert values == expected


@pytest.mark.django_db
def test_notification_channel_choices():
    values = {choice[0] for choice in NotificationChannel.choices}
    assert values == {"email", "in_app"}
