"""Tests for notification recipient resolution and rendering."""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.accounts.models import Role, User, UserRole
from apps.branches.models import Branch
from apps.catalog.models import Part
from apps.core.tests.factories import TenantFactory
from apps.recommendations.enums import RecommendationState
from apps.recommendations.models import Recommendation

from ..recipients import (
    SUBJECT_TEMPLATES,
    get_recipients_for_recommendation,
    render_notification_body,
)


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


@pytest.mark.django_db
def test_new_recommendation_returns_manager_and_coordinator(
    recommendation, manager, coordinator
):
    recipients = get_recipients_for_recommendation(
        recommendation, "new_recommendation"
    )
    assert set(recipients) == {manager, coordinator}


@pytest.mark.django_db
def test_partial_fulfillment_includes_gerente(
    recommendation, manager, coordinator, gerente
):
    recipients = get_recipients_for_recommendation(
        recommendation, "partial_fulfillment"
    )
    assert set(recipients) == {manager, coordinator, gerente}


@pytest.mark.django_db
def test_cross_coordinator_pending_includes_gerente(
    recommendation, manager, coordinator, gerente
):
    recipients = get_recipients_for_recommendation(
        recommendation, "cross_coordinator_pending"
    )
    assert set(recipients) == {manager, coordinator, gerente}


@pytest.mark.django_db
def test_escalated_to_coordinator_returns_coordinator(recommendation, coordinator):
    recipients = get_recipients_for_recommendation(
        recommendation, "escalated_to_coordinator"
    )
    assert recipients == [coordinator]


@pytest.mark.django_db
def test_escalated_to_coordinator_empty_when_no_coordinator(recommendation):
    recommendation.branch.coordinator = None
    recommendation.branch.save(update_fields=["coordinator"])
    recipients = get_recipients_for_recommendation(
        recommendation, "escalated_to_coordinator"
    )
    assert recipients == []


@pytest.mark.django_db
def test_escalated_to_gerente_returns_all_gerentes(
    recommendation, gerente, tenant
):
    second_gerente = User.objects.create_user(
        email="gerente2@example.com", password="secret", tenant=tenant
    )
    role, _ = Role.objects.get_or_create(name=Role.GERENTE)
    UserRole.objects.create(user=second_gerente, role=role)

    recipients = get_recipients_for_recommendation(
        recommendation, "escalated_to_gerente"
    )
    assert set(recipients) == {gerente, second_gerente}


@pytest.mark.django_db
def test_approved_returns_decided_by(recommendation, manager):
    recommendation.decided_by = manager
    recommendation.state = RecommendationState.APPROVED
    recommendation.save()

    recipients = get_recipients_for_recommendation(recommendation, "approved")
    assert recipients == [manager]


@pytest.mark.django_db
def test_rejected_returns_decided_by(recommendation, coordinator):
    recommendation.decided_by = coordinator
    recommendation.state = RecommendationState.REJECTED
    recommendation.save()

    recipients = get_recipients_for_recommendation(recommendation, "rejected")
    assert recipients == [coordinator]


@pytest.mark.django_db
def test_approved_empty_when_no_decided_by(recommendation):
    recommendation.decided_by = None
    recommendation.save()
    recipients = get_recipients_for_recommendation(recommendation, "approved")
    assert recipients == []


@pytest.mark.django_db
def test_unknown_event_type_returns_empty(recommendation):
    recipients = get_recipients_for_recommendation(recommendation, "unknown_event")
    assert recipients == []


@pytest.mark.django_db
def test_deduplication_when_manager_is_also_gerente(
    recommendation, manager, coordinator, gerente
):
    role, _ = Role.objects.get_or_create(name=Role.GERENTE)
    UserRole.objects.create(user=manager, role=role)

    recipients = get_recipients_for_recommendation(
        recommendation, "partial_fulfillment"
    )
    assert len(recipients) == 3
    assert set(recipients) == {manager, coordinator, gerente}


@pytest.mark.django_db
def test_render_notification_body(recommendation):
    body = render_notification_body(recommendation, "new_recommendation")
    assert "Event: new_recommendation" in body
    assert "Part: SKU-001 (Brake Pads)" in body
    assert "Branch: SUC-001 (Branch One)" in body
    assert "Quantity: 12" in body
    assert f"See: /recommendations/{recommendation.id}/" in body


@pytest.mark.django_db
def test_subject_templates_render_for_event_types(recommendation):
    for event_type in SUBJECT_TEMPLATES:
        subject = SUBJECT_TEMPLATES[event_type].format(
            part_code=recommendation.part.internal_sku_code,
            gap=5,
        )
        assert recommendation.part.internal_sku_code in subject
        assert len(subject) > 0
