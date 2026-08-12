# dashboard — Specification

## Purpose

Provides role-based views for stock health, recommendations, classification results, and KPI tiles. Each role (branch manager, coordinator, gerente, admin) sees data scoped to their access level. Dashboard is the primary interface for reviewing and acting on recommendations.

## Requirements

### REQ-DS-001: Branch manager view
The system **shall** display a dashboard for branch managers showing: own branch stock health, pending recommendations count, approval history, override log, classification results, and KPI tiles (Stock Total, Rotación, Cobertura, Stock Obsoleto, Stock Excesivo).

#### Scenario: Branch manager sees own branch data
- GIVEN a branch manager logs in
- WHEN the dashboard loads
- THEN the manager sees only data for their assigned branch
- AND pending recommendations count is prominently displayed

#### Scenario: KPI tiles for branch manager
- GIVEN a branch manager views the dashboard
- WHEN the KPI tiles render
- THEN the tiles show: Stock Total, Rotación de Stock, Cobertura (días), Stock Obsoleto, Stock Excesivo
- AND all values are scoped to the manager's branch only

#### Scenario: Override log visibility
- GIVEN a branch manager has applied 3 demand overrides
- WHEN the manager views the override log widget
- THEN the log shows all 3 overrides with SKU, value, type, date, and status

### REQ-DS-002: Coordinator view
The system **shall** display a dashboard for coordinators showing: branches in their scope (read), aggregated KPIs within their scope, escalated items, inter-branch transfer status, and branch manager activity within their scope.

#### Scenario: Coordinator sees scoped branches
- GIVEN a coordinator with 5 branches in their scope
- WHEN the coordinator views the dashboard
- THEN the dashboard shows aggregated data for all 5 branches
- AND the coordinator can drill down into each branch individually

#### Scenario: Escalated items widget
- GIVEN 3 recommendations have been escalated to the coordinator
- WHEN the coordinator views the dashboard
- THEN the escalated items widget shows all 3 with branch, SKU, quantity, and escalation reason

#### Scenario: Inter-branch transfer status
- GIVEN 2 inter-branch transfers are in progress within the coordinator's scope
- WHEN the coordinator views the transfer status widget
- THEN the widget shows source branch, destination branch, SKU, quantity, and current state

### REQ-DS-003: Gerente view
The system **shall** display a dashboard for the gerente showing: org-wide KPIs, cross-coordinator transfer queue, classification review queue, and supervision data for all coordinators.

#### Scenario: Gerente sees org-wide KPIs
- GIVEN the gerente logs in
- WHEN the dashboard loads
- THEN KPI tiles show organization-wide aggregates (all branches, all coordinators)

#### Scenario: Cross-coordinator transfer queue
- GIVEN 2 cross-coordinator transfers are pending gerente decision
- WHEN the gerente views the dashboard
- THEN the cross-coordinator queue shows both transfers with source/destination coordinators, branches, and quantities

#### Scenario: Classification review queue
- GIVEN the monthly classification pass produced 12 Lifecycle Stage codes for review
- WHEN the gerente views the classification review widget
- THEN the widget shows all 12 items with SKU, proposed code, and confirm/override actions

### REQ-DS-004: Admin view
The system **shall** display a dashboard for administrators showing: all branches, user management, system configuration, and global KPIs.

#### Scenario: Admin sees all branches
- GIVEN an admin logs in
- WHEN the dashboard loads
- THEN the admin sees data for all branches across the organization
- AND can access user management and system configuration panels

### REQ-DS-005: KPI tile definitions
The system **shall** display the following KPI tiles with consistent definitions across all roles:

| KPI | Formula |
|-----|---------|
| Stock Total | Σ(current_stock × APP/DDP) |
| Rotación de Stock | Ingresos Año-12 / Stock Promedio-12 |
| Cobertura (días) | 365 / Stock Turn Ratio |
| Stock Obsoleto | merchandise without sales > 12 months |
| Stock Excesivo | Stock Actual − (Demanda Proyectada + Stock Seguridad) |

#### Scenario: KPI values match formula
- GIVEN a branch with known stock and sales data
- WHEN the KPI tiles render
- THEN each KPI value matches the defined formula within rounding tolerance

### REQ-DS-006: Classification results display
The system **shall** display classification results (Volume Class and Lifecycle Stage) per SKU in the dashboard, with filtering and sorting capabilities.

#### Scenario: Classification results table
- GIVEN a branch has 500 classified SKUs
- WHEN the branch manager views the classification results
- THEN a table shows each SKU with its Volume Class and Lifecycle Stage
- AND the manager can filter by Volume Class or Lifecycle Stage
- AND the manager can sort by either column

#### Scenario: Special flags highlighted
- GIVEN a SKU is classified as NS-C (campaign/recall)
- WHEN the classification results table renders
- THEN the NS-C flag is visually highlighted (distinct from normal classifications)

### REQ-DS-007: CSV export
The system **shall** allow CSV download for recommendation tables and KPI data from any role's dashboard view.

#### Scenario: Export recommendations to CSV
- GIVEN a branch manager has 47 pending recommendations
- WHEN the manager clicks "Export CSV"
- THEN a CSV file is downloaded containing all 47 recommendations
- AND the CSV includes: SKU, classification, quantity, source type, source branch, state, date

### REQ-DS-008: Real-time refresh
The system **shall** refresh KPI tiles automatically at a configured interval (default: every 60 seconds) using HTMX partial updates.

#### Scenario: KPI auto-refresh
- GIVEN a branch manager is viewing the dashboard
- WHEN 60 seconds pass
- THEN the KPI tiles refresh via HTMX without a full page reload
- AND the pending recommendations count updates if new recommendations were generated

## Edge cases

- Dashboard loads with zero recommendations (empty state with helpful message)
- Dashboard loads with zero stock data (branch not yet activated)
- KPI calculation takes too long (show cached values with "stale" indicator)
- User with multiple roles sees the union of all role-specific views
- Dashboard accessed on mobile device (responsive layout, not a separate app)
- CSV export with special characters in SKU descriptions (proper CSV escaping)
- HTMX refresh fails (graceful degradation — show last-known values with error indicator)

## Acceptance criteria

- AC-1: Branch manager sees only own branch data
- AC-2: Coordinator sees aggregated data for branches in their scope
- AC-3: Gerente sees org-wide KPIs and cross-coordinator transfer queue
- AC-4: Admin sees all branches plus user management and system configuration
- AC-5: KPI tiles match the defined formulas within rounding tolerance
- AC-6: Classification results are filterable and sortable by Volume Class and Lifecycle Stage
- AC-7: CSV export includes all visible columns and properly escapes special characters
- AC-8: KPI tiles auto-refresh every 60 seconds via HTMX

## Notes

- Rendering: server-side Django templates + HTMX (no SPA complexity)
- Styling: Pico.css (minimal, classless, no build step)
- Export: CSV via django-import-export or plain csv.writer
