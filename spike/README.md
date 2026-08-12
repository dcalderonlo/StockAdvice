# StockAdvice — Phase 0 Spike

A minimal, runnable validation of the core replenishment methodology for the
StockAdvice project. It proves that the formulas (Planning Target, Punto de
Pedido, Cantidad de Pedido, Volume Class, excess stock) behave sensibly with
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
| Stock | Stock Disponible (physically available) |
| Trans | Stock en Tránsito (inbound) |
| PP | Punto de Pedido (reorder point) |
| Cantidad | Cantidad de Pedido (only shown when triggered) |
| Source | `Inter-branch transfer from …`, `External supplier`, or `No action` |

A triggered row means `Stock Actual ≤ Punto de Pedido`. The engine then
recommends enough stock to bring the branch back up to Planning Target,
accounting for inbound transit.

## Formula reference

```
velocity          = weighted average monthly sales (recent months weighted heavier)
Planning Target   = (velocity / 30) × (Periodo de Stock + Stock de Seguridad)
Punto de Pedido   = Planning Target + (velocity / 30) × Tiempo de Pedido
Cantidad Pedido   = max(0, Planning Target − Stock Disponible − Stock en Tránsito)
Excess stock      = max(0, Stock Actual − Punto de Pedido)
Volume Class      = VC1..VC8 based on annual sales thresholds
```

### Known discrepancy with the source material

The Star Cooperation material (used as an internal formula reference) lists the
following example:

> monthly sales 20, Periodo de Stock 30, Stock de Seguridad 15, Tiempo de Pedido 10  
> → Planning Target = 37, Punto de Pedido = 47, Cantidad de Pedido = 12

Those numbers only work if **Planning Target is interpreted as including lead
time** (`20/30 × (30+15+10) ≈ 37`) and if **Punto de Pedido adds lead-time days
directly** (`37 + 10 = 47`). That interpretation is dimensionally inconsistent
and contradicts the proposal/design-brief definition:

> Planning Target = (ventas_mensuales / 30) × días_del_periodo  
> Punto de Pedido = Planning Target + Lead Time

This spike follows the **proposal/design-brief interpretation**, which gives:

| Metric | Proposal-aligned | Material example |
|--------|------------------|------------------|
| Planning Target | 30.0 | 37 |
| Punto de Pedido | 36.7 | 47 |
| Cantidad de Pedido | 5.0 | 12 |

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
3. `inventory` app: StockLevel, StockMovement, StockEnTransito.
4. `classification` engine (VC1–VC8, Lifecycle Stage).
5. `replenishment` engine with real source resolution and approval workflow.
6. `notifications` + `dashboard` with role-based views.
7. Scheduling via Django-Q2 and deployment docs.

Resolve before v1:

- The Planning Target / Punto de Pedido interpretation discrepancy documented
  above.
- Exact weighted-velocity weights (spike uses linear 0.5→1.5).
- Default Periodo de Stock, Stock de Seguridad, and Tiempo de Pedido values.
