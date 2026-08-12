# recommendation-engine — Specification

## Purpose

Generates replenishment recommendations with source resolution, prioritizing inter-branch transfers over external supplier orders. Handles multi-source split, partial fulfillment, DC topology, and excess stock protection to ensure source branches do not fall below their own Punto de Pedido.

## Requirements

### REQ-RE-001: Recommendation trigger
The system **shall** generate a recommendation for each SKU where current stock (Stock Disponible + Stock en Tránsito) is less than or equal to the Punto de Pedido.

#### Scenario: Stock below Punto de Pedido
- GIVEN a SKU with Stock Disponible = 15, Stock en Tránsito = 10, Punto de Pedido = 47
- WHEN the replenishment run evaluates the SKU
- THEN current stock (25) ≤ Punto de Pedido (47) triggers a recommendation
- AND Cantidad de Pedido is calculated

#### Scenario: Stock above Punto de Pedido
- GIVEN a SKU with Stock Disponible = 50, Punto de Pedido = 47
- WHEN the replenishment run evaluates the SKU
- THEN no recommendation is generated for this SKU

#### Scenario: Stock exactly at Punto de Pedido
- GIVEN a SKU with Stock Disponible = 37, Stock en Tránsito = 0, Punto de Pedido = 37
- WHEN the replenishment run evaluates the SKU
- THEN the recommendation IS triggered (≤, not <)

### REQ-RE-002: Source resolution — inter-branch transfer first
The system **shall** check other branches for excess stock before recommending external supplier orders. Excess stock is defined as: **max(0, current_stock − Punto de Pedido)**. A branch can transfer only up to its excess stock.

#### Scenario: Transfer from single source branch
- GIVEN Branch A needs 12 units of SKU-X
- AND Branch B has excess stock of 20 units of SKU-X
- WHEN the system resolves the source
- THEN the system recommends an inter-branch transfer of 12 units from Branch B to Branch A
- AND Branch B retains 8 units of excess stock after the transfer

#### Scenario: No excess stock at any branch
- GIVEN Branch A needs 15 units of SKU-X
- AND no other branch has excess stock of SKU-X
- WHEN the system resolves the source
- THEN the system recommends an external supplier order for 15 units
- AND no source branch is named

### REQ-RE-003: Multi-source split
The system **shall** split a recommendation across multiple source branches when no single branch has sufficient excess stock to fulfill the full quantity.

#### Scenario: Split across two source branches
- GIVEN Branch A needs 20 units of SKU-X
- AND Branch B has excess of 8 units
- AND Branch C has excess of 15 units
- WHEN the system resolves the source
- THEN the system recommends 8 units from Branch B and 12 units from Branch C
- AND Branch C retains 3 units of excess stock

### REQ-RE-004: Partial fulfillment alert
When total excess stock across all candidate branches is less than the recommended quantity, the system **shall** alert the branch manager, coordinator(s), and gerente del departamento about partial availability and recommend external purchase for the remainder.

#### Scenario: Partial transfer with external remainder
- GIVEN Branch A needs 30 units of SKU-X
- AND total excess stock across all branches is 18 units
- WHEN the system resolves the source
- THEN the system recommends 18 units via inter-branch transfer
- AND recommends 12 units via external supplier
- AND alerts branch manager, coordinator(s), and gerente about partial fulfillment

### REQ-RE-005: DC topology in source resolution
For branches dependent on a DC, the system **shall** first check the parent DC for excess stock. If the DC lacks sufficient stock, the system **shall** search other branches (not just the DC's children) for excess stock.

#### Scenario: DC fulfills dependent branch
- GIVEN a sucursal needs 10 units of SKU-X
- AND its parent DC has excess of 15 units of SKU-X
- WHEN the system resolves the source
- THEN the system recommends a transfer from the DC to the sucursal

#### Scenario: DC insufficient, other branches searched
- GIVEN a sucursal needs 25 units of SKU-X
- AND its parent DC has excess of only 10 units
- AND another branch (not in the same DC group) has excess of 20 units
- WHEN the system resolves the source
- THEN the system recommends 10 units from the DC and 15 units from the other branch

### REQ-RE-006: DC self-replenishment
For distribution centers, the system **shall** calculate projected stock after fulfilling inter-branch transfers to dependent branches. If projected stock falls below the DC's own Punto de Pedido, the system **shall** recommend an external purchase order for the DC.

#### Scenario: DC needs replenishment after transfers
- GIVEN a DC with Stock Disponible = 100 and Punto de Pedido = 60
- AND the DC must transfer 50 units to dependent branches
- WHEN the system evaluates the DC
- THEN projected stock after transfers = 50
- AND 50 ≤ 60 triggers a DC replenishment recommendation
- AND the source is always "external supplier" for DC replenishment

### REQ-RE-007: Recommendation content
Each recommendation **shall** include: SKU, classification code, quantity, source type (transfer/supplier), source branch (if transfer), and projected coverage after fulfillment.

#### Scenario: Complete recommendation
- GIVEN a replenishment run generates a recommendation
- WHEN the recommendation is created
- THEN it includes: internal SKU code, Volume Class/Lifecycle Stage, Cantidad de Pedido, source type, source branch (if transfer), and projected coverage days after fulfillment

### REQ-RE-008: Lifecycle-stage-based exclusion
The system **shall** exclude SKUs classified as OBS-R (Obsolete, >24 months no sales) and NS-NS (Non-stock) from automatic recommendations.

#### Scenario: OBS-R excluded
- GIVEN a SKU classified as OBS-R
- WHEN the replenishment run evaluates the SKU
- THEN no recommendation is generated
- AND the SKU remains visible in the catalog for historical reference

#### Scenario: NS-NS excluded
- GIVEN a SKU classified as NS-NS
- WHEN the replenishment run evaluates the SKU
- THEN no recommendation is generated
- AND the SKU is only ordered per individual request

### REQ-RE-009: Cold-start SKU handling
The system **shall** not generate automatic recommendations for SKUs with zero sales history. These SKUs are flagged as requiring manual override.

#### Scenario: Cold-start SKU flagged
- GIVEN a SKU with zero sales history
- WHEN the replenishment run evaluates the SKU
- THEN the system skips automatic recommendation
- AND flags the SKU as "requires manual override"
- AND notifies the branch manager

## Edge cases

- All branches have zero excess stock (full external supplier recommendation)
- Source branch's excess stock is exactly equal to the needed quantity
- Cross-reference group where one equivalent has excess and the other needs stock
- DC with no dependent branches (DC evaluated as a regular branch)
- Recommendation quantity = 0 (stock exactly meets Planning Target — no action)
- Multiple SKUs needing the same source branch (source branch excess must be shared)
- Transfer recommendation for a SKU that is OBS-P at the source but Active at the destination

## Acceptance criteria

- AC-1: Inter-branch transfer is always checked before external supplier
- AC-2: Source branch never falls below its own Punto de Pedido after transfer
- AC-3: Partial fulfillment generates alerts to branch manager, coordinator(s), and gerente
- AC-4: OBS-R and NS-NS SKUs are excluded from automatic recommendations
- AC-5: Cold-start SKUs are flagged for manual override, not auto-recommended
- AC-6: Each recommendation includes SKU, classification, quantity, source type, source branch, and projected coverage

## Notes

- System never executes transfers or orders — recommendations are advisory only
- External supplier recommendations do not name a specific supplier (purchasing department handles off-system)
- DC self-replenishment source is always "external supplier" (DC is the source for its dependents)
