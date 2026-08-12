"""Output formatters for recommendations: console table and simple HTML."""

from __future__ import annotations

from html import escape
from typing import Iterable

from stockadvice_spike.entities import Recommendation


def _fmt(value: float, decimals: int = 1) -> str:
    """Format a float for display, dropping trailing zeros."""
    if value == int(value):
        return str(int(value))
    return f"{value:.{decimals}f}"


def _source_label(rec: Recommendation) -> str:
    """Return a concise human-readable source/action label."""
    if rec.quantity <= 0:
        return "No action"
    src = rec.primary_source
    if src.source_type == "transfer":
        branch = src.source_branch_code or "?"
        if rec.is_partial:
            return f"Partial transfer from {branch} + supplier"
        return f"Inter-branch transfer from {branch}"
    if src.source_type == "supplier":
        return "External supplier"
    return src.source_type


def render_console(recommendations: Iterable[Recommendation]) -> str:
    """Render recommendations as an aligned console table."""
    recs = list(recommendations)
    lines = []
    lines.append("StockAdvice Phase 0 — Replenishment Recommendations")
    lines.append("=" * 110)
    header = (
        f"{'SKU':<10} {'Description':<28} {'VC':<5} "
        f"{'Stock':>8} {'Trans':>8} {'PP':>10} {'Cantidad':>10} {'Source':<30}"
    )
    lines.append(header)
    lines.append("-" * 110)

    trigger_count = 0
    for rec in recs:
        result = rec.planning_result
        if result is None:
            continue
        cantidad = _fmt(rec.quantity) if rec.quantity > 0 else "-"
        if rec.quantity > 0:
            trigger_count += 1
        lines.append(
            f"{rec.part.internal_sku_code:<10} "
            f"{rec.part.description:<28} "
            f"{result.volume_class or '-':<5} "
            f"{_fmt(result.stock_disponible):>8} "
            f"{_fmt(result.stock_en_transito):>8} "
            f"{_fmt(result.punto_pedido):>10} "
            f"{cantidad:>10} "
            f"{_source_label(rec):<30}"
        )

    lines.append("-" * 110)
    lines.append(f"Total SKUs evaluated: {len(recs)} | Recommendations triggered: {trigger_count}")
    return "\n".join(lines)


def render_html(recommendations: Iterable[Recommendation], title: str = "StockAdvice Spike") -> str:
    """Render recommendations as a simple HTML page using Pico.css."""
    recs = list(recommendations)
    trigger_count = sum(1 for r in recs if r.quantity > 0)

    rows = []
    for rec in recs:
        result = rec.planning_result
        if result is None:
            continue
        cantidad = _fmt(rec.quantity) if rec.quantity > 0 else "-"
        row_class = "triggered" if rec.quantity > 0 else ""
        rows.append(
            f"<tr class='{row_class}'>"
            f"<td>{escape(rec.part.internal_sku_code)}</td>"
            f"<td>{escape(rec.part.description)}</td>"
            f"<td>{escape(result.volume_class or '-')}</td>"
            f"<td class='numeric'>{_fmt(result.stock_disponible)}</td>"
            f"<td class='numeric'>{_fmt(result.stock_en_transito)}</td>"
            f"<td class='numeric'>{_fmt(result.punto_pedido)}</td>"
            f"<td class='numeric'>{cantidad}</td>"
            f"<td>{escape(_source_label(rec))}</td>"
            f"</tr>"
        )

    rows_html = "\n".join(rows)

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
  <style>
    .numeric {{ text-align: right; font-variant-numeric: tabular-nums; }}
    tr.triggered {{ background-color: #fff3cd; }}
    h1 {{ margin-bottom: 0.25rem; }}
    .summary {{ margin-bottom: 1.5rem; color: #555; }}
  </style>
</head>
<body>
  <main class="container">
    <h1>{escape(title)}</h1>
    <p class="summary">
      Total SKUs evaluated: <strong>{len(recs)}</strong> |
      Recommendations triggered: <strong>{trigger_count}</strong>
    </p>
    <table>
      <thead>
        <tr>
          <th>SKU</th>
          <th>Description</th>
          <th>Volume Class</th>
          <th class="numeric">Stock Actual</th>
          <th class="numeric">Stock en Tránsito</th>
          <th class="numeric">Punto de Pedido</th>
          <th class="numeric">Cantidad de Pedido</th>
          <th>Source</th>
        </tr>
      </thead>
      <tbody>
{rows_html}
      </tbody>
    </table>
  </main>
</body>
</html>
"""
