"""Tests for notification event triggers."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Role, User, UserRole
from apps.branches.models import Branch
from apps.catalog.models import DemandOverride, DemandOverrideType, Part
from apps.core.tests.factories import TenantFactory
from apps.notifications.enums import NotificationChannel, NotificationType
from apps.notifications.models import Notification
from apps.notifications.triggers import (
    notify_cross_coordinator_pending,
    notify_decided,
    notify_escalated,
    notify_new_recommendation,
    notify_override_created,
    notify_override_expired,
    notify_partial_fulfillment,
)
from apps.recommendations.enums import RecommendationState
from apps.recommendations.models import Recommendation


@pytest.fixture
def tenant():
    return TenantFactory()


@pytest.fixture
def manager(tenant):
    return User.objects.create_user(
        email="manager@example.com", password="secret", tenant=tenant
    )


@pytest.fixture
def coordinator(tenant):
    return User.objects.create_user(
        email="coordinator@example.com", password="secret", tenant=tenant
    )


@pytest.fixture
def gerente(tenant):
    user = User.objects.create_user(
        email="gerente@example.com", password="secret", tenant=tenant
    )
    role, _ = Role.objects.get_or_create(name=Role.GERENTE)
    UserRole.objects.create(user=user, role=role)
    return user


@pytest.fixture
def branch(tenant, manager, coordinator):
    return Branch.objects.create(
        tenant=tenant,
        code="SUC-001",
        name="Branch One",
        type="sucursal",
        manager=manager,
        coordinator=coordinator,
    )


@pytest.fixture
def part(tenant):
    return Part.objects.create(
        tenant=tenant,
        internal_sku_code="SKU-001",
        primary_manufacturer_code="MFR-001",
        description="Brake Pads",
    )


@pytest.fixture
def recommendation(branch, part):
    return Recommendation.objects.create(
        tenant=branch.tenant,
        branch=branch,
        part=part,
        state=RecommendationState.PENDING,
        quantity=Decimal("12.00"),
        current_stock=Decimal("15.00"),
        punto_pedido=Decimal("47.00"),
        planning_target=Decimal("37.00"),
        velocity=Decimal("20.00"),
    )


@pytest.fixture
def override_creator(tenant):
    return User.objects.create_user(
        email="creator@example.com", password="secret", tenant=tenant
    )


@pytest.mark.django_db
def test_notify_new_recommendation_creates_email_and_in_app(
    recommendation, manager, coordinator
):
    notify_new_recommendation(recommendation)

    # Two recipients * two channels = 4 notifications.
    assert Notification.objects.filter(
        type=NotificationType.NEW_RECOMMENDATION
    ).count() == 4

    for user in (manager, coordinator):
        assert (
            Notification.objects.filter(
                user=user,
                type=NotificationType.NEW_RECOMMENDATION,
                channel=NotificationChannel.EMAIL,
            ).count()
            == 1
        )
        assert (
            Notification.objects.filter(
                user=user,
                type=NotificationType.NEW_RECOMMENDATION,
                channel=NotificationChannel.IN_APP,
            ).count()
            == 1
        )


@pytest.mark.django_db
def test_notify_escalated_to_coordinator(recommendation, coordinator):
    recommendation.escalation_level = "coordinator"
    recommendation.save(update_fields=["escalation_level"])

    notify_escalated(recommendation, "none", "coordinator")

    notifications = Notification.objects.filter(
        type=NotificationType.RECOMMENDATION_ESCALATED
    )
    assert notifications.count() == 2
    assert notifications.filter(user=coordinator).count() == 2
    email = notifications.get(channel=NotificationChannel.EMAIL, user=coordinator)
    assert "Previous level: none" in email.body
    assert "New level: coordinator" in email.body


@pytest.mark.django_db
def test_notify_escalated_to_gerente(recommendation, gerente, tenant):
    second_gerente = User.objects.create_user(
        email="gerente2@example.com", password="secret", tenant=tenant
    )
    role, _ = Role.objects.get_or_create(name=Role.GERENTE)
    UserRole.objects.create(user=second_gerente, role=role)

    recommendation.escalation_level = "gerente"
    recommendation.save(update_fields=["escalation_level"])

    notify_escalated(recommendation, "coordinator", "gerente")

    notifications = Notification.objects.filter(
        type=NotificationType.RECOMMENDATION_ESCALATED
    )
    assert notifications.count() == 4
    assert notifications.filter(user=gerente).count() == 2
    assert notifications.filter(user=second_gerente).count() == 2


@pytest.mark.django_db
def test_notify_decided_approved(recommendation, manager):
    recommendation.decided_by = manager
    recommendation.state = RecommendationState.APPROVED
    recommendation.save()

    notify_decided(recommendation, manager, "approved")

    notifications = Notification.objects.filter(
        type=NotificationType.RECOMMENDATION_APPROVED
    )
    assert notifications.count() == 2
    email = notifications.get(channel=NotificationChannel.EMAIL)
    assert "Decision: approved" in email.body
    assert manager.email in email.body


@pytest.mark.django_db
def test_notify_decided_rejected(recommendation, coordinator):
    recommendation.decided_by = coordinator
    recommendation.state = RecommendationState.REJECTED
    recommendation.save()

    notify_decided(recommendation, coordinator, "rejected")

    notifications = Notification.objects.filter(
        type=NotificationType.RECOMMENDATION_REJECTED
    )
    assert notifications.count() == 2
    assert notifications.filter(user=coordinator).count() == 2


@pytest.mark.django_db
def test_notify_decided_handled_maps_to_approved_type(recommendation, manager):
    recommendation.decided_by = manager
    recommendation.state = RecommendationState.HANDLED
    recommendation.save()

    notify_decided(recommendation, manager, "handled")

    assert Notification.objects.filter(
        type=NotificationType.RECOMMENDATION_APPROVED
    ).count() == 2


@pytest.mark.django_db
def test_notify_decided_skips_unknown_decision(recommendation, manager):
    notify_decided(recommendation, manager, "invalid")
    assert Notification.objects.count() == 0


@pytest.mark.django_db
def test_notify_partial_fulfillment(recommendation, manager, coordinator, gerente):
    recommendation.is_partial = True
    recommendation.partial_gap = Decimal("7.00")
    recommendation.save()

    notify_partial_fulfillment(recommendation)

    notifications = Notification.objects.filter(
        type=NotificationType.PARTIAL_FULFILLMENT
    )
    # manager + coordinator + gerente, each email + in_app = 6.
    assert notifications.count() == 6
    email = notifications.filter(user=manager, channel=NotificationChannel.EMAIL).first()
    assert "Gap: 7.00 units still needed" in email.body


@pytest.mark.django_db
def test_notify_cross_coordinator_pending_only_gerente(
    recommendation, manager, coordinator, gerente
):
    notify_cross_coordinator_pending(recommendation)

    notifications = Notification.objects.filter(
        type=NotificationType.CROSS_COORDINATOR_PENDING
    )
    # manager + coordinator + gerente, each email + in_app = 6.
    assert notifications.count() == 6
    assert notifications.filter(user=gerente).count() == 2
    assert notifications.filter(user=manager).count() == 2


@pytest.mark.django_db
def test_notify_override_created_only_gerentes(
    tenant, part, override_creator, gerente
):
    override = DemandOverride.objects.create(
        tenant=tenant,
        part=part,
        override_type=DemandOverrideType.PERSISTENT,
        override_value=Decimal("42.0000"),
        created_by=override_creator,
        notes="manual adjustment",
    )

    notify_override_created(override)

    notifications = Notification.objects.filter(
        type=NotificationType.OVERRIDE_CREATED
    )
    assert notifications.count() == 2
    assert notifications.filter(user=gerente).count() == 2
    assert notifications.filter(user=override_creator).count() == 0


@pytest.mark.django_db
def test_notify_override_expired_creator_and_gerentes(
    tenant, part, override_creator, gerente
):
    override = DemandOverride.objects.create(
        tenant=tenant,
        part=part,
        override_type=DemandOverrideType.WITH_EXPIRY,
        override_value=Decimal("42.0000"),
        expires_at=date(2020, 1, 1),
        created_by=override_creator,
    )

    notify_override_expired(override)

    notifications = Notification.objects.filter(
        type=NotificationType.OVERRIDE_EXPIRED
    )
    assert notifications.count() == 4
    assert notifications.filter(user=override_creator).count() == 2
    assert notifications.filter(user=gerente).count() == 2
