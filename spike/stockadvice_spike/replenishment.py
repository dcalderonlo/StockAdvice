"""Replenishment engine: derive planning metrics and produce recommendations.

For the spike the engine is single-branch and source resolution is limited to a
simplified inter-branch transfer scan. The external-supplier fallback is
represented explicitly so the output format is honest about what v1 will need.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from stockadvice_spike.entities import (
    BranchConfig,
    Part,
    PlanningResult,
    Recommendation,
    RecommendationSource,
    SalesMovement,
    StockLevel,
)
from stockadvice_spike.formulas import (
    annual_sales_from_history,
    cantidad_pedido,
    excess_stock,
    planning_target,
    punto_pedido,
    velocity,
    volume_class,
)


def build_sales_lookup(
    movements: Iterable[SalesMovement],
) -> dict[tuple[str, str], list[float]]:
    """Group sales movements by (branch_code, sku) into ordered monthly lists."""
    lookup: dict[tuple[str, str], dict[int, float]] = defaultdict(dict)
    for mv in movements:
        key = (mv.branch_code, mv.part.internal_sku_code)
        lookup[key][mv.month_index] = float(mv.quantity)

    result: dict[tuple[str, str], list[float]] = {}
    for key, month_map in lookup.items():
        max_index = max(month_map.keys()) if month_map else -1
        result[key] = [month_map.get(i, 0.0) for i in range(max_index + 1)]
    return result


def compute_planning_result(
    part: Part,
    branch_code: str,
    sales_history: list[float],
    stock_level: StockLevel | None,
    config: BranchConfig,
) -> PlanningResult:
    """Compute all derived metrics for one part / branch."""
    vel = velocity(sales_history)
    annual = annual_sales_from_history(sales_history)
    vc = volume_class(annual)

    pt = planning_target(
        vel, config.period_days, config.security_days, part.lead_time_days
    )
    pp = punto_pedido(pt, part.lead_time_days)

    disponible = stock_level.stock_disponible if stock_level else 0.0
    transito = stock_level.stock_en_transito if stock_level else 0.0
    actual = disponible + transito

    cq = cantidad_pedido(pt, disponible, transito)
    excess = excess_stock(actual, pp)

    return PlanningResult(
        part=part,
        branch_code=branch_code,
        velocity=vel,
        annual_sales=annual,
        volume_class=vc,
        planning_target=pt,
        punto_pedido=pp,
        stock_disponible=disponible,
        stock_en_transito=transito,
        cantidad_pedido=cq,
        excess_stock=excess,
    )


def resolve_source(
    result: PlanningResult,
    all_results: dict[str, PlanningResult],
) -> Recommendation:
    """Decide whether the recommendation can be fulfilled internally.

    The spike uses a naive greedy scan over all other results in the same
    fixture set. It does not model distance, transfer cost, or DC topology; that
    is deferred to v1.
    """
    destination = result.branch_code
    sku = result.part.internal_sku_code
    needed = result.cantidad_pedido

    if needed <= 0:
        return Recommendation(
            part=result.part,
            destination_branch_code=destination,
            quantity=0.0,
            primary_source=RecommendationSource(
                source_type="no_action",
                reason="Stock above Punto de Pedido",
            ),
            planning_result=result,
        )

    # Look for surplus at other branches. For the spike we only have one
    # real branch, but we simulate a sibling branch "SUC-001" that holds some
    # excess inventory for transfer-demonstration purposes.
    transfers: list[RecommendationSource] = []
    remaining = needed

    for source_code, source_result in all_results.items():
        if source_code == destination:
            continue
        if source_result.part.internal_sku_code != sku:
            continue
        available = source_result.excess_stock
        if available <= 0:
            continue
        take = min(available, remaining)
        transfers.append(
            RecommendationSource(
                source_type="transfer",
                source_branch_code=source_code,
                quantity=take,
                reason=f"Excess stock at {source_code}",
            )
        )
        remaining -= take
        if remaining <= 0:
            break

    if transfers and remaining <= 0:
        return Recommendation(
            part=result.part,
            destination_branch_code=destination,
            quantity=needed,
            primary_source=transfers[0],
            fill_sources=transfers[1:],
            planning_result=result,
            is_partial=False,
            partial_gap=0.0,
        )

    # Partial fulfillment: some transfer, remainder external.
    if transfers:
        covered = needed - remaining
        return Recommendation(
            part=result.part,
            destination_branch_code=destination,
            quantity=needed,
            primary_source=RecommendationSource(
                source_type="transfer",
                source_branch_code=transfers[0].source_branch_code,
                quantity=covered,
                reason="Partial inter-branch transfer",
            ),
            fill_sources=[
                *transfers[1:],
                RecommendationSource(
                    source_type="supplier",
                    quantity=remaining,
                    reason="External supplier fallback for remaining quantity",
                ),
            ],
            planning_result=result,
            is_partial=True,
            partial_gap=remaining,
        )

    # No internal source available.
    return Recommendation(
        part=result.part,
        destination_branch_code=destination,
        quantity=needed,
        primary_source=RecommendationSource(
            source_type="supplier",
            quantity=needed,
            reason="No excess stock at sibling branches",
        ),
        planning_result=result,
    )


def run_replenishment(
    parts: Iterable[Part],
    stock_levels: Iterable[StockLevel],
    movements: Iterable[SalesMovement],
    config: BranchConfig,
    sibling_stock_levels: Iterable[StockLevel] | None = None,
) -> list[Recommendation]:
    """Run the full replenishment algorithm and return recommendations.

    Parameters
    ----------
    parts:
        Catalog items to evaluate.
    stock_levels:
        Stock levels for the branch being replenished.
    movements:
        Sales movements used to derive velocity and volume class.
    config:
        Branch planning parameters.
    sibling_stock_levels:
        Optional stock levels from other branches, used for transfer source
        resolution. If omitted, all recommendations fall back to supplier.
    """
    sales_lookup = build_sales_lookup(movements)
    stock_lookup = {
        sl.part.internal_sku_code: sl for sl in stock_levels if sl.branch_code == config.branch_code
    }

    # Combine destination + sibling levels for source resolution.
    all_levels = list(stock_levels)
    if sibling_stock_levels:
        all_levels.extend(sibling_stock_levels)

    all_results: dict[str, PlanningResult] = {}
    for sl in all_levels:
        key = (sl.branch_code, sl.part.internal_sku_code)
        history = sales_lookup.get(key, [])
        # Guard against missing history (cold-start SKUs).
        if not history:
            history = [0.0] * 12
        all_results[sl.branch_code] = compute_planning_result(
            sl.part, sl.branch_code, history, sl, config
        )

    recommendations = []
    for part in parts:
        key = (config.branch_code, part.internal_sku_code)
        history = sales_lookup.get(key, [0.0] * 12)
        stock_level = stock_lookup.get(part.internal_sku_code)
        result = compute_planning_result(
            part, config.branch_code, history, stock_level, config
        )
        rec = resolve_source(result, all_results)
        recommendations.append(rec)

    return recommendations
