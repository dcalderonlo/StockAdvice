# StockAdvice — Phase 0 Spike

A minimal, runnable validation of the core replenishment methodology for the
StockAdvice project. It proves that the formulas (Planning Target, Punto de
Pedido, Order Quantity, Volume Class, excess stock) behave sensibly with
realistic automotive data before investing in Django, PostgreSQL, DMS adapters,
or the full approval workflow.

## What this spike validates

- The canonical inventory formulas from the proposal and design brief are
  internally consistent and can be expressed as pure, testable functions.
- Weighted velocity favors recent months without overreacting to a single spike.
- Volume Class thresholds correctly segment fast, medium, and slow movers.
- The replenishment engine can scan fixture data and produce actionable
  recommendations (inter-branch transfer or external supplier fallback).
- Edge cases (zero sales, missing stock, missing history, negative clamping) are
  handled safely.

## What this spike is NOT

- No Django, no database, no migrations, no admin.
- No real DMS adapter; data is hardcoded in `stockadvice_spike/fixtures/sample_data.py`.
- No authentication, multi-tenancy, notifications, dashboard, or deployment.
- Source resolution is intentionally naive (one simulated sibling branch).

## Quick start

```bash
# From the spike/ directory
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run the console output
python run_console.py

# Run the test suite
pytest

# Optional: render an HTML page
python run_html.py -o recommendations.html
```

## Output interpretation

`run_console.py` prints a table with one row per SKU:

| Column | Meaning |
|--------|---------|
| SKU | Internal catalog code |
| Description | Human-readable part name |
| VC | Volume Class (VC1 fastest … VC8 slowest; blank = zero sales) |
| Stock | Available Stock (physically available) |
| Trans | In Transit Stock (inbound) |
| PP | Reorder Point (reorder point) |
| Cantidad | Order Quantity (only shown when triggered) |
| Source | `Inter-branch transfer from …`, `External supplier`, or `No action` |

A triggered row means `Current Stock ≤ Reorder Point`. The engine then
recommends enough stock to bring the branch back up to Planning Target,
accounting for inbound transit.

## Formula reference

```
velocity          = weighted average monthly sales (recent months weighted heavier)
Planning Target   = (velocity / 30) × (Stock Period + Safety Stock)
Reorder Point   = Planning Target + (velocity / 30) × Lead Time
Order Quantity   = max(0, Planning Target − Available Stock − In Transit Stock)
Excess stock      = max(0, Current Stock − Reorder Point)
Volume Class      = VC1..VC8 based on annual sales thresholds
```

### Known discrepancy with the source material

The Star Cooperation material (used as an internal formula reference) lists the
following example:

> monthly sales 20, Stock Period 30, Safety Stock 15, Lead Time 10  
> → Planning Target = 37, Reorder Point = 47, Order Quantity = 12

Those numbers only work if **Planning Target is interpreted as including lead
time** (`20/30 × (30+15+10) ≈ 37`) and if **Reorder Point adds lead-time days
directly** (`37 + 10 = 47`). That interpretation is dimensionally inconsistent
and contradicts the proposal/design-brief definition:

> Planning Target = (monthly_sales / 30) × period_days  
> Reorder Point = Planning Target + Lead Time

This spike follows the **proposal/design-brief interpretation**, which gives:

| Metric | Proposal-aligned | Material example |
|--------|------------------|------------------|
| Planning Target | 30.0 | 37 |
| Reorder Point | 36.7 | 47 |
| Order Quantity | 5.0 | 12 |

The discrepancy is surfaced here so the team can resolve the canonical formula
before v1. Either interpretation is implementable; the important thing is to
pick one and apply it consistently across the product, tests, and training
materials.

## Success criteria for this spike

- [x] `pytest` passes with 10+ formula tests.
- [x] `run_console.py` produces a readable table with recommendations.
- [x] Fast movers have high Volume Classes, slow movers low classes.
- [x] Cold-start SKUs (zero sales) produce no automatic recommendation.
- [x] Surplus branches can act as transfer sources for deficit branches.
- [x] Edge cases (zero sales, missing data, negative clamping) are safe.

## Next steps

If this spike is accepted, proceed to the full v1 implementation plan
(`sdd-tasks` for the automotive-stock-advisor change):

1. Django scaffold + `core` / `accounts` apps.
2. `branches` + `catalog` with DMS adapter interface and mock adapter.
3. `inventory` app: StockLevel, StockMovement, InTransitStock.
4. `classification` engine (VC1–VC8, Lifecycle Stage).
5. `replenishment` engine with real source resolution and approval workflow.
6. `notifications` + `dashboard` with role-based views.
7. Scheduling via Django-Q2 and deployment docs.

Resolve before v1:

- The Planning Target / Reorder Point interpretation discrepancy documented
  above.
- Exact weighted-velocity weights (spike uses linear 0.5→1.5).
- Default Stock Period, Safety Stock, and Lead Time values.
