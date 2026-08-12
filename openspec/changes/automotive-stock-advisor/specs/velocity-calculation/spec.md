# velocity-calculation — Specification

## Purpose

Calculates weighted average monthly velocity (recent months weighted heavier), coverage days, and projected demand per SKU per branch. These derived metrics feed the Planning Target calculation and classification engine.

## Requirements

### REQ-VC-001: Weighted average velocity
The system **shall** calculate velocity as a weighted average of monthly sales, with recent months weighted more heavily than older months. The weighting function **shall** be configurable and produce results in units/month.

#### Scenario: Flat sales history
- GIVEN 12 months of flat sales at 10 units/month
- WHEN the system calculates velocity
- THEN the weighted average velocity equals 10.0 units/month
- AND the result is identical to the simple average

#### Scenario: Rising sales trend
- GIVEN sales increasing from 10 to 21 units over 12 months
- WHEN the system calculates velocity
- THEN the weighted average is higher than the simple arithmetic mean
- AND recent months contribute proportionally more to the result

#### Scenario: Empty sales history
- GIVEN a SKU with zero sales records
- WHEN the system calculates velocity
- THEN velocity = 0.0 units/month
- AND the SKU is flagged as cold-start

#### Scenario: Shorter history accepted
- GIVEN a SKU with only 6 months of sales history
- WHEN the system calculates velocity
- THEN the system computes a weighted average over the 6 available months
- AND does not reject the SKU for insufficient history

### REQ-VC-002: Coverage days
The system **shall** calculate coverage days as 365 divided by the Stock Turn Ratio (Ingresos Año-12 / Stock Promedio-12). Coverage days represents the average number of days merchandise remains in stock until sold.

#### Scenario: Normal coverage calculation
- GIVEN annual revenue of 5605 and average stock value of 1830
- WHEN the system calculates coverage days
- THEN Stock Turn Ratio ≈ 3.06
- AND coverage days ≈ 119.2 days

#### Scenario: Zero average stock
- GIVEN average stock value of 0
- WHEN the system calculates coverage days
- THEN coverage days = 0.0 (avoids division by zero)
- AND no error is raised

### REQ-VC-003: Projected demand
The system **shall** calculate projected demand for a configurable period based on the weighted velocity. Projected demand = velocity × (period_days / 30).

#### Scenario: Monthly projection
- GIVEN velocity = 20 units/month and period = 30 days
- WHEN the system calculates projected demand
- THEN projected demand = 20.0 units

#### Scenario: Extended projection
- GIVEN velocity = 15 units/month and period = 55 days
- WHEN the system calculates projected demand
- THEN projected demand = 27.5 units

### REQ-VC-004: DC velocity aggregation
For distribution centers, the system **shall** calculate DC velocity as the sum of the DC's own historical sales velocity plus the sum of velocities of all dependent branches.

#### Scenario: DC with two dependent branches
- GIVEN a DC with own velocity of 10 units/month
- AND two dependent branches with velocities of 15 and 8 units/month
- WHEN the system calculates DC velocity
- THEN DC velocity = 10 + 15 + 8 = 33 units/month
- AND this aggregated velocity is used in the DC's Planning Target calculation

#### Scenario: DC with no dependents
- GIVEN a DC with no dependent branches
- WHEN the system calculates DC velocity
- THEN DC velocity equals the DC's own sales velocity only

## Edge cases

- Velocity = 0 (cold-start SKU with no sales history)
- Single month of sales history (minimum valid input)
- Negative sales values (returns/corrections — system should handle as negative units)
- Extremely high velocity (outlier detection — system should not cap but flag)
- Sales history with gaps (missing months treated as zero sales)
- DC with all zero-velocity dependents (DC velocity = own velocity only)

## Acceptance criteria

- AC-1: Weighted velocity for flat 12-month history at X units/month returns exactly X
- AC-2: Rising trend produces weighted average > simple arithmetic mean
- AC-3: Empty history returns velocity = 0.0 without error
- AC-4: Coverage days avoids division by zero when average stock = 0
- AC-5: DC velocity aggregation correctly sums own + dependent branch velocities
- AC-6: Velocity calculation is deterministic for the same input data

## Notes

- Exact weighting function deferred to design (spike uses linear 0.5→1.5 ramp)
- Velocity is persisted as a derived metric, not recalculated on every read
- Formulas validated in Phase 0 spike (51 tests passing)
