#!/usr/bin/env python3
"""Optional HTML entry point: render recommendations to a simple HTML file."""

from __future__ import annotations

import argparse
from pathlib import Path

from stockadvice_spike.fixtures.sample_data import (
    BRANCH_CONFIG,
    get_parts,
    get_sales_movements,
    get_stock_levels,
)
from stockadvice_spike.output import render_html
from stockadvice_spike.replenishment import run_replenishment


def main() -> int:
    parser = argparse.ArgumentParser(description="Render StockAdvice spike recommendations to HTML")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("recommendations.html"),
        help="Output HTML file path",
    )
    args = parser.parse_args()

    recommendations = run_replenishment(
        parts=get_parts(),
        stock_levels=get_stock_levels(),
        movements=get_sales_movements(),
        config=BRANCH_CONFIG,
    )

    html = render_html(recommendations, title="StockAdvice Phase 0 Recommendations")
    args.output.write_text(html, encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
