"""Pure functions for inventory planning calculations.

All functions are side-effect free and operate on scalar values or simple
collections. This makes them trivial to unit-test and reuse in later phases.

Formula baseline (from source material, per user decision 2026-08-08):
- Planning Target = (ventas_mensuales / 30) × (Periodo de Stock + Stock de Seguridad + Tiempo de Pedido)
- Punto de Pedido   = Planning Target + Tiempo de Pedido (raw, days added to units — matches material's example)
- Cantidad de Pedido = max(0, Planning Target − Stock Disponible − Stock en Tránsito)
- Excess stock       = max(0, Stock Actual − Punto de Pedido)

NOTE: Planning Target INCLUDES lead time, per the source material convention.
The proposal originally had Planning Target = (v/30) × (period + security),
but the source material's example (sales 20, period 30, security 15, lead 10 →
PT 37) only works with lead time included. The user adopted the material's
interpretation, so this spike follows it.

DIMENSIONAL NOTE on Punto de Pedido: PT is in units, lead_time_days is in
days, so PP is technically not a pure unit. The material's example treats
the addition as raw numeric (PP = 37 + 10 = 47). This is consistent with
the material's convention but not dimensionally clean. Preserved for fidelity
to the source; can be revisited in v2+ if needed.
"""

from __future__ import annotations

from typing import Iterable


def velocity(sales_history: list[float]) -> float:
    """Weighted average monthly sales, recent months weighted more heavily.

    For the spike we use simple linear weights: month 1 (oldest) = 0.5,
    month 12 (newest) = 1.5. Recent months therefore get 3× the weight of the
    oldest month. The weights are normalized so the result is still in units/month.

    A shorter history is accepted; missing months are treated as zero sales and
    still contribute (with reduced weight) so that cold-start SKUs naturally get
    a low velocity.
    """
    if not sales_history:
        return 0.0

    n = len(sales_history)
    # Linear ramp from 0.5 to 1.5 across the provided history.
    weights = [0.5 + (i / max(n - 1, 1)) for i in range(n)]
    weighted_sum = sum(q * w for q, w in zip(sales_history, weights))
    weight_total = sum(weights)
    return weighted_sum / weight_total if weight_total else 0.0


def stock_turn_ratio(annual_revenue: float, average_stock_value: float) -> float:
    """Rotación de Stock: how many times stock turns in 12 months."""
    if average_stock_value <= 0:
        return 0.0
    return annual_revenue / average_stock_value


def coverage_days(annual_revenue: float, average_stock_value: float) -> float:
    """Cobertura: average days merchandise remains in stock until sold."""
    str_ratio = stock_turn_ratio(annual_revenue, average_stock_value)
    if str_ratio <= 0:
        return 0.0
    return 365.0 / str_ratio


def planning_target(
    velocity: float, period_days: int, security_days: int, lead_time_days: int
) -> float:
    """Planning Target = (velocity / 30) × (period_days + security_days + lead_time_days).

    Per the source material's convention, Planning Target (Stock Máximo) INCLUDES
    the Tiempo de Pedido. The divisor covers the full replenishment cycle:
    operating period + safety buffer + lead time.
    """
    if velocity < 0:
        velocity = 0.0
    return (velocity / 30.0) * (period_days + security_days + lead_time_days)


def punto_pedido(planning_target_value: float, lead_time_days: int) -> float:
    """Punto de Pedido = Planning Target + lead_time_days.

    Per the source material's example, PP is computed by literally adding the
    lead time in DAYS to the Planning Target in UNITS (raw numeric addition).
    This is dimensionally inconsistent but matches the material's convention
    (e.g., PT 37 + lead 10 = PP 47).
    """
    return planning_target_value + lead_time_days


def cantidad_pedido(
    planning_target_value: float, stock_disponible: float, stock_en_transito: float
) -> float:
    """Cantidad de Pedido = max(0, Planning Target − disponible − tránsito)."""
    return max(0.0, planning_target_value - stock_disponible - stock_en_transito)


def volume_class(annual_sales: int) -> str:
    """Volume Class (VC1–VC8) based on annual sales volume.

    Thresholds from proposal §6 / material §4:
      VC1 > 250, VC2 121–250, VC3 61–120, VC4 31–60,
      VC5 15–30, VC6 7–14, VC7 4–6, VC8 1–3.
    Zero sales return an empty string (cold-start / no classification).
    """
    if annual_sales >= 251:
        return "VC1"
    if annual_sales >= 121:
        return "VC2"
    if annual_sales >= 61:
        return "VC3"
    if annual_sales >= 31:
        return "VC4"
    if annual_sales >= 15:
        return "VC5"
    if annual_sales >= 7:
        return "VC6"
    if annual_sales >= 4:
        return "VC7"
    if annual_sales >= 1:
        return "VC8"
    return ""


def excess_stock(stock_actual: float, punto_pedido_value: float) -> float:
    """Excess stock available for inter-branch transfer without falling below PP."""
    return max(0.0, stock_actual - punto_pedido_value)


def annual_sales_from_history(sales_history: Iterable[float]) -> int:
    """Simple sum of a 12-month sales history."""
    return int(sum(sales_history))
