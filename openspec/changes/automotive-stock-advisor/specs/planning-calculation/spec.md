# planning-calculation — Specification

## Purpose

Calculates Planning Target, Punto de Pedido, and Cantidad de Pedido per SKU per branch using the material-aligned formulas. These three metrics form the mathematical core of the replenishment advisory system.

## Requirements

### REQ-PC-001: Planning Target calculation
The system **shall** calculate Planning Target per the material-aligned formula:

**Planning Target = (velocity / 30) × (Periodo de Stock + Stock de Seguridad + Tiempo de Pedido)**

Planning Target INCLUDES lead time, per the source material's convention. The result is in units and represents the maximum stock level needed to cover the full replenishment cycle.

#### Scenario: Material example one
- GIVEN velocity = 20 units/month, Periodo de Stock = 30, Stock de Seguridad = 15, Tiempo de Pedido = 10
- WHEN the system calculates Planning Target
- THEN Planning Target = (20 / 30) × 55 = 36.67 units

#### Scenario: Material example two
- GIVEN velocity = 12 units/month, Periodo de Stock = 44, Stock de Seguridad = 22, Tiempo de Pedido = 11
- WHEN the system calculates Planning Target
- THEN Planning Target = (12 / 30) × 77 = 30.8 units

#### Scenario: Zero velocity
- GIVEN velocity = 0 units/month
- WHEN the system calculates Planning Target
- THEN Planning Target = 0.0 units
- AND no replenishment is triggered

#### Scenario: Negative velocity clamped
- GIVEN velocity = -5 units/month (data error)
- WHEN the system calculates Planning Target
- THEN velocity is clamped to 0.0
- AND Planning Target = 0.0 units

### REQ-PC-002: Punto de Pedido calculation
The system **shall** calculate Punto de Pedido as:

**Punto de Pedido = Planning Target + Tiempo de Pedido**

The addition is raw numeric (units + days), per the source material's example. This is the reorder trigger point.

#### Scenario: Material example one
- GIVEN Planning Target = 36.67 and Tiempo de Pedido = 10
- WHEN the system calculates Punto de Pedido
- THEN Punto de Pedido = 36.67 + 10 = 46.67

#### Scenario: Material example two
- GIVEN Planning Target = 30.8 and Tiempo de Pedido = 11
- WHEN the system calculates Punto de Pedido
- THEN Punto de Pedido = 30.8 + 11 = 41.8

### REQ-PC-003: Cantidad de Pedido calculation
The system **shall** calculate Cantidad de Pedido as:

**Cantidad de Pedido = max(0, Planning Target − Stock Disponible − Stock en Tránsito)**

Stock en Tránsito is treated as a separate concept from Stock Disponible. The result is never negative.

#### Scenario: Material example one
- GIVEN Planning Target = 36.67, Stock Disponible = 15, Stock en Tránsito = 10
- WHEN the system calculates Cantidad de Pedido
- THEN Cantidad de Pedido = max(0, 36.67 − 15 − 10) = 11.67 units

#### Scenario: Stock exceeds target
- GIVEN Planning Target = 10, Stock Disponible = 20, Stock en Tránsito = 0
- WHEN the system calculates Cantidad de Pedido
- THEN Cantidad de Pedido = 0 (no replenishment needed)

#### Scenario: Transit accounts for partial need
- GIVEN Planning Target = 100, Stock Disponible = 70, Stock en Tránsito = 20
- WHEN the system calculates Cantidad de Pedido
- THEN Cantidad de Pedido = max(0, 100 − 70 − 20) = 10 units

### REQ-PC-004: Per-branch and per-supplier lead time
The system **shall** support configurable lead time at the branch level or supplier level. If both are available, the system **shall** use the most specific value (per-supplier over per-branch default).

#### Scenario: Per-supplier lead time available
- GIVEN a branch has a default lead time of 14 days
- AND a specific supplier has a configured lead time of 7 days
- WHEN the system calculates Planning Target for a part from that supplier
- THEN the system uses 7 days as Tiempo de Pedido

#### Scenario: Default lead time fallback
- GIVEN no per-supplier lead time is configured
- WHEN the system calculates Planning Target
- THEN the system uses the branch-level default lead time

### REQ-PC-005: DC Planning Target with aggregated velocity
For distribution centers, the system **shall** use the aggregated DC velocity (own sales + dependent branches) in the Planning Target formula. The DC's Planning Target reflects the total demand it must serve.

#### Scenario: DC Planning Target with dependents
- GIVEN a DC with aggregated velocity of 33 units/month
- AND Periodo de Stock = 30, Stock de Seguridad = 15, Tiempo de Pedido = 10
- WHEN the system calculates DC Planning Target
- THEN Planning Target = (33 / 30) × 55 = 60.5 units

## Edge cases

- Zero lead time (instantaneous delivery — Planning Target covers only period + security)
- Very high velocity (Planning Target exceeds warehouse capacity — system should flag but not cap)
- Negative Stock Disponible (data error — system should flag and treat as 0)
- Negative Stock en Tránsito (data error — system should flag and treat as 0)
- Periodo de Stock = 0 (no operating period — unusual but valid)
- Stock de Seguridad = 0 (no safety buffer — valid for JIT scenarios)
- All parameters zero (Planning Target = 0, Punto de Pedido = 0, Cantidad de Pedido = 0)

## Acceptance criteria

- AC-1: Planning Target formula matches material example within 0.01 tolerance
- AC-2: Punto de Pedido = Planning Target + lead_time_days (raw numeric addition)
- AC-3: Cantidad de Pedido is never negative (min 0)
- AC-4: Stock en Tránsito is subtracted separately from Stock Disponible
- AC-5: Negative velocity is clamped to 0 before calculation
- AC-6: DC Planning Target uses aggregated velocity (own + dependents)

## Notes

- Formulas validated in Phase 0 spike (51 tests passing)
- Material-aligned convention adopted 2026-08-08 (lead time INCLUDED in Planning Target)
- Display rounding is separate from internal calculation (system stores float, rounds for UI)
