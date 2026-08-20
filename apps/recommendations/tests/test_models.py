"""Tests for the Recommendation model and state machine."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import User
from apps.core.tests.factories import TenantFactory
from apps.inventory.models import StockMovement, StockMovementType
from apps.inventory.tests.factories import BranchFactory, PartFactory

from ..enums import RecommendationState
from ..models import InvalidTransitionError, Recommendation


def create_sales(tenant, branch, part, quantities: list[float], today: date | None = None):
    """Create SALE movements ordered oldest month to newest month."""
    today = today or date.today()
    sequence = _month_sequence(today, len(quantities))
    for (year, month), qty in zip(sequence, quantities):
        if qty == 0:
            continue
        StockMovement.objects.create(
            tenant=tenant,
            branch=branch,
            part=part,
            movement_type=StockMovementType.SALE,
            quantity=Decimal(str(-qty)),
            movement_date=date(year, month, 15),
        )


def _add_months(year: int, month: int, months: int) -> tuple[int, int]:
    month += months
    while month <= 0:
        year -= 1
        month += 12
    while month > 12:
        year += 1
        month -= 12
    return year, month


def _month_sequence(today: date, months: int) -> list[tuple[int, int]]:
    sequence: list[tuple[int, int]] = []
    for offset in range(months - 1, -1, -1):
        sequence.append(_add_months(today.year, today.month, -offset))
    return sequence


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
        explanation="Stock 15.0 ≤ PP 47.0. Recommended 12.0 units.",
        classification="VC3 active",
        velocity=Decimal("20.00"),
    )


@pytest.mark.django_db
class TestRecommendationStateMachine:
    def test_is_pending(self, recommendation):
        assert recommendation.is_pending() is True
        assert recommendation.is_decided() is False

    def test_is_decided(self, recommendation, user):
        recommendation.transition_to(RecommendationState.APPROVED, user)
        assert recommendation.is_pending() is False
        assert recommendation.is_decided() is True

    def test_can_transition_to_valid_targets(self, recommendation):
        assert recommendation.can_transition_to(RecommendationState.APPROVED) is True
        assert recommendation.can_transition_to(RecommendationState.REJECTED) is True
        assert recommendation.can_transition_to(RecommendationState.HANDLED) is True
        assert recommendation.can_transition_to(RecommendationState.PENDING) is False

    def test_cannot_transition_to_ordered_from_pending(self, recommendation):
        assert recommendation.can_transition_to(RecommendationState.ORDERED) is False

    def test_approved_can_transition_to_ordered_and_handled(self, recommendation, user):
        recommendation.transition_to(RecommendationState.APPROVED, user)
        assert recommendation.can_transition_to(RecommendationState.ORDERED) is True
        assert recommendation.can_transition_to(RecommendationState.HANDLED) is True
        assert recommendation.can_transition_to(RecommendationState.REJECTED) is False

    def test_rejected_can_reopen_to_pending(self, recommendation, user):
        recommendation.transition_to(RecommendationState.REJECTED, user)
        assert recommendation.can_transition_to(RecommendationState.PENDING) is True

    def test_handled_can_reopen_to_pending(self, recommendation, user):
        recommendation.transition_to(RecommendationState.HANDLED, user)
        assert recommendation.can_transition_to(RecommendationState.PENDING) is True

    def test_ordered_is_terminal(self, recommendation, user):
        recommendation.transition_to(RecommendationState.APPROVED, user)
        recommendation.transition_to(RecommendationState.ORDERED, user)
        assert recommendation.can_transition_to(RecommendationState.PENDING) is False
        assert recommendation.can_transition_to(RecommendationState.HANDLED) is False

    def test_transition_to_updates_audit_fields(self, recommendation, user):
        recommendation.transition_to(RecommendationState.APPROVED, user, notes="Looks good")

        assert recommendation.state == RecommendationState.APPROVED
        assert recommendation.decided_by == user
        assert recommendation.decided_at is not None
        assert recommendation.decision_notes == "Looks good"

    def test_invalid_transition_raises(self, recommendation, user):
        recommendation.transition_to(RecommendationState.REJECTED, user)

        with pytest.raises(InvalidTransitionError):
            recommendation.transition_to(RecommendationState.APPROVED, user)

    def test_ordered_transition_is_terminal(self, recommendation, user):
        recommendation.transition_to(RecommendationState.APPROVED, user)
        recommendation.transition_to(RecommendationState.ORDERED, user)

        with pytest.raises(InvalidTransitionError):
            recommendation.transition_to(RecommendationState.HANDLED, user)


@pytest.mark.django_db
class TestRecommendationSnapshotFields:
    def test_snapshot_values_preserved(self, tenant, branch, part):
        rec = Recommendation.objects.create(
            tenant=tenant,
            branch=branch,
            part=part,
            quantity=Decimal("12.00"),
            current_stock=Decimal("15.00"),
            punto_pedido=Decimal("47.00"),
            planning_target=Decimal("37.00"),
            velocity=Decimal("20.00"),
            classification="VC3 active",
        )

        assert rec.current_stock == Decimal("15.00")
        assert rec.punto_pedido == Decimal("47.00")
        assert rec.planning_target == Decimal("37.00")
        assert rec.velocity == Decimal("20.00")

    def test_unique_pending_constraint(self, tenant, branch, part):
        Recommendation.objects.create(
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

        with pytest.raises(Exception):  # IntegrityError or similar
            Recommendation.objects.create(
                tenant=tenant,
                branch=branch,
                part=part,
                state=RecommendationState.PENDING,
                quantity=Decimal("5.00"),
                current_stock=Decimal("15.00"),
                punto_pedido=Decimal("47.00"),
                planning_target=Decimal("37.00"),
                velocity=Decimal("20.00"),
            )

    def test_different_states_allow_multiple_rows(self, tenant, branch, part):
        Recommendation.objects.create(
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

        # A decided recommendation for the same part should be allowed.
        decided = Recommendation.objects.create(
            tenant=tenant,
            branch=branch,
            part=part,
            state=RecommendationState.REJECTED,
            quantity=Decimal("12.00"),
            current_stock=Decimal("15.00"),
            punto_pedido=Decimal("47.00"),
            planning_target=Decimal("37.00"),
            velocity=Decimal("20.00"),
        )

        assert decided.state == RecommendationState.REJECTED

    def test_coverage_days_after_fulfillment(self, recommendation):
        # velocity=20, current_stock=15, quantity=12 -> projected=27
        # coverage = 27/20 * 30 = 40.5 days
        assert recommendation.coverage_days_after_fulfillment == Decimal("40.50")

    def test_coverage_days_zero_when_no_velocity(self, tenant, branch, part):
        rec = Recommendation.objects.create(
            tenant=tenant,
            branch=branch,
            part=part,
            quantity=Decimal("12.00"),
            current_stock=Decimal("15.00"),
            punto_pedido=Decimal("47.00"),
            planning_target=Decimal("37.00"),
            velocity=Decimal("0.00"),
        )
        assert rec.coverage_days_after_fulfillment == Decimal("0.00")


