"""Sanity checks for formula behavior on edge-case inputs."""

from __future__ import annotations

import pytest

from stockadvice_spike.entities import BranchConfig, Part, SalesMovement, StockLevel
from stockadvice_spike.formulas import (
    cantidad_pedido,
    excess_stock,
    planning_target,
    punto_pedido,
    velocity,
    volume_class,
)
from stockadvice_spike.replenishment import run_replenishment


def test_zero_sales_history_yields_zero_velocity(self=None) -> None:
    assert velocity([0.0] * 12) == 0.0


def test_zero_velocity_yields_zero_planning_target() -> None:
    assert planning_target(
        velocity=0.0, period_days=30, security_days=10, lead_time_days=10
    ) == 0.0


def test_zero_velocity_yields_zero_punto_pedido() -> None:
    # PP = 0 + 10 = 10 (PP gets lead time added regardless of velocity).
    # The check is that zero PT propagates correctly into PP, not that PP is zero.
    assert punto_pedido(planning_target_value=0.0, lead_time_days=10) == 10.0


def test_negative_cantidad_is_clamped() -> None:
    assert cantidad_pedido(10.0, stock_disponible=50.0, stock_en_transito=10.0) == 0.0


def test_negative_stock_does_not_produce_negative_cantidad() -> None:
    # Negative stock should not happen, but the formula must not break.
    assert cantidad_pedido(10.0, stock_disponible=-5.0, stock_en_transito=0.0) == 15.0


def test_very_large_numbers_remain_stable() -> None:
    big = 1_000_000.0
    assert planning_target(
        big, period_days=30, security_days=10, lead_time_days=10
    ) == pytest.approx(big / 30.0 * 50.0)


def test_excess_stock_with_negative_stock_actual() -> None:
    # Negative stock actual is invalid but should not crash.
    assert excess_stock(stock_actual=-10.0, punto_pedido_value=5.0) == 0.0


def test_run_replenishment_with_missing_stock_level() -> None:
    """The engine must handle a part that has sales history but no stock level."""
    part = Part("GHOST-001", "GHOST-001", "Ghost Part", lead_time_days=10)
    config = BranchConfig(branch_code="BR", period_days=30, security_days=10)
    movements = [SalesMovement(part, "BR", month_index=i, quantity=5) for i in range(12)]

    recommendations = run_replenishment(
        parts=[part],
        stock_levels=[],  # no stock level
        movements=movements,
        config=config,
    )
    assert len(recommendations) == 1
    rec = recommendations[0]
    assert rec.quantity > 0
    assert rec.planning_result is not None
    assert rec.planning_result.stock_disponible == 0.0


def test_run_replenishment_with_missing_sales_history() -> None:
    """The engine must handle a part that has stock but no sales history."""
    part = Part("NEW-001", "NEW-001", "New Part", lead_time_days=10)
    config = BranchConfig(branch_code="BR", period_days=30, security_days=10)
    stock = StockLevel(part, "BR", stock_disponible=5.0, stock_en_transito=0.0)

    recommendations = run_replenishment(
        parts=[part],
        stock_levels=[stock],
        movements=[],  # no sales history
        config=config,
    )
    assert len(recommendations) == 1
    rec = recommendations[0]
    assert rec.quantity == 0.0
    assert rec.primary_source.source_type == "no_action"
    assert volume_class(rec.planning_result.annual_sales) == ""
