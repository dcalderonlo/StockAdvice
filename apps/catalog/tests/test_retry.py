"""Tests for the DMS adapter retry mechanism."""

from __future__ import annotations

from datetime import date

import pytest

from ..adapters import BaseDMSAdapter, with_retry
from ..adapters.exceptions import (
    DMSAuthenticationError,
    DMSConfigurationError,
    DMSConnectionError,
    DMSDataError,
    DMSError,
    DMSTimeoutError,
    DMSUnavailableError,
)


class FakeAdapter(BaseDMSAdapter):
    """Test double that can be configured to fail a number of times."""

    def __init__(self, config=None, failures=None, exception_class=DMSConnectionError):
        super().__init__(config or {})
        self.failures = failures or []
        self.exception_class = exception_class
        self.calls = []

    def test_connection(self) -> bool:
        self.calls.append("test_connection")
        if self.failures:
            failure = self.failures.pop(0)
            if failure:
                raise self.exception_class("simulated failure")
        return True

    def read_parts(self) -> list[dict]:
        self.calls.append("read_parts")
        if self.failures:
            failure = self.failures.pop(0)
            if failure:
                raise self.exception_class("simulated failure")
        return [{"internal_sku_code": "TEST-001"}]

    def read_stock(self, branch_code: str) -> dict[str, float]:
        self.calls.append("read_stock")
        return {"TEST-001": 10.0}

    def read_sales(self, branch_code: str, since_date: date) -> dict[str, list[float]]:
        self.calls.append("read_sales")
        return {"TEST-001": [1.0, 2.0]}

    def read_purchase_orders(self, branch_code: str) -> list[dict]:
        self.calls.append("read_purchase_orders")
        return []


def test_successful_call_no_retries():
    adapter = FakeAdapter()
    result = adapter.read_parts()

    assert result == [{"internal_sku_code": "TEST-001"}]
    assert adapter.calls == ["read_parts"]


def test_retry_then_success(monkeypatch):
    sleeps = []
    monkeypatch.setattr(
        "apps.catalog.adapters.retry.time.sleep", lambda seconds: sleeps.append(seconds)
    )

    adapter = FakeAdapter(failures=[True, False])
    result = adapter.read_parts()

    assert result == [{"internal_sku_code": "TEST-001"}]
    assert adapter.calls == ["read_parts", "read_parts"]
    assert sleeps == [1.0]


def test_max_attempts_exceeded(monkeypatch):
    sleeps = []
    monkeypatch.setattr(
        "apps.catalog.adapters.retry.time.sleep", lambda seconds: sleeps.append(seconds)
    )

    adapter = FakeAdapter(failures=[True, True, True])
    with pytest.raises(DMSConnectionError, match="simulated failure"):
        adapter.read_parts()

    assert adapter.calls == ["read_parts", "read_parts", "read_parts"]
    assert sleeps == [1.0, 2.0]


@pytest.mark.parametrize(
    "exception_class",
    [
        DMSAuthenticationError,
        DMSConfigurationError,
        DMSDataError,
    ],
)
def test_non_retryable_exception_fails_immediately(exception_class):
    adapter = FakeAdapter(failures=[True], exception_class=exception_class)
    with pytest.raises(exception_class, match="simulated failure"):
        adapter.read_parts()

    assert adapter.calls == ["read_parts"]


@pytest.mark.parametrize(
    "exception_class",
    [DMSConnectionError, DMSTimeoutError, DMSUnavailableError],
)
def test_all_retryable_exceptions_are_retried(exception_class, monkeypatch):
    monkeypatch.setattr("apps.catalog.adapters.retry.time.sleep", lambda _seconds: None)
    adapter = FakeAdapter(failures=[True, False], exception_class=exception_class)

    result = adapter.read_parts()

    assert result == [{"internal_sku_code": "TEST-001"}]
    assert len(adapter.calls) == 2


def test_backoff_timing(monkeypatch):
    sleeps = []
    monkeypatch.setattr(
        "apps.catalog.adapters.retry.time.sleep", lambda seconds: sleeps.append(seconds)
    )

    adapter = FakeAdapter(
        config={"retry": {"base_delay_seconds": 0.5, "max_delay_seconds": 10.0}},
        failures=[True, True, True],
    )
    with pytest.raises(DMSConnectionError):
        adapter.read_parts()

    assert sleeps == [0.5, 1.0]


def test_max_delay_caps_backoff(monkeypatch):
    sleeps = []
    monkeypatch.setattr(
        "apps.catalog.adapters.retry.time.sleep", lambda seconds: sleeps.append(seconds)
    )

    adapter = FakeAdapter(
        config={
            "retry": {
                "base_delay_seconds": 1.0,
                "max_delay_seconds": 1.5,
                "max_attempts": 4,
            }
        },
        failures=[True, True, True, True],
    )
    with pytest.raises(DMSConnectionError):
        adapter.read_parts()

    assert sleeps == [1.0, 1.5, 1.5]


def test_per_tenant_config_overrides_attempts(monkeypatch):
    monkeypatch.setattr("apps.catalog.adapters.retry.time.sleep", lambda _seconds: None)

    adapter = FakeAdapter(
        config={"retry": {"max_attempts": 5}},
        failures=[True, True, True, True, True],
    )
    with pytest.raises(DMSConnectionError):
        adapter.read_parts()

    assert len(adapter.calls) == 5


def test_retry_disabled(monkeypatch):
    monkeypatch.setattr("apps.catalog.adapters.retry.time.sleep", lambda _seconds: None)

    adapter = FakeAdapter(
        config={"retry": {"enabled": False}},
        failures=[True, True],
    )
    with pytest.raises(DMSConnectionError):
        adapter.read_parts()

    assert len(adapter.calls) == 1


def test_base_adapter_auto_wraps_methods():
    """Concrete methods inherited from BaseDMSAdapter are wrapped once."""
    assert getattr(FakeAdapter.read_parts, "_retry_wrapped", False) is True
    assert getattr(FakeAdapter.read_stock, "_retry_wrapped", False) is True


def test_test_connection_uses_shorter_defaults(monkeypatch):
    sleeps = []
    monkeypatch.setattr(
        "apps.catalog.adapters.retry.time.sleep", lambda seconds: sleeps.append(seconds)
    )

    adapter = FakeAdapter(failures=[True, True, True])
    with pytest.raises(DMSConnectionError):
        adapter.test_connection()

    # base_delay=0.5 => delays 0.5s and 1.0s before the final attempt.
    assert sleeps == [0.5, 1.0]


def test_exception_hierarchy():
    assert issubclass(DMSConnectionError, DMSError)
    assert issubclass(DMSTimeoutError, DMSError)
    assert issubclass(DMSUnavailableError, DMSError)
    assert issubclass(DMSAuthenticationError, DMSError)
    assert issubclass(DMSConfigurationError, DMSError)
    assert issubclass(DMSDataError, DMSError)


def test_retry_config_is_read_from_adapter_instance(monkeypatch):
    monkeypatch.setattr("apps.catalog.adapters.retry.time.sleep", lambda _seconds: None)

    adapter = FakeAdapter(
        config={
            "retry": {
                "enabled": True,
                "max_attempts": 3,
                "base_delay_seconds": 1.0,
                "max_delay_seconds": 30.0,
                "timeout_seconds": 30.0,
            }
        },
        failures=[True, False],
    )
    result = adapter.read_parts()

    assert result == [{"internal_sku_code": "TEST-001"}]
    assert len(adapter.calls) == 2


def test_with_retry_on_free_function(monkeypatch):
    """The decorator also works when applied manually to free functions."""
    sleeps = []
    monkeypatch.setattr(
        "apps.catalog.adapters.retry.time.sleep", lambda seconds: sleeps.append(seconds)
    )

    calls = []

    @with_retry(max_attempts=2, base_delay=0.1)
    def flaky():
        calls.append("call")
        if len(calls) == 1:
            raise DMSUnavailableError("boom")
        return "ok"

    assert flaky() == "ok"
    assert calls == ["call", "call"]
    assert sleeps == [0.1]
