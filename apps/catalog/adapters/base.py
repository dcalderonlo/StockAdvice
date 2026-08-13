"""Abstract DMS adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from .retry import with_retry


class BaseDMSAdapter(ABC):
    """Read-only interface for extracting data from an external DMS/ERP.

    Concrete adapters handle schema variability internally and return
    normalized Python structures that the ingestion services consume. Every
    public read method is automatically wrapped with ``@with_retry`` so that
    transient DMS failures are retried with exponential backoff; subclasses do
    not need to repeat the decorator.
    """

    _RETRYABLE_METHODS = frozenset(
        {
            "test_connection",
            "read_parts",
            "read_stock",
            "read_sales",
            "read_purchase_orders",
        }
    )

    # Method-specific retry defaults. ``test_connection`` uses a shorter backoff
    # because a connectivity probe should fail fast; reads use the standard 1s/2s/4s.
    _RETRY_OVERRIDES = {
        "test_connection": {
            "max_attempts": 3,
            "base_delay": 0.5,
            "max_delay": 5.0,
            "timeout_seconds": 10.0,
        },
    }

    def __init__(self, config: dict) -> None:
        self.config = config

    def __init_subclass__(cls, **kwargs):
        """Auto-wrap concrete read methods with the retry decorator.

        Subclasses can override retry settings through ``self.config["retry"]``
        or disable retries entirely with ``{"retry": {"enabled": false}}``.
        """
        super().__init_subclass__(**kwargs)
        for name in cls._RETRYABLE_METHODS:
            if name not in cls.__dict__:
                continue
            method = cls.__dict__[name]
            if not callable(method) or getattr(method, "_retry_wrapped", False):
                continue
            overrides = cls._RETRY_OVERRIDES.get(name, {})
            wrapped = with_retry(**overrides)(method)
            wrapped._retry_wrapped = True  # type: ignore[attr-defined]
            setattr(cls, name, wrapped)

    @with_retry(max_attempts=3, base_delay=0.5, max_delay=5.0, timeout_seconds=10.0)
    @abstractmethod
    def test_connection(self) -> bool:
        """Return True if the DMS is reachable with the current config."""
        ...

    @with_retry()
    @abstractmethod
    def read_parts(self) -> list[dict]:
        """Return a list of part dicts for ingestion into ``Part``.

        Expected keys per dict: internal_sku_code, primary_manufacturer_code,
        description, category, unit_of_measure, lead_time_days.
        """
        ...

    @with_retry()
    @abstractmethod
    def read_stock(self, branch_code: str) -> dict[str, float]:
        """Return a mapping of internal SKU code -> available stock quantity."""
        ...

    @with_retry()
    @abstractmethod
    def read_sales(
        self, branch_code: str, since_date: date
    ) -> dict[str, list[float]]:
        """Return a mapping of SKU -> list of monthly sales (most recent first)."""
        ...

    @with_retry()
    @abstractmethod
    def read_purchase_orders(self, branch_code: str) -> list[dict]:
        """Return a list of in-transit purchase orders.

        Expected keys per dict: sku, quantity, expected_date.
        """
        ...
