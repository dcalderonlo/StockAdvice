"""Tests for the MockDMSAdapter."""

from __future__ import annotations

from datetime import date

import pytest

from ..adapters import MockDMSAdapter


@pytest.fixture
def adapter():
    return MockDMSAdapter(config={"source": "fixture"})


def test_test_connection(adapter):
    assert adapter.test_connection() is True


def test_read_parts_count(adapter):
    parts = adapter.read_parts()
    assert len(parts) == 50
    assert all("internal_sku_code" in part for part in parts)
    assert all("description" in part for part in parts)


def test_read_stock_returns_all_skus(adapter):
    stock = adapter.read_stock("CD-001")
    assert len(stock) == 50
    assert all(isinstance(qty, (int, float)) for qty in stock.values())
    assert stock[adapter.read_parts()[0]["internal_sku_code"]] > 0


def test_read_stock_unknown_branch(adapter):
    assert adapter.read_stock("UNKNOWN") == {}


def test_read_sales_shape(adapter):
    sales = adapter.read_sales("SUC-001", date(2026, 1, 1))
    assert len(sales) == 50
    for sku, months in sales.items():
        assert len(months) == 12
        assert all(isinstance(value, (int, float)) for value in months)


def test_read_sales_unknown_branch(adapter):
    assert adapter.read_sales("UNKNOWN", date(2026, 1, 1)) == {}


def test_read_purchase_orders(adapter):
    orders = adapter.read_purchase_orders("SUC-001")
    assert len(orders) >= 1
    assert all("sku" in order and "quantity" in order for order in orders)


def test_read_purchase_orders_unknown_branch(adapter):
    assert adapter.read_purchase_orders("UNKNOWN") == []
