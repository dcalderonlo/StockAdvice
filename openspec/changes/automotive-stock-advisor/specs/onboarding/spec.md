# onboarding — Specification

## Purpose

Guides implementation-assisted branch activation through a structured process: DMS connection, sales backfill, branch manager assignment, and first test run. Onboarding is not self-service; a team member or partner accompanies the initial deployment.

## Requirements

### REQ-OB-001: DMS connection setup
The system **shall** guide the user through configuring a DMS connection for a new branch, including adapter selection, connection credentials, and schema validation.

#### Scenario: DMS connection configured
- GIVEN a new branch is being onboarded
- WHEN the user selects a DMS adapter and provides connection credentials
- THEN the system tests the connection
- AND validates that required tables/views are accessible
- AND reports any missing data sources

#### Scenario: DMS connection validation failure
- GIVEN a DMS adapter is configured but the connection fails
- WHEN the system tests the connection
- THEN the system displays the specific error (timeout, auth failure, missing table)
- AND does not proceed to the next onboarding step

### REQ-OB-002: Sales history backfill
The system **shall** import at least 12 months of historical sales data from the DMS during branch activation.

#### Scenario: Full 12-month backfill
- GIVEN a branch has 18 months of sales history in the DMS
- WHEN the onboarding process imports sales data
- THEN the system imports all 18 months
- AND validates data completeness (no gaps in monthly records)

#### Scenario: Insufficient sales history
- GIVEN a branch has only 6 months of sales history
- WHEN the onboarding process imports sales data
- THEN the system imports the available 6 months
- AND warns the user that classification accuracy may be limited
- AND allows the user to proceed (does not block)

#### Scenario: No sales history
- GIVEN a newly opened branch with zero sales history
- WHEN the onboarding process imports sales data
- THEN the system records an empty sales history
- AND all SKUs are flagged as cold-start
- AND the user is informed that manual demand overrides are required

### REQ-OB-003: Branch manager assignment
The system **shall** require a branch manager to be assigned before the first replenishment run can execute.

#### Scenario: Branch manager assigned
- GIVEN a new branch is being onboarded
- WHEN the user assigns a branch manager (existing user or new invite)
- THEN the branch manager is linked to the branch
- AND the branch manager receives an invitation email

#### Scenario: First run blocked without manager
- GIVEN a branch has no assigned branch manager
- WHEN the user attempts to trigger the first replenishment run
- THEN the system blocks the run
- AND displays a message requiring branch manager assignment

### REQ-OB-004: First test run
The system **shall** support a manual first test run that validates the end-to-end flow: catalog read → velocity calculation → classification → Planning Target → recommendation generation.

#### Scenario: First test run succeeds
- GIVEN a branch is fully configured (DMS connected, sales imported, manager assigned)
- WHEN the user triggers the first test run
- THEN the system reads catalog, stock, and sales from the DMS
- AND calculates velocity, classification, Planning Target, and Punto de Pedido
- AND generates recommendations (if any SKUs trigger)
- AND displays the results in the dashboard

#### Scenario: First test run with errors
- GIVEN a branch has incomplete data (e.g., missing lead times)
- WHEN the user triggers the first test run
- THEN the system completes the run with available data
- AND flags any missing data points in the results
- AND allows the user to review partial recommendations

### REQ-OB-005: Onboarding checklist
The system **shall** display an onboarding checklist tracking progress through each step: DMS connection → sales backfill → branch manager assignment → first test run → go-live.

#### Scenario: Onboarding progress tracked
- GIVEN a branch is being onboarded
- WHEN the user views the onboarding checklist
- THEN completed steps are marked with checkmarks
- AND the current step is highlighted
- AND the next step is indicated

#### Scenario: Onboarding complete
- GIVEN all onboarding steps are completed
- WHEN the user views the checklist
- THEN all steps are marked complete
- AND the branch status changes to "active"
- AND scheduled replenishment runs are enabled

### REQ-OB-006: User provisioning hierarchy
The system **shall** support hierarchical user provisioning: admin invites gerente, gerente invites coordinators, coordinator invites branch managers. Each invite specifies role + branch (or scope).

#### Scenario: Admin invites gerente
- GIVEN an admin wants to add a gerente
- WHEN the admin sends an invitation email
- THEN the invite specifies the gerente role with org-wide scope
- AND the recipient creates a password and activates their account

#### Scenario: Coordinator invites branch manager
- GIVEN a coordinator wants to add a branch manager for a branch in their scope
- WHEN the coordinator sends an invitation email
- THEN the invite specifies the warehouse_manager role and the specific branch
- AND the recipient creates a password and activates their account

## Edge cases

- DMS adapter not yet implemented for the tenant's DMS (onboarding blocked until adapter is built)
- Sales history import interrupted mid-way (system should resume from last successful month)
- Branch manager invite email bounces (system should flag and allow resend)
- First test run produces zero recommendations (valid — no SKUs below Punto de Pedido)
- Branch activated with only 1 SKU (valid but unusual — system should handle)
- Onboarding abandoned mid-process (branch remains in "pending" state, can be resumed)
- User invited with a role they already have (system should warn about role duplication)

## Acceptance criteria

- AC-1: DMS connection is validated before proceeding to next onboarding step
- AC-2: Sales history import covers at least 12 months when available
- AC-3: Branch manager assignment is required before first replenishment run
- AC-4: First test run validates the end-to-end flow and displays results
- AC-5: Onboarding checklist tracks progress through all steps
- AC-6: User provisioning follows the hierarchy (admin → gerente → coordinator → branch manager)
- AC-7: Target onboarding time: ≤ 28 days from kickoff to first live run

## Notes

- Onboarding is implementation-assisted (not self-service)
- Onboarding playbook should be documented separately for the implementation team
- Target: ≤ 28 days from kickoff to first live run (per proposal §8)
