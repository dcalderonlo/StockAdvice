#!/usr/bin/env python3
"""Console entry point: load fixtures, run engine, print recommendations."""

from __future__ import annotations

from stockadvice_spike.fixtures.sample_data import (
    BRANCH_CONFIG,
    get_parts,
    get_sales_movements,
    get_stock_levels,
)
from stockadvice_spike.output import render_console
from stockadvice_spike.replenishment import run_replenishment


def main() -> int:
    recommendations = run_replenishment(
        parts=get_parts(),
        stock_levels=get_stock_levels(),
        movements=get_sales_movements(),
        config=BRANCH_CONFIG,
    )
    print(render_console(recommendations))

    triggered = [r for r in recommendations if r.quantity > 0]
    print()
    print(f"Action required for {len(triggered)} SKU(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
