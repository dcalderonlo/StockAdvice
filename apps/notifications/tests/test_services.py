"""Tests for the NotificationService."""

from __future__ import annotations

import pytest
from django.core import mail

from apps.accounts.models import User
from apps.core.tests.factories import TenantFactory

from ..enums import NotificationChannel, NotificationType
from ..models import Notification
from ..services import NotificationService


@pytest.fixture
def tenant():
    return TenantFactory()


@pytest.fixture
def user(tenant):
    return User.objects.create_user(
        email="user@example.com", password="secret", tenant=tenant
    )


@pytest.fixture
def service(tenant):
    return NotificationService(tenant)


@pytest.mark.django_db
def test_send_email_notification_creates_record_and_sends(user, service):
    notification = service.send_email_notification(
        user=user,
        notification_type=NotificationType.NEW_RECOMMENDATION,
        subject="New recommendation",
        body="A new recommendation is available.",
        related_object_type="recommendation",
    )

    assert notification.channel == NotificationChannel.EMAIL
    assert notification.type == NotificationType.NEW_RECOMMENDATION
    assert notification.user == user
    assert notification.sent_at is not None
    assert notification.error == ""

    assert len(mail.outbox) == 1
    sent = mail.outbox[0]
    assert sent.subject == "New recommendation"
    assert sent.body == "A new recommendation is available."
    assert sent.to == [user.email]


@pytest.mark.django_db
def test_send_email_notification_records_error_on_failure(user, service, monkeypatch):
    def _broken_send(*args, **kwargs):
        raise RuntimeError("SMTP connection refused")

    monkeypatch.setattr(
        "apps.notifications.services.send_mail",
        _broken_send,
    )
    notification = service.send_email_notification(
        user=user,
        notification_type=NotificationType.NEW_RECOMMENDATION,
        subject="New recommendation",
        body="Body",
    )

    assert notification.sent_at is None
    assert "SMTP connection refused" in notification.error


@pytest.mark.django_db
def test_send_in_app_notification_creates_record_only(user, service):
    notification = service.send_in_app_notification(
        user=user,
        notification_type=NotificationType.PARTIAL_FULFILLMENT,
        subject="Partial fulfillment",
        body="Only part of the quantity is available.",
    )

    assert notification.channel == NotificationChannel.IN_APP
    assert notification.type == NotificationType.PARTIAL_FULFILLMENT
    assert notification.sent_at is None
    assert notification.error == ""
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_send_notification_creates_both_channels(user, service):
    results = service.send_notification(
        user=user,
        notification_type=NotificationType.CROSS_COORDINATOR_PENDING,
        subject="Cross-coordinator pending",
        body="Pending approval.",
    )

    assert len(results) == 2
    channels = {n.channel for n in results}
    assert channels == {NotificationChannel.EMAIL, NotificationChannel.IN_APP}
    assert Notification.objects.filter(user=user).count() == 2
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_mark_as_read(user, service):
    notification = service.send_in_app_notification(
        user=user,
        notification_type=NotificationType.NEW_RECOMMENDATION,
        subject="Test",
        body="Body",
    )
    assert notification.read_at is None

    result = service.mark_as_read(notification.id)
    assert result is True

    notification.refresh_from_db()
    assert notification.read_at is not None

    # Idempotent
    result = service.mark_as_read(notification.id)
    assert result is True


@pytest.mark.django_db
def test_mark_as_read_missing_notification_returns_false(service):
    from uuid import uuid4

    assert service.mark_as_read(uuid4()) is False


@pytest.mark.django_db
def test_get_unread_for_user_filters_correctly(user, service, tenant):
    other_user = User.objects.create_user(
        email="other@example.com", password="secret", tenant=tenant
    )

    unread_in_app = service.send_in_app_notification(
        user=user,
        notification_type=NotificationType.NEW_RECOMMENDATION,
        subject="Unread",
        body="Body",
    )
    read_in_app = service.send_in_app_notification(
        user=user,
        notification_type=NotificationType.NEW_RECOMMENDATION,
        subject="Read",
        body="Body",
    )
    read_in_app.mark_as_read()

    service.send_email_notification(
        user=user,
        notification_type=NotificationType.NEW_RECOMMENDATION,
        subject="Email",
        body="Body",
    )

    service.send_in_app_notification(
        user=other_user,
        notification_type=NotificationType.NEW_RECOMMENDATION,
        subject="Other user",
        body="Body",
    )

    unread = list(service.get_unread_for_user(user))
    assert len(unread) == 1
    assert unread[0].id == unread_in_app.id
