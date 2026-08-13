"""Deterministic fixture data for the MockDMSAdapter."""

from __future__ import annotations

from datetime import date
from typing import Any

BRANCH_CODES = ["SUC-001", "SUC-002", "SUC-003", "CD-001"]

_CATEGORIES = [
    "Brake System",
    "Engine",
    "Suspension",
    "Electrical",
    "Filters",
    "Transmission",
    "Cooling",
    "Body",
]


def _build_parts_catalog(count: int = 50) -> list[dict[str, Any]]:
    """Generate a stable catalog of ``count`` parts."""
    parts: list[dict[str, Any]] = []
    for i in range(1, count + 1):
        category = _CATEGORIES[i % len(_CATEGORIES)]
        parts.append(
            {
                "internal_sku_code": f"SKU-{i:04d}",
                "primary_manufacturer_code": f"MFR-{i:04d}",
                "description": f"{category} part #{i}",
                "category": category,
                "unit_of_measure": "PCS",
                "lead_time_days": 7 + (i % 8),
            }
        )
    return parts


PARTS_CATALOG: list[dict[str, Any]] = _build_parts_catalog(50)


def _sku(index: int) -> str:
    return PARTS_CATALOG[index]["internal_sku_code"]


_STOCK_LEVELS: dict[str, dict[str, float]] = {
    "SUC-001": {PARTS_CATALOG[i]["internal_sku_code"]: float(5 + (i % 20)) for i in range(50)},
    "SUC-002": {PARTS_CATALOG[i]["internal_sku_code"]: float(3 + (i % 15)) for i in range(50)},
    "SUC-003": {PARTS_CATALOG[i]["internal_sku_code"]: float(8 + (i % 12)) for i in range(50)},
    "CD-001": {PARTS_CATALOG[i]["internal_sku_code"]: float(20 + (i % 30)) for i in range(50)},
}


def get_stock_levels(branch_code: str) -> dict[str, float]:
    """Return available stock per SKU for ``branch_code``."""
    if branch_code not in _STOCK_LEVELS:
        return {}
    return dict(_STOCK_LEVELS[branch_code])


_SALES_HISTORY: dict[str, dict[str, list[float]]] = {}


def _build_sales_history() -> dict[str, dict[str, list[float]]]:
    """Generate 12 months of sales per branch and SKU."""
    history: dict[str, dict[str, list[float]]] = {}
    for branch in BRANCH_CODES:
        history[branch] = {}
        for i, part in enumerate(PARTS_CATALOG):
            base = 2.0 + (i % 10)
            # Recent months weighted a bit higher to exercise velocity formulas.
            months = [base + ((11 - m) * 0.15) + ((i + m) % 3) for m in range(12)]
            history[branch][part["internal_sku_code"]] = months
    return history


_SALES_HISTORY = _build_sales_history()


def get_sales_history(branch_code: str, since_date: date) -> dict[str, list[float]]:
    """Return 12 monthly sales figures per SKU (most recent first)."""
    if branch_code not in _SALES_HISTORY:
        return {}
    # ``since_date`` is accepted to match the interface contract but the fixture
    # always returns the same 12-month window regardless of the date.
    _ = since_date
    return {sku: list(values) for sku, values in _SALES_HISTORY[branch_code].items()}


_PURCHASE_ORDERS: dict[str, list[dict[str, Any]]] = {
    "SUC-001": [
        {"sku": _sku(0), "quantity": 12.0, "expected_date": date(2026, 8, 20)},
        {"sku": _sku(5), "quantity": 8.0, "expected_date": date(2026, 8, 22)},
    ],
    "SUC-002": [
        {"sku": _sku(1), "quantity": 6.0, "expected_date": date(2026, 8, 21)},
    ],
    "SUC-003": [
        {"sku": _sku(2), "quantity": 10.0, "expected_date": date(2026, 8, 23)},
        {"sku": _sku(7), "quantity": 4.0, "expected_date": date(2026, 8, 25)},
    ],
    "CD-001": [
        {"sku": _sku(3), "quantity": 30.0, "expected_date": date(2026, 8, 24)},
    ],
}


def get_purchase_orders(branch_code: str) -> list[dict[str, Any]]:
    """Return in-transit purchase orders for ``branch_code``."""
    return [dict(order) for order in _PURCHASE_ORDERS.get(branch_code, [])]
