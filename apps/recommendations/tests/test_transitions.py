"""Tests for the recommendation state transition service."""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.accounts.models import User
from apps.core.tests.factories import TenantFactory
from apps.inventory.tests.factories import BranchFactory, PartFactory

from ..enums import RecommendationState
from ..models import AlreadyDecidedError, InvalidTransitionError, Recommendation
from ..transitions import transition_recommendation


@pytest.fixture
def tenant():
    return TenantFactory()


@pytest.fixture
def branch(tenant):
    return BranchFactory(tenant=tenant, code="SUC-001")


@pytest.fixture
def part(tenant):
    return PartFactory(tenant=tenant, lead_time_days=10)


@pytest.fixture
def user(tenant):
    return User.objects.create_user(
        email="manager@example.com", password="pw", tenant=tenant
    )


@pytest.fixture
def recommendation(tenant, branch, part):
    return Recommendation.objects.create(
        tenant=tenant,
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
class TestValidTransitions:
    def test_pending_to_approved(self, recommendation, user):
        rec = transition_recommendation(
            recommendation, RecommendationState.APPROVED, user, notes="Approve"
        )

        assert rec.state == RecommendationState.APPROVED
        assert rec.decided_by == user
        assert rec.decision_notes == "Approve"
        assert rec.decided_at is not None

    def test_pending_to_rejected(self, recommendation, user):
        rec = transition_recommendation(
            recommendation, RecommendationState.REJECTED, user
        )

        assert rec.state == RecommendationState.REJECTED

    def test_pending_to_handled(self, recommendation, user):
        rec = transition_recommendation(
            recommendation, RecommendationState.HANDLED, user
        )

        assert rec.state == RecommendationState.HANDLED

    def test_approved_to_ordered(self, recommendation, user):
        transition_recommendation(recommendation, RecommendationState.APPROVED, user)
        rec = transition_recommendation(
            recommendation, RecommendationState.ORDERED, user
        )

        assert rec.state == RecommendationState.ORDERED

    def test_approved_to_handled(self, recommendation, user):
        transition_recommendation(recommendation, RecommendationState.APPROVED, user)
        rec = transition_recommendation(
            recommendation, RecommendationState.HANDLED, user
        )

        assert rec.state == RecommendationState.HANDLED

    def test_rejected_to_pending(self, recommendation, user):
        transition_recommendation(recommendation, RecommendationState.REJECTED, user)
        rec = transition_recommendation(
            recommendation, RecommendationState.PENDING, user
        )

        assert rec.state == RecommendationState.PENDING

    def test_handled_to_pending(self, recommendation, user):
        transition_recommendation(recommendation, RecommendationState.HANDLED, user)
        rec = transition_recommendation(
            recommendation, RecommendationState.PENDING, user
        )

        assert rec.state == RecommendationState.PENDING


@pytest.mark.django_db
class TestInvalidTransitions:
    def test_pending_to_ordered_is_invalid(self, recommendation, user):
        with pytest.raises(InvalidTransitionError):
            transition_recommendation(
                recommendation, RecommendationState.ORDERED, user
            )

    def test_rejected_to_approved_requires_pending_first(self, recommendation, user):
        transition_recommendation(recommendation, RecommendationState.REJECTED, user)

        with pytest.raises(InvalidTransitionError):
            transition_recommendation(
                recommendation, RecommendationState.APPROVED, user
            )

    def test_ordered_is_terminal(self, recommendation, user):
        transition_recommendation(recommendation, RecommendationState.APPROVED, user)
        transition_recommendation(recommendation, RecommendationState.ORDERED, user)

        with pytest.raises(AlreadyDecidedError):
            transition_recommendation(
                recommendation, RecommendationState.HANDLED, user
            )

    def test_approved_to_pending_raises_already_decided(self, recommendation, user):
        transition_recommendation(recommendation, RecommendationState.APPROVED, user)

        with pytest.raises(AlreadyDecidedError):
            transition_recommendation(
                recommendation, RecommendationState.PENDING, user
            )

    def test_invalid_transition_message(self, recommendation, user):
        transition_recommendation(recommendation, RecommendationState.REJECTED, user)

        with pytest.raises(InvalidTransitionError, match="Cannot transition"):
            transition_recommendation(
                recommendation, RecommendationState.ORDERED, user
            )
