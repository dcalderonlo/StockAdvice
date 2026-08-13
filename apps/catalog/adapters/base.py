"""Abstract DMS adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date


class BaseDMSAdapter(ABC):
    """Read-only interface for extracting data from an external DMS/ERP.

    Concrete adapters handle schema variability internally and return
    normalized Python structures that the ingestion services consume.
    """

    def __init__(self, config: dict) -> None:
        self.config = config

    @abstractmethod
    def test_connection(self) -> bool:
        """Return True if the DMS is reachable with the current config."""
        ...

    @abstractmethod
    def read_parts(self) -> list[dict]:
        """Return a list of part dicts for ingestion into ``Part``.

        Expected keys per dict: internal_sku_code, primary_manufacturer_code,
        description, category, unit_of_measure, lead_time_days.
        """
        ...

    @abstractmethod
    def read_stock(self, branch_code: str) -> dict[str, float]:
        """Return a mapping of internal SKU code -> available stock quantity."""
        ...

    @abstractmethod
    def read_sales(
        self, branch_code: str, since_date: date
    ) -> dict[str, list[float]]:
        """Return a mapping of SKU -> list of monthly sales (most recent first)."""
        ...

    @abstractmethod
    def read_purchase_orders(self, branch_code: str) -> list[dict]:
        """Return a list of in-transit purchase orders.

        Expected keys per dict: sku, quantity, expected_date.
        """
        ...
