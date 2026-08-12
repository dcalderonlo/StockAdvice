# demand-override — Specification

## Purpose

Allows users to override the system's calculated expected demand for a SKU. Every override triggers a mandatory type selection prompt (persistent, per-run, or with expiry) with clear explanations of each option. Overrides affect subsequent Planning Target and Cantidad de Pedido calculations.

## Requirements

### REQ-DO-001: Mandatory type selection
Every time a user overrides expected demand for a SKU, the system **shall** prompt the user to select the override type and **shall** explain each option. This prompt is mandatory and not skippable.

#### Scenario: Override with type selection
- GIVEN a branch manager wants to override the calculated demand for a SKU
- WHEN the manager enters a new demand value
- THEN the system displays a prompt with three options: Persistent, Per-run, With expiry
- AND each option includes an explanation of its behavior
- AND the manager must select one before the override is saved

#### Scenario: Explanation of Persistent
- GIVEN the override type selection prompt is displayed
- WHEN the user views the Persistent option
- THEN the system explains: "This override remains until you manually change it. Future runs will use this value instead of the calculated demand."

#### Scenario: Explanation of Per-run
- GIVEN the override type selection prompt is displayed
- WHEN the user views the Per-run option
- THEN the system explains: "This override applies to this run only. The next run will use the calculated demand value."

#### Scenario: Explanation of With expiry
- GIVEN the override type selection prompt is displayed
- WHEN the user views the With expiry option
- THEN the system explains: "This override remains until a specified date, after which the system reverts to calculated demand."
- AND the system prompts the user to enter an expiry date

### REQ-DO-002: Persistent override
A persistent override **shall** remain active until manually changed or removed by a user with override authority.

#### Scenario: Persistent override affects next run
- GIVEN a branch manager sets a persistent override of 25 units/month for SKU-X
- WHEN the next scheduled replenishment run executes
- THEN the system uses 25 units/month as the velocity for SKU-X
- AND does not recalculate velocity from sales history

#### Scenario: Persistent override persists across runs
- GIVEN a persistent override was set 3 runs ago
- WHEN the current replenishment run executes
- THEN the system still uses the overridden value
- AND the dashboard shows the override age (e.g., "overridden 45 days ago")

### REQ-DO-003: Per-run override
A per-run override **shall** apply only to the current replenishment run. The next run uses the calculated demand value.

#### Scenario: Per-run override applies once
- GIVEN a branch manager sets a per-run override of 30 units/month for SKU-X
- WHEN the current replenishment run completes
- THEN the recommendation for SKU-X uses 30 units/month
- AND the override is discarded after the run

#### Scenario: Next run uses calculated value
- GIVEN a per-run override was applied in the previous run
- WHEN the next replenishment run executes
- THEN the system uses the calculated velocity from sales history
- AND no override is applied

### REQ-DO-004: Override with expiry
An override with expiry **shall** remain active until the specified date, after which the system automatically reverts to calculated demand.

#### Scenario: Override active before expiry
- GIVEN a branch manager sets an override with expiry date of 2026-11-01
- WHEN a replenishment run executes on 2026-10-15
- THEN the system uses the overridden value

#### Scenario: Override expired
- GIVEN a branch manager set an override with expiry date of 2026-11-01
- WHEN a replenishment run executes on 2026-11-05
- THEN the system uses the calculated velocity from sales history
- AND the override is marked as expired

### REQ-DO-005: Override authority
Only the branch manager of the target branch **shall** have authority to apply demand overrides for that branch's SKUs.

#### Scenario: Branch manager applies override
- GIVEN a branch manager for Branch A
- WHEN the manager applies a demand override for a SKU in Branch A
- THEN the override is accepted and saved

#### Scenario: Non-manager cannot override
- GIVEN a user without branch manager role for Branch A
- WHEN the user attempts to apply a demand override for a SKU in Branch A
- THEN the system rejects the override
- AND displays an authorization error

### REQ-DO-006: Override affects calculations
When an override is active, the system **shall** use the overridden demand value in place of the calculated velocity for Planning Target, Punto de Pedido, and Cantidad de Pedido calculations.

#### Scenario: Override changes recommendation
- GIVEN calculated velocity = 10 units/month, but override = 20 units/month (persistent)
- WHEN the system calculates Planning Target
- THEN the system uses 20 units/month in the formula
- AND the resulting recommendation reflects the higher demand

### REQ-DO-007: Override log visibility
The system **shall** maintain a log of all overrides, visible in the branch manager's dashboard, showing: SKU, override value, type, set date, expiry date (if applicable), set by user, and current status (active/expired).

#### Scenario: Override log entry
- GIVEN a branch manager sets a persistent override
- WHEN the dashboard displays the override log
- THEN the log shows: SKU code, override value, type = "Persistent", set date, set by user, status = "Active"

#### Scenario: Override age warning
- GIVEN a persistent override that has been active for 80 days
- WHEN the dashboard displays the override log
- THEN the system displays a warning that the override is approaching 90 days
- AND suggests reviewing the override for drift

## Edge cases

- Override value = 0 (effectively marks SKU as zero-demand — system should accept but warn)
- Override value negative (data entry error — system should reject)
- Expiry date in the past (system should reject or auto-expire immediately)
- Multiple overrides for the same SKU (latest override wins, previous is archived)
- Override set on a cold-start SKU (valid — provides initial demand estimate)
- Override on an OBS-R SKU (system should warn that OBS-R SKUs are excluded from recommendations)
- Override persists after SKU is reclassified (override still applies until manually changed or expired)

## Acceptance criteria

- AC-1: Override type selection prompt is mandatory and not skippable
- AC-2: Each override type (Persistent, Per-run, With expiry) has a clear explanation
- AC-3: Persistent overrides survive multiple replenishment runs
- AC-4: Per-run overrides are discarded after the current run completes
- AC-5: Expired overrides automatically revert to calculated demand
- AC-6: Only the branch manager can apply overrides for their branch
- AC-7: Override log is visible in the dashboard with age warnings at 90 days

## Notes

- Override drift KPI: % of persistent overrides unchanged after 90 days (target < 10%)
- Override is stored as a separate entity from the calculated velocity
- Audit log records which role was used when applying the override
