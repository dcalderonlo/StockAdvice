"""Mock DMS adapter backed by local fixture data."""

from __future__ import annotations

from datetime import date

from .base import BaseDMSAdapter
from ..fixtures.sample_dms_data import (
    get_purchase_orders,
    get_sales_history,
    get_stock_levels,
    PARTS_CATALOG,
)


class MockDMSAdapter(BaseDMSAdapter):
    """Concrete adapter that returns deterministic fixture data."""

    def test_connection(self) -> bool:
        return True

    def read_parts(self) -> list[dict]:
        return [dict(part) for part in PARTS_CATALOG]

    def read_stock(self, branch_code: str) -> dict[str, float]:
        return get_stock_levels(branch_code)

    def read_sales(self, branch_code: str, since_date: date) -> dict[str, list[float]]:
        return get_sales_history(branch_code, since_date)

    def read_purchase_orders(self, branch_code: str) -> list[dict]:
        return get_purchase_orders(branch_code)
