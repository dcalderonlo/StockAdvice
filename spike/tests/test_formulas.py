"""Unit tests for the core planning formulas.

The "known good" values below are computed from the source material's formula
interpretation (per user decision 2026-08-08):

  Planning Target = (velocity / 30) × (period_days + security_days + lead_time_days)
  Punto de Pedido   = Planning Target + lead_time_days (raw, matches material's example)
  Cantidad de Pedido = max(0, Planning Target − stock − transit)

The source material (Star Cooperation LPR Basics) lists example values:
  monthly sales 20, period 30, security 15, lead 10 → PT 37, PP 47, CP 12

Material's math: PT = (20/30) × 55 = 36.67 ≈ 37; PP = 37 + 10 = 47; CP = 37 - 15 - 10 = 12.

We use float values in tests (no rounding), and the system rounds for display.
"""

from __future__ import annotations

import pytest

from stockadvice_spike.formulas import (
    annual_sales_from_history,
    cantidad_pedido,
    coverage_days,
    excess_stock,
    planning_target,
    punto_pedido,
    stock_turn_ratio,
    velocity,
    volume_class,
)


class TestVelocity:
    def test_flat_history_returns_same_value(self) -> None:
        history = [10.0] * 12
        assert velocity(history) == pytest.approx(10.0)

    def test_recent_months_weigh_heavier(self) -> None:
        rising = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0]
        vel = velocity(rising)
        # Weighted average must be above the simple mean because recent months weigh more.
        assert vel > sum(rising) / len(rising)
        assert vel == pytest.approx(16.58, abs=0.01)

    def test_empty_history_is_zero(self) -> None:
        assert velocity([]) == 0.0

    def test_shorter_history_is_accepted(self) -> None:
        # 6 months, linear weights from 0.5 to 1.5.
        history = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0]
        vel = velocity(history)
        assert vel == pytest.approx(8.17, abs=0.01)


class TestPlanningTarget:
    def test_material_example_one(self) -> None:
        # Material: monthly sales 20, period 30, security 15, lead 10.
        # Material PT: (20/30) * (30+15+10) = 36.67 (rounds to 37 in example).
        assert planning_target(
            velocity=20.0, period_days=30, security_days=15, lead_time_days=10
        ) == pytest.approx(36.67, abs=0.01)

    def test_material_example_two(self) -> None:
        # Material: monthly sales 12, period 44, security 22, lead 11.
        # Material PT: (12/30) * (44+22+11) = 30.8 (rounds to 31 in example).
        assert planning_target(
            velocity=12.0, period_days=44, security_days=22, lead_time_days=11
        ) == pytest.approx(30.8, abs=0.01)

    def test_zero_velocity(self) -> None:
        assert planning_target(
            velocity=0.0, period_days=30, security_days=10, lead_time_days=5
        ) == 0.0

    def test_negative_velocity_is_clamped(self) -> None:
        assert planning_target(
            velocity=-5.0, period_days=30, security_days=10, lead_time_days=5
        ) == 0.0


class TestPuntoDePedido:
    def test_material_example_one(self) -> None:
        # Material: PT = 37, lead = 10 → PP = 37 + 10 = 47.
        # (Using float PT 36.67, PP = 36.67 + 10 = 46.67.)
        assert punto_pedido(planning_target_value=36.67, lead_time_days=10) == pytest.approx(46.67, abs=0.01)

    def test_material_example_two(self) -> None:
        # Material: PT ≈ 31, lead = 11 → PP = 31 + 11 = 42.
        # (Using float PT 30.8, PP = 30.8 + 11 = 41.8.)
        assert punto_pedido(planning_target_value=30.8, lead_time_days=11) == pytest.approx(41.8, abs=0.01)


class TestCantidadPedido:
    def test_material_example_one(self) -> None:
        # Material: PT = 37, stock = 15, transit = 10 → CP = 37 - 15 - 10 = 12.
        # (Using float PT 36.67, CP = 36.67 - 15 - 10 = 11.67.)
        assert cantidad_pedido(36.67, stock_disponible=15.0, stock_en_transito=10.0) == pytest.approx(11.67, abs=0.01)

    def test_material_example_two(self) -> None:
        # Material: PT = 31, stock = 9, transit = 20 → CP = 31 - 9 - 20 = 2.
        # (Using float PT 30.8, CP = 30.8 - 9 - 20 = 1.8.)
        assert cantidad_pedido(30.8, stock_disponible=9.0, stock_en_transito=20.0) == pytest.approx(1.8, abs=0.01)

    def test_cantidad_is_zero_when_stock_exceeds_target(self) -> None:
        assert cantidad_pedido(10.0, stock_disponible=20.0, stock_en_transito=0.0) == 0.0

    def test_cantidad_accounts_for_transit(self) -> None:
        assert cantidad_pedido(100.0, stock_disponible=70.0, stock_en_transito=20.0) == 10.0


class TestVolumeClass:
    @pytest.mark.parametrize(
        "sales,expected",
        [
            (0, ""),
            (1, "VC8"),
            (3, "VC8"),
            (4, "VC7"),
            (6, "VC7"),
            (7, "VC6"),
            (14, "VC6"),
            (15, "VC5"),
            (30, "VC5"),
            (31, "VC4"),
            (60, "VC4"),
            (61, "VC3"),
            (120, "VC3"),
            (121, "VC2"),
            (250, "VC2"),
            (251, "VC1"),
            (1000, "VC1"),
        ],
    )
    def test_volume_class_boundaries(self, sales: int, expected: str) -> None:
        assert volume_class(sales) == expected


class TestExcessStock:
    def test_excess_when_stock_above_pp(self) -> None:
        assert excess_stock(stock_actual=100.0, punto_pedido_value=40.0) == 60.0

    def test_no_excess_when_stock_at_pp(self) -> None:
        assert excess_stock(stock_actual=40.0, punto_pedido_value=40.0) == 0.0

    def test_no_excess_when_stock_below_pp(self) -> None:
        assert excess_stock(stock_actual=30.0, punto_pedido_value=40.0) == 0.0


class TestKPIs:
    def test_stock_turn_ratio(self) -> None:
        # From material: Ingresos Año-12 = 5605, Stock Promedio-12 = 1830 → 3.1.
        assert stock_turn_ratio(5605.0, 1830.0) == pytest.approx(3.06, abs=0.01)

    def test_coverage_days(self) -> None:
        # 365 / 3.06 ≈ 119.
        assert coverage_days(5605.0, 1830.0) == pytest.approx(119.2, abs=0.1)

    def test_zero_average_stock_avoids_division_by_zero(self) -> None:
        assert stock_turn_ratio(1000.0, 0.0) == 0.0
        assert coverage_days(1000.0, 0.0) == 0.0

    def test_annual_sales(self) -> None:
        assert annual_sales_from_history([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]) == 78
