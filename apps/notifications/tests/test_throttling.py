"""Tests for notification throttling and digest helpers."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.core.tests.factories import TenantFactory
from apps.notifications.enums import NotificationChannel, NotificationType
from apps.notifications.models import Notification
from apps.notifications.throttling import (
    digest_pending_notifications,
    should_send_email_now,
)


@pytest.fixture
def tenant():
    return TenantFactory()


@pytest.fixture
def user(tenant):
    return User.objects.create_user(
        email="user@example.com", password="secret", tenant=tenant
    )


@pytest.mark.django_db
def test_should_send_email_now_returns_true_when_no_recent(user):
    assert should_send_email_now(NotificationType.NEW_RECOMMENDATION, user) is True


@pytest.mark.django_db
def test_should_send_email_now_returns_false_when_recent(user):
    Notification.objects.create(
        tenant=user.tenant,
        user=user,
        type=NotificationType.NEW_RECOMMENDATION,
        channel=NotificationChannel.EMAIL,
        subject="Recent",
        body="Body",
        sent_at=timezone.now() - timedelta(minutes=30),
    )

    assert should_send_email_now(NotificationType.NEW_RECOMMENDATION, user) is False


@pytest.mark.django_db
def test_should_send_email_now_returns_true_after_one_hour(user):
    Notification.objects.create(
        tenant=user.tenant,
        user=user,
        type=NotificationType.NEW_RECOMMENDATION,
        channel=NotificationChannel.EMAIL,
        subject="Old",
        body="Body",
        sent_at=timezone.now() - timedelta(hours=2),
    )

    assert should_send_email_now(NotificationType.NEW_RECOMMENDATION, user) is True


@pytest.mark.django_db
def test_should_send_email_now_per_type(user):
    Notification.objects.create(
        tenant=user.tenant,
        user=user,
        type=NotificationType.NEW_RECOMMENDATION,
        channel=NotificationChannel.EMAIL,
        subject="Recent",
        body="Body",
        sent_at=timezone.now() - timedelta(minutes=30),
    )

    assert should_send_email_now(NotificationType.PARTIAL_FULFILLMENT, user) is True


@pytest.mark.django_db
def test_digest_pending_notifications_returns_none_when_empty(user):
    assert digest_pending_notifications(user, NotificationType.NEW_RECOMMENDATION) is None


@pytest.mark.django_db
def test_digest_pending_notifications_combines_multiple(user):
    Notification.objects.create(
        tenant=user.tenant,
        user=user,
        type=NotificationType.NEW_RECOMMENDATION,
        channel=NotificationChannel.EMAIL,
        subject="First recommendation",
        body="Body one",
    )
    Notification.objects.create(
        tenant=user.tenant,
        user=user,
        type=NotificationType.NEW_RECOMMENDATION,
        channel=NotificationChannel.EMAIL,
        subject="Second recommendation",
        body="Body two",
    )

    digest = digest_pending_notifications(user, NotificationType.NEW_RECOMMENDATION)

    assert digest is not None
    assert digest["count"] == 2
    assert "and 1 more" in digest["subject"]
    assert "Body one" in digest["body"]
    assert "Body two" in digest["body"]
    assert "---" in digest["body"]


@pytest.mark.django_db
def test_digest_pending_notifications_only_email_channel(user):
    Notification.objects.create(
        tenant=user.tenant,
        user=user,
        type=NotificationType.NEW_RECOMMENDATION,
        channel=NotificationChannel.IN_APP,
        subject="In-app only",
        body="Body",
    )

    assert digest_pending_notifications(user, NotificationType.NEW_RECOMMENDATION) is None
