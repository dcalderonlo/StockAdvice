# Proposal: Automotive Stock Advisor

## Metadata

| Field | Value |
|-------|-------|
| Change slug | `automotive-stock-advisor` |
| Status | draft — multi-sector ready |
| Date | 2026-07-29 |
| Owner | Product (pending assignment) |
| Domain | Multi-sector inventory management (v1 default: automotive aftermarket) |

## 1. Intent

Multi-branch organizations operate in a permanent tension between **availability** (too much stock → excess capital, obsolescence) and **capital** (too little stock → lost sales, poor service support). Inventory holding cost exceeds **20% annually** (damaged/lost parts, insurance, space, labor, capital cost). Today, replenishment is manual: managers eyeball spreadsheets, guess quantities, and miss the mathematical optimum.

This system introduces a **scheduled, advisory replenishment engine** for multi-sector organizations (concesionarios, farmacéuticas, ferreterías, manufactureras, etc.). It reads live data from the DMS/ERP, calculates classification (Volume Class / Lifecycle Stage), velocity, Planning Target, Punto de Pedido, and Cantidad de Pedido per SKU, then generates concrete recommendations — first trying inter-branch transfers, then external supplier fallback. Humans approve every action; the system never writes stock.

## 2. Goals

1. **Reduce Stock Excesivo** — cut excess stock (Stock Actual − Demanda Proyectada − Stock Seguridad) by ≥25% within 6 months of deployment.
2. **Improve Rotación de Stock** — increase Stock Turn Ratio (Ingresos Año-12 / Stock Promedio-12) by ≥15% within 6 months.
3. **Reduce Stock Obsoleto** — cut merchandise without sales >12 months by ≥20% within 12 months.
4. **Cut time-to-reorder** — from ~2 hours manual spreadsheet work per run to <15 minutes review-and-approve per branch.
5. **Increase inter-branch transfer rate** — ≥40% of recommendations resolved via internal transfer before external ordering.
6. **Achieve ≥80% recommendation acceptance** (approved or handled) within first quarter.

## 3. Non-Goals (v1)

- Vehicle compatibility (model/year fitment lookup)
- Core/return tracking (reverse logistics)
- Multi-tenant SaaS (single tenant v1; `tenant_id` present from day 1)
- Multi-region deployment
- Self-service onboarding (initial onboarding is implementation-assisted)
- Automated seasonal adjustment (estacionalidad / Ciclo Temporal patterns)
- Automated obsoletion detection (classification is calculated, but lifecycle stage transitions require gerente review)
- External supplier identification in recommendations (branch manager investigates)
- System-owned parts catalog (catalog is read from DMS)
- Advanced analytics (forecast accuracy, recommendation quality scoring)
- Purchasing department workflow (compras) — the system informs; humans coordinate with the purchasing department off-system. The purchasing department is out of scope for v1.

## 4. Target Users & Personas

### Administrator
- **Who**: IT or operations lead at the tenant organization.
- **Responsibilities**: configures system, manages branches at the system level, invites users (including gerente, coordinators, and branch managers), assigns roles, sets system-wide escalation thresholds, monitors consolidated KPIs across all branches. Admin does NOT handle cross-coordinator escalations or classification reviews (gerente responsibilities).
- **Access**: all branches, all data, all users.

### Gerente del Departamento (Department Manager)
- **Who**: head of the parts department or operations manager at the multi-branch organization.
- **Responsibilities**: handles cross-coordinator escalations and transfers (when a transfer or escalation crosses coordinator boundaries), reviews lifecycle stage transitions, confirms special flags (NS-C campaign/recall, NS-NS non-stock), approves escalated recommendations that cross coordinator scope, supervises all coordinators. Gerente does NOT handle day-to-day branch operations (coordinator's responsibility) or system configuration (admin's responsibility).
- **Access**: all branches (read + approval authority for cross-coordinator cases), global KPIs visibility across the whole organization. Can manage users with gerente role and below. Cannot configure system-wide settings (admin-only).

### Warehouse Coordinator
- **Who**: regional or group-level supervisor overseeing a subset of branches.
- **Responsibilities**: manages branches within their scope, invites users (branch managers) for branches in their scope, assigns roles within their scope, sets escalation thresholds for their scope, reviews escalated recommendations including complex inter-branch transfers (within their scope), receives notifications on approvals and stock-out alerts, supervises all branch managers in their scope. Coordinator does NOT handle cross-coordinator transfers, lifecycle transitions, or special flags (gerente responsibilities).
- **Access**: branches in their scope (read + approval authority), global KPIs visibility within their scope. Can manage branches, users, and roles within their scope. Cannot configure system-wide settings (admin-only). Supervises all branch managers in their scope.

### Warehouse Manager (one per branch)
- **Who**: person responsible for parts inventory at a specific location.
- **Responsibilities**: reviews Punto de Pedido alerts, approves/rejects/handles recommendations, applies demand overrides (with type selection), marks non-transferable recommendations as handled once external replenishment is coordinated off-system with the purchasing department (out of scope for v1), escalates high-impact recommendations, reviews classification output for their branch.
- **Access**: own branch only.

## 5. User Scenarios

### Scenario 1: Scheduled run computes Punto de Pedido → recommendation generated
1. System triggers weekly run for Branch A.
2. Engine reads live stock, sales movements (12 months), lead times from DMS.
3. For each SKU: calculates classification (VC1–VC8 / New / Obsolete / Inactive), velocity (weighted average), Planning Target = (ventas_mensuales / 30) × días_del_periodo, Punto de Pedido = Planning Target + Lead Time.
4. SKU "Brake Pads" (VC3): Stock Disponible = 15, Stock en Tránsito = 10, Planning Target = 37, Punto de Pedido = 47. Current stock (15) ≤ Punto de Pedido (47) → trigger.
5. Cantidad de Pedido = Planning Target (37) − Stock Disponible (15) − Stock en Tránsito (10) = **12 units**.
6. Source resolution: check other branches for surplus → Branch B has excess → recommend inter-branch transfer. Else recommend external supplier order (no supplier named).
7. Recommendation enters `pending` state. Branch manager and coordinator notified.

### Scenario 2: Branch manager reviews and approves
1. Branch manager logs in, sees 47 pending recommendations.
2. Reviews line by line: approves 30 (system generates transfer orders or purchase requests), rejects 5 (knows of incoming shipment not yet in DMS), marks 12 as `handled` (already acted on manually).
3. For one SKU, manager disagrees with projected demand → clicks override → system prompts: "Is this override persistent, per-run, or with expiry?" → manager selects "persistent, 3 months" → system records override and recalculates.
4. One recommendation exceeds configured value threshold → system auto-escalates to coordinator.

### Scenario 3: Classification engine derives codes from sales data
1. Periodic classification pass runs (e.g., monthly).
2. For each SKU: count sales/year → assign Volume Class (VC1 >250, VC2 121–250, ..., VC8 1–3).
3. New SKU added 4 months ago with 18 sales in first 6 months → classify as **N1** (Lifecycle Stage: New, high velocity).
4. SKU with no sales >12 months but still in stock → classify as **OBS-P** (Lifecycle Stage: Obsolete, pre-obsolescence).
5. SKU with no sales >24 months → classify as **OBS-R** (Lifecycle Stage: Obsolete, obsolescence).
6. SKU with no sales >12 months and no stock → classify as **Inactive** (Lifecycle Stage: Inactive).
7. Classification results visible in dashboard; gerente reviews and confirms (except automatic Volume Classes which are applied).

### Scenario 4a: Cold-start SKU requires manual override
1. New part line added to DMS catalog (primary manufacturer code + internal SKU code).
2. Scheduled run encounters SKU with zero sales history → system skips automatic recommendation, flags as "requires manual override."
3. Branch manager sees flag → applies initial demand estimate (per-run override) → next run includes the SKU in calculations.

### Scenario 4b: Cross-manufacturer equivalent reference lookup
1. Customer asks for a part with primary manufacturer code 12345-ABC from Manufacturer X.
2. Branch manager searches the system by primary manufacturer code; the system queries the DMS for "primary manufacturer code 12345-ABC and equivalents".
3. DMS returns: 12345-ABC is related to 67890-DEF from Supplier Y (both currently manufactured; equivalent references per the DMS).
4. DMS also returns aggregated stock AND aggregated KPIs for the cross-manufacturer group: 4 units of 12345-ABC + 6 units of 67890-DEF = 10 units across both references. The system also aggregates KPIs across the group: combined velocity, combined coverage days, consolidated classification (most conservative lifecycle stage wins — if 12345-ABC is Active and 67890-DEF is Pre-Obsolete, the group is treated as Pre-Obsolete for review purposes).
5. The system uses the aggregated stock and aggregated KPIs (10 units, combined velocity, etc.) for the coverage calculation; no Punto de Pedido trigger if coverage is above threshold.
6. If stock had been 0 across both references, the system would query alternative manufacturer equivalents as a fallback.

### Scenario 5: Lifecycle stage drives behavior
1. SKU classified as **NS-C** (Campaign / Recall) → linked to recall; system flags for special handling (may be assigned to specific customers; different notification logic).
2. SKU classified as **NS-NS** (Non-stock / Individual order) → NOT auto-replenished; ordered per individual request only.
3. SKU classified as **OBS-R** (Obsolete, >24 months no sales) → excluded from recommendations; remains visible in catalog for historical reference.

## 6. Functional Requirements

### Catalog & Data Ingestion (Reads)
- Read parts catalog from DMS: internal SKU code (primary key), primary manufacturer code, alternative manufacturer codes (1 Part ↔ M alternative manufacturer cross-reference). The system also reads cross-reference relationships from the DMS (substitutable references, alternative denominations, successor/predecessor references). The DMS is the source of truth; the system consumes them as-is. The system does not maintain its own cross-reference tables.
- Read live stock levels from DMS per branch warehouse (Stock Disponible).
- Read sales movements: POS public sales + workshop consumption (outbound); purchase entries (inbound).
- Read Stock en Tránsito (units in transit to the branch, from any source: supplier purchase orders, in-flight inter-branch transfers). If unavailable in the DMS, the system can track transfers it has itself recommended (the system knows it advised an inter-branch transfer; once the branch manager marks it as approved, the system considers those units in transit until marked received). This is v1-ready.
- Read Lead Time per supplier (or per product, if available from DMS or config).
- Read branch topology: branch type (sucursal or centro de distribución), parent branch (for sucursales that depend on a DC), branch managers. A distribution center (DC) is a branch configured to supply other branches; it has its own stock, sales, and Punto de Pedido calculated independently. Multi-level DC hierarchies (DC depending on another DC) are out of scope for v1.
- Import 12+ months of historical sales at branch activation.
- Sync frequency: per-run (live read at recommendation generation time).

### Velocity Calculation (Calculates)
- Weighted average velocity: recent months weighted heavier (exact weighting formula deferred to design).
- Derived metrics persisted: velocity (units/month), coverage days (365 / Stock Turn Ratio), projected demand for configured period.
- For distribution centers, velocity is the historical sales rate of the DC itself PLUS the sum of historical sales of its dependent branches: `velocity_dc = velocity_dc_own_sales + Σ velocity_dependent_branches`. The DC's velocity reflects the total demand it must serve (own sales + transfers to children).

### Classification Engine (Calculates)
- Periodic classification pass (e.g., monthly) over the catalog.
- **Volume Class (VC)**: by sales volume per year. VC1 = highest volume (>250 sales/year), VC2 (121–250), VC3 (61–120), VC4 (31–60), VC5 (15–30), VC6 (7–14), VC7 (4–6), VC8 = lowest volume (1–3 sales/year).
- **Lifecycle Stage — New** (first 6 months from entry): N1 (>15 sales in first 6 months), N2 (4–15), N3 (0–3). Special: NS-C (campaign / recall), NS-NS (non-stock / individual order).
- **Lifecycle Stage — Obsolete**: OBS-S (replacement of old reference), OBS-N (>6 months in stock / never sold), OBS-P (>12 months no sales), OBS-R (>24 months no sales).
- **Lifecycle Stage — Inactive**: >12 months no sales, no stock.
- Classification drives replenishment behavior (e.g., NS-C = special handling, NS-NS = no auto-replenishment, OBS-R = exclude).
- Gerente reviews classification results; Volume Classes applied automatically, Lifecycle Stage codes require gerente confirmation for special flags (NS-C campaign/recall, NS-NS non-stock). The gerente may delegate classification review to a designated coordinator within their scope (the designated coordinator becomes the primary reviewer for their scope; gerente retains oversight).

### Planning Target & Punto de Pedido Calculation (Calculates)
- **Planning Target** = (ventas_mensuales / 30) × (Periodo de Stock + Stock de Seguridad + Tiempo de Pedido). Per the source material's convention, Planning Target (Stock Máximo) INCLUDES lead time in the divisor. The system covers demand for the full replenishment cycle (operating period + safety buffer + lead time).
- **Punto de Pedido** = Planning Target + Tiempo de Pedido (raw, in days, per the source material's example). The "+Tiempo de Pedido" is a literal numeric addition (dimensionally inconsistent but matches the material's example: PT 37 + lead 10 = PP 47).
- Per-branch or per-supplier lead time (configurable).

### Cantidad de Pedido Calculation (Calculates)
- **Cantidad de Pedido** = Planning Target − Stock Disponible − Stock en Tránsito.
- Stock en Tránsito treated as separate concept from Stock Disponible.

### Recommendation Generation
- Triggered by schedule (weekly/biweekly/monthly/quarterly, per-branch config).
- For each SKU where current stock ≤ Punto de Pedido: calculate Cantidad de Pedido.
- Source resolution: check other branches for **excess stock** (defined as `current_stock − Punto de Pedido`). A branch can transfer units to other branches only up to the amount of its excess stock, ensuring the source branch does not fall below its own Punto de Pedido. The system may split a recommendation across multiple source branches. If total excess stock across all candidate branches is less than the recommendation, the system alerts the branch manager, coordinator(s), and gerente del departamento about partial availability and recommends external purchase for the remainder (using the standard email + dashboard alert flow).
- Each recommendation includes: SKU, classification code, quantity, source type (transfer/supplier), source branch (if transfer), projected coverage after fulfillment.
- For distribution centers, the Punto de Pedido check considers projected stock after fulfilling inter-branch transfers to dependent branches: `stock_proyectado_dc = stock_actual_dc − Σ unidades_a_transferir_a_dependientes`. If `stock_proyectado_dc ≤ Punto de Pedido`, the system recommends an external purchase order (Cantidad de Pedido = Planning Target − Stock Disponible − Stock en Tránsito). The source is always "external supplier" for DC replenishment (the DC is itself the source of its dependents). Notification recipients: branch manager of the DC, coordinator(s) that depend on the DC, gerente del departamento.
- **Edge case: insufficient DC stock**: if the natural source (a DC) lacks sufficient stock to fulfill the recommendation, the system searches OTHER branches (not just the DC's children) for excess stock above their Punto de Pedido. The recommendation may be split across multiple sources (DC + other branches). If partial availability still does not cover the full recommendation, the system alerts the branch manager, coordinator(s), and gerente del departamento about the partial fulfillment and the remaining gap (using the standard email + dashboard alert flow; no new alert types).

### Approval Workflow
- State machine: `pending → approved | rejected | handled | ordered`.
- Default approver: branch manager (own branch).
- Escalation: recommendations crossing configured threshold (value, volume, or impact) auto-escalate to coordinator; coordinator may further escalate to gerente (or admin for system-wide cases).
- Approval actions: approve (proceed), reject (skip this run), handled (already done externally), ordered (confirmation after external action).

### Demand Override UX
- Every time a user overrides expected demand for a SKU, the system **prompts the user to select the override type** and **explains each option**:
  - **Persistent**: override remains until manually changed.
  - **Per-run**: override applies to this run only; next run uses calculated value.
  - **With expiry**: override remains until a specified date, then reverts.
- This is a mandatory runtime prompt, not a global setting. The user must make this choice each time they override.

### Notifications
- Channels: email + in-app dashboard.
- Recipients: branch manager (own branch recommendations), coordinator (escalations + cross-branch alerts).
- Admin receives no direct notifications; views consolidated state in dashboard.

### Dashboard (Role-Based Views)
- **Branch manager view**: own branch stock health, pending recommendations, approval history, override log, classification results.
- **Coordinator view**: branches in their scope (read), KPIs within their scope (Stock Total, Rotación, Cobertura, Stock Obsoleto, Stock Excesivo for their scope), escalated items, inter-branch transfer status (within their scope), branch manager activity in their scope.
- **Admin view**: all branches, user management, system configuration, global KPIs (Stock Total, Rotación, Cobertura, Stock Obsoleto, Stock Excesivo).

### Onboarding
- Implementation-assisted: team or partner accompanies initial deployment.
- Per-branch process: DMS connection → local stock import → 12-month sales backfill → branch manager assignment → first test run.
- User provisioning: admin/gerente/coordinator invite users by email based on hierarchy (admin invites gerente, gerente invites coordinators, coordinator invites branch managers); each user assigned role + branch.

### User Management
- A user can have one or more roles. Effective permissions are the union of all assigned roles. Audit logs record which role was used for each action. The admin panel warns about role combinations that may create conflicts of interest (e.g., a user with both admin and warehouse manager roles can configure the system and operate on their own branch). Roles are not exclusive by default. Available roles: administrator, gerente (department manager), warehouse manager, warehouse coordinator.
- Branch configuration: each branch has a type ('sucursal' or 'centro de distribución'). A regular branch may have a parent_branch_id pointing to its DC. DCs are top-level (no parent) in v1; multi-level DC hierarchies are v2. Branch type is set at onboarding or via the admin/gerente panel.
- Branch assignment: manager linked to one specific branch; coordinator assigned to a subset of branches (multiple coordinators supported, each with their own scope); gerente supervises all branches (org-wide role); admin has global access.
- Invitation flow: email-based, role + branch specified at invite time.

## 7. Business Rules

1. **Replenishment hierarchy**: inter-branch transfer first → external supplier fallback. The system always checks for surplus stock at other branches before recommending external purchase.
2. **Punto de Pedido trigger**: when current stock ≤ Punto de Pedido, recommend Cantidad de Pedido.
3. **Stock en Tránsito**: treated separately from Stock Disponible in Cantidad de Pedido calculation.
4. **Classification is calculated, not manual**: system runs periodic classification pass over catalog, derives Volume Class (VC1–VC8) and Lifecycle Stage (New, Obsolete, Inactive) codes per SKU from sales data. Special flags (NS-C campaign/recall, NS-NS non-stock) require gerente confirmation.
5. **Lifecycle stages drive behavior**:
   - Lifecycle Stage: New (0–6 months from first entry): N1/N2/N3 codes; may require special handling.
   - Lifecycle Stage: Active (with peak consumption): VC1–VC8 codes; normal replenishment.
   - Lifecycle Stage: Pre-Obsolete (>12 months without sales): OBS-P code; flagged for review.
   - Lifecycle Stage: Obsolete (>24 months without sales): OBS-R code; excluded from recommendations.
   - Non-Stocking: NS-NS code; no auto-replenishment, ordered per individual request.
6. **Override UX**: every demand override triggers mandatory type selection (persistent / per-run / with expiry) with explanations. Not skippable.
7. **Cold-start mandatory override**: SKUs with zero sales history cannot receive automatic recommendations. Manual demand override (any type) required before system evaluates them.
8. **Advisory-only**: system generates recommendations; it never modifies DMS stock, places orders, or executes transfers. All actions require human approval and execution.
9. **Single tenant, multi-branch**: v1 operates as single tenant with multiple branches. Data model includes `tenant_id` on all entities to enable future multi-tenancy without migration.
10. **Part identity**: internal SKU code is primary key. The DMS maintains cross-reference relationships (substitutable references, alternative denominations, successor/predecessor references); the system consumes these for stock aggregation, recommendation generation, and lifecycle tracking. The system does not redefine or duplicate these relationships.
11. **Escalation by threshold**: recommendations exceeding configured value, volume, or impact thresholds auto-escalate from branch manager to coordinator (or gerente if coordinator threshold crossed; gerente may further escalate to admin for system-wide cases). Thresholds configurable per tenant.
12. **External replenishment off-system**: external replenishment is the responsibility of the purchasing department (compras), which is out of scope for v1. The system generates a recommendation flag and an alert; the purchasing department acts off-system. The system does not name a specific supplier in any recommendation.
13. **Cross-coordinator transfer**: cross-coordinator transfers (between branches in different coordinator scopes) are decided by the gerente. The source and destination coordinators are notified but do not approve. If the gerente rejects, the transfer is not executed. Single-coordinator transfers (within the same scope) follow the standard branch manager → coordinator approval flow.
14. **Excess stock for inter-branch transfer**: a branch can transfer units to other branches only up to the amount of its excess stock, defined as `current_stock − Punto de Pedido`. This ensures the source branch does not fall below its own Punto de Pedido when fulfilling transfers. The system may split a recommendation across multiple source branches based on their available excess. If total excess stock across all candidates is less than the recommendation, the system alerts the destination branch manager, coordinator(s), and gerente del departamento about partial availability and recommends external purchase for the remainder.

## 8. KPIs & Success Metrics

### Primary KPIs
- **Stock Total** = Σ(current_stock × APP/DDP) — total capital tied up in inventory.
- **Rotación de Stock** = Ingresos Año-12 / Stock Promedio-12 — how many times stock sells in 12 months. Target: ≥15% increase within 6 months.
- **Cobertura (días)** = 365 / Stock Turn Ratio — average days merchandise is available until sold. Target: optimize toward balanced cost point.
- **Stock Obsoleto** = merchandise without sales >12 months. Target: ≥20% reduction within 12 months.
- **Stock Excesivo** = Stock Actual − (Demanda Proyectada + Stock Seguridad). Target: ≥25% reduction within 6 months.
- **Stock de Seguridad** = additional buffer for peaks and delays (configurable per branch/SKU).
- **Stock Máximo** = Periodo de Stock + Stock de Seguridad (= Planning Target component). Per the material's convention, Planning Target additionally includes Tiempo de Pedido.
- **Punto de Pedido** = Planning Target + Tiempo de Pedido (raw, matches material).
- **Cantidad de Pedido** = Planning Target − Stock Disponible − Stock en Tránsito.

### Secondary Process KPIs
- **Time-to-reorder**: average time from recommendation generation to approval/action. Target: <15 minutes per run.
- **Recommendation acceptance rate**: % of recommendations approved or marked handled (not rejected). Target: ≥80%.
- **Inter-branch transfer rate**: % of recommendations resolved via internal transfer vs. external order. Target: ≥40%.
- **Override drift**: % of persistent overrides that remain unchanged after 90 days. Target: <10%.
- **Onboarding time**: days from kickoff to first live run. Target: ≤28 days.

## 9. Risks & Open Questions

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| DMS schema varies across organizations | High | Abstract DMS integration behind adapter interface; initial implementation informs adapter design. |
| Lead time source unclear (per-supplier config vs. derived from purchase orders) | Medium | v1: configurable per supplier or per branch. v2: derive from historical PO data. |
| Classification edge cases (e.g., seasonal SKUs, campaign parts with irregular sales) | Medium | Gerente reviews classification results; special flags (NS-C, NS-NS) require confirmation (delegable to a designated coordinator within their scope). v2: automated seasonal adjustment. |
| Obsolescence gradations require gerente UX for review | Medium | Dashboard shows lifecycle stage per SKU; gerente (or delegated coordinator) can confirm or override classification. |
| Escalation thresholds set too low → coordinator overload | Medium | Default thresholds based on tenant's historical order values; adjustable per tenant. |
| Assisted onboarding is operationally expensive per client | High | Document onboarding playbook; automate where possible (sales backfill, user invite); measure onboarding time to identify bottlenecks. |
| Inter-branch transfer recommendations may be impractical (distance, logistics) | Medium | Include branch proximity metadata in v2; v1 relies on coordinator judgment. |
| Override misuse (persistent overrides that drift from reality) | Medium | Dashboard shows override age; admin can audit and reset. |
| Conflict of interest in multi-role assignments | Medium | Admin panel warns when a user has both system-config and operational roles (e.g., admin + warehouse manager). Audit logs record which role was used for each action. |
| Distribution center dependency risks | Medium | If a DC fails or is over-supplied, dependent branches can be affected. The system monitors DC health (stock level, lead time) and flags risks when DC stock is below critical thresholds for the demand of its dependents. v2: multi-level DC hierarchies (DC depending on another DC). |
| DMS data quality (missing sales records, incorrect stock, missing lead times) | High | Validation checks at ingestion; flag anomalies in dashboard; tenant data audit before go-live. |

### Open Questions
- What is the exact weighted velocity formula? (Deferred to design; options: linear decay, exponential smoothing, custom weights per month.)
- What are the default escalation thresholds? (System provides sensible defaults based on industry standards; first deployment may tune per their historical order values.)
- How is "surplus stock" defined for inter-branch transfer? → **ANSWERED**: Excess stock = `current_stock − Punto de Pedido`. A branch can transfer up to its excess stock without falling below its own Punto de Pedido. The system splits recommendations across multiple sources when needed.
- How should the system handle SKUs with irregular sales patterns (Ciclo Temporal / estacionalidad)? (Deferred to v2; v1 uses linear Planning Target calculation.)
- Should classification pass run at the same frequency as replenishment run, or separately (e.g., monthly)? (Deferred to design; likely separate to avoid reclassification on every run.)

## 10. Scope

### In Scope (v1)
- Scheduled replenishment engine (weekly/biweekly/monthly/quarterly, per-branch).
- DMS/ERP read integration (catalog, stock, sales movements, lead times if available).
- Classification engine (VC1–VC8 / New / Obsolete / Inactive derivation from sales data).
- Velocity calculation (weighted average, 12-month window).
- Planning Target & Punto de Pedido calculation.
- Cantidad de Pedido calculation (with Stock en Tránsito as separate concept).
- Recommendation generation with inter-branch transfer priority.
- Full approval workflow (pending → approved/rejected/handled/ordered).
- Escalation by configurable threshold.
- Demand override UX with mandatory type selection.
- Email + in-app notifications.
- Role-based dashboard (admin, gerente, branch manager, coordinator) with KPI tiles (Stock Total, Rotación, Cobertura, Stock Obsoleto, Stock Excesivo).
- Implementation-assisted onboarding with 12-month sales backfill.
- User invitation and role/branch assignment.
- Lifecycle stage visibility (New, Active, Pre-Obsolete, Obsolete, Non-Stocking).
- v1 is designed to be developed and maintained by a small team (potentially a single developer). Stack and architecture favor simplicity, good documentation, and low operational burden. See §12 (Approach) for stack criteria and the recommended MVP-first approach.
- `tenant_id` on all entities (single tenant active, multi-tenant ready).

### Out of Scope (v1 — deferred to v2+)
- Vehicle compatibility (model/year fitment).
- Core/return tracking (reverse logistics).
- Multi-tenant SaaS activation.
- Multi-region deployment.
- Self-service onboarding.
- Automated seasonal adjustment (Ciclo Temporal / estacionalidad patterns).
- Automated obsoletion detection (lifecycle stage transitions require gerente review).
- External supplier identification in recommendations.
- System-owned parts catalog.
- Advanced analytics (forecast accuracy, recommendation quality scoring).
- Branch proximity metadata for inter-branch transfer optimization.
- Automated derivation of lead times from historical PO data.

## 11. Capabilities

### New Capabilities
- `catalog-ingestion`: reads catalog (with internal SKU code, primary manufacturer code, alternative manufacturer codes — 1 Part ↔ M alternative manufacturer cross-reference), stock, sales movements, lead times, Stock en Tránsito, cross-reference relationships, and branch topology (branch type, parent branch) from the DMS/ERP (DMS is the source of truth for cross-reference data and branch topology). Supports distribution center topology: a branch can be configured as a DC that supplies other branches, with velocity aggregation and Punto de Pedido calculated accordingly. Multi-level DC hierarchies are v2.
- `velocity-calculation`: weighted average velocity, coverage days (365 / Stock Turn Ratio), projected demand.
- `classification-engine`: periodic classification pass deriving Volume Class (VC1–VC8) and Lifecycle Stage (New: N1/N2/N3, Obsolete: OBS-S/OBS-N/OBS-P/OBS-R, Inactive, Special: NS-C/NS-NS) codes from sales data.
- `planning-calculation`: Planning Target, Punto de Pedido, Cantidad de Pedido per SKU.
- `recommendation-engine`: generate replenishment recommendations with source resolution (inter-branch transfer → external supplier fallback).
- `approval-workflow`: state machine, escalation, threshold-based routing.
- `demand-override`: override UX with mandatory type selection and persistence rules.
- `notification-service`: email + in-app alerts for recommendations and escalations.
- `dashboard`: role-based views for stock health, recommendations, classification results, and KPI tiles (Stock Total, Rotación, Cobertura, Stock Obsoleto, Stock Excesivo).
- `onboarding`: guided branch activation with sales backfill.
- `user-management`: invitation, role assignment, branch access control with coordinator-level branch scoping (multiple coordinators supported, each with their own subset of branches) and gerente-level org-wide scope. Supports multiple roles per user, with effective permissions computed as the union of all assigned roles.
- `sector-configuration`: configuration of sector-specific terminology, classification codes, lifecycle stages, and special categories. The system ships with a default configuration (automotive aftermarket) and supports adding other sectors (pharmaceutical, hardware, manufacturing, etc.) by configuring terminology, classification, and lifecycle rules without modifying the core logic.
- `operations`: deployment, monitoring, logging, and basic system alerting (for the system itself, not for the inventory domain). v1 should be deployable on a single server or basic PaaS with minimal infrastructure. Multi-server, microservices, and complex orchestration (Kubernetes, message queues, etc.) are v2+ unless strictly necessary.

### Modified Capabilities
None (greenfield project).

## 12. Approach

The system operates as a **read-only advisory layer** on top of the organization's existing DMS/ERP. It never writes to the DMS. At each scheduled run, it pulls live stock, sales data, and lead times, computes derived metrics (classification, velocity, Planning Target, Punto de Pedido, Cantidad de Pedido), persists those metrics in its own database, and generates recommendations. Recommendations enter a workflow state machine; humans approve, reject, or mark as handled. The system tracks the state but does not execute fulfillment.

Key architectural decisions (deferred to design phase):
- Stack selection (language, framework, database).
- Scheduling mechanism (cron, job queue, event-driven).
- DMS integration pattern (direct DB read, API, ETL).
- Notification delivery (SMTP, transactional email service, websocket for in-app).
- Deployment model (single server, containerized, cloud-managed).
- Classification pass frequency and execution model (separate job vs. part of replenishment run).

### Stack considerations for solo development

v1 is designed to be developed and maintained by a small team (potentially a single developer). The stack and architecture should be chosen with the following criteria:

- **Single-developer manageable**: low complexity, good documentation, low operational burden. Avoid stacks that require specialized ops knowledge or large team coordination.
- **Quick local iteration**: minimal setup, fast feedback loop, easy debugging. The developer should be able to run the full system locally with one command.
- **Mature ecosystem for the domain**: strong libraries for database access, scheduled jobs, web dashboards, email notifications, and CSV/XLS parsing (for any future file upload).
- **Operational simplicity**: deployable on a single server or basic PaaS (Heroku, Render, Fly.io, DigitalOcean App Platform). Clear logging and basic monitoring (Sentry or similar) are enough for v1.
- **Common, well-documented technologies**: widely known languages and frameworks, both for solo productivity and for future hiring if the project scales.

Avoid for v1: Kubernetes, microservices, complex message queues, custom infrastructure orchestration. These add operational burden disproportionate to a solo-dev project.

### MVP-first approach (recommended)

Given the absence of a confirmed pilot client and the solo-development context, consider building a **minimal viable spike first** ("Phase 0") that validates the core flow with minimal investment:

- **Phase 0 (spike)**: a minimal script or small app that does the core flow end-to-end — read a small dataset → calculate Punto de Pedido → generate a recommendation → show it in a console or simple HTML page. Validates the methodology with the developer as the first "user". Time investment: days, not months.
- **Phase 1 (v1 MVP)**: the full proposal scope, but with simple tooling, basic UI, and the most important features first. Defer the rest (advanced analytics, complex multi-coordinator logic, etc.) to v1.5 or v2.
- **Phase 2+ (v1 full + v2)**: complete the full v1 scope, add the v2+ features, and harden for production.

This MVP-first approach reduces risk: if the methodology doesn't work as expected, the developer has invested days, not months. If it does work, the Phase 0 spike becomes the seed of Phase 1.

The system supports multiple sectors via the `sector-configuration` capability. v1 is configured for automotive aftermarket by default; other sectors (pharmaceutical, hardware, manufacturing, etc.) can be supported by configuring terminology, classification, and lifecycle rules without modifying the core logic. The formulas (Punto de Pedido, Cantidad de Pedido, Planning Target) are universal inventory management concepts; sector-specific aspects are the labels and rules, not the math.

## 13. Phasing

### v1 (This Proposal)
- Scheduled replenishment engine with classification, velocity, Planning Target, Punto de Pedido, Cantidad de Pedido.
- DMS/ERP read integration (catalog, stock, sales, lead times if available).
- Recommendation generation with inter-branch transfer priority.
- Full approval workflow with escalation.
- Demand override UX with mandatory type selection.
- Email + in-app notifications.
- Role-based dashboard with KPI tiles (Stock Total, Rotación, Cobertura, Stock Obsoleto, Stock Excesivo).
- Implementation-assisted onboarding.
- User management with invitation flow.
- Lifecycle stage visibility (New, Active, Pre-Obsolete, Obsolete, Non-Stocking).
- Single tenant, multi-branch, `tenant_id` present.

### v2+ (Deferred)
- Vehicle compatibility (model/year fitment lookup).
- Core/return tracking (reverse logistics for rebuildable parts).
- Multi-tenant SaaS with self-service activation.
- Multi-region deployment for geographic optimization.
- Automated seasonal adjustment (Ciclo Temporal / estacionalidad patterns).
- Automated obsoletion detection (lifecycle stage transitions fully automated, without human review).
- External supplier identification in recommendations (system suggests supplier based on historical purchases).
- System-owned catalog enrichment (brand, quality tier, supplier metadata).
- Branch proximity metadata for inter-branch transfer optimization.
- Advanced analytics: forecast accuracy, recommendation quality scoring.
- Automated derivation of lead times from historical PO data.

## 14. Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| DMS/ERP database | Read | System reads catalog, stock, sales movements, lead times, Stock en Tránsito. No writes. |
| Branch warehouse operations | Modified | Warehouse managers shift from manual spreadsheet to dashboard-based review of Punto de Pedido alerts and recommendations. |
| Coordinator workflow | Modified | Coordinators receive escalated recommendations and approve inter-branch transfers. |
| Admin operations | Modified | Admins configure system, manage users, monitor global KPIs; gerente (or delegated coordinator) reviews classification results. |
| IT infrastructure | New | System requires hosting, database, email service, DMS connectivity. |

## 15. Rollback Plan

The system is advisory-only and reads from the DMS without writing. Rollback is straightforward:
1. **Disable scheduled runs**: admin toggles off the schedule for a branch or globally. No recommendations are generated.
2. **Revert to manual process**: warehouse managers return to spreadsheet-based replenishment. No data loss; DMS is unchanged.
3. **System decommission**: if the system is abandoned, the DMS is unaffected. The system's own database (derived metrics, recommendations, approvals, classification) can be archived or deleted.
4. **Partial rollback**: if a specific feature (e.g., classification engine, escalation) causes issues, it can be disabled via configuration without affecting the rest of the system.

## 16. Dependencies

- **DMS/ERP access**: organization must provide read access to catalog, stock, sales movements, and lead times (or API). Schema documentation required.
- **Email service**: transactional email provider for notifications (SMTP credentials or API key).
- **Hosting infrastructure**: server, database, network connectivity to DMS.
- **First client commitment**: implementation-assisted onboarding requires an organization willing to pilot and provide feedback.
- **12-month sales history**: organization must have at least 12 months of sales data in DMS for meaningful velocity and classification calculation.
- **Lead time data**: organization must provide lead times per supplier (or per product) if available; otherwise, configurable defaults required.

## 17. Success Criteria

- [ ] System generates recommendations for all active SKUs at each scheduled run based on Punto de Pedido trigger.
- [ ] Classification engine derives VC1–VC8 / New / Obsolete / Inactive codes from sales data; gerente (or delegated coordinator) can review and confirm special flags (NS-C, NS-NS).
- [ ] Planning Target, Punto de Pedido, and Cantidad de Pedido calculated per material formulas.
- [ ] Branch managers can review and act on all pending recommendations within 15 minutes per run.
- [ ] Escalation workflow routes high-impact recommendations to coordinator automatically.
- [ ] Demand override UX prompts for type selection on every override; overrides persist according to selected type.
- [ ] SKUs classified as OBS-R (Obsolete, >24 months no sales) excluded from recommendations; remain visible in catalog.
- [ ] Cold-start SKUs require manual override before inclusion.
- [ ] Dashboard displays accurate KPIs (Stock Total, Rotación, Cobertura, Stock Obsoleto, Stock Excesivo) and classification results for each role.
- [ ] Email notifications delivered within 5 minutes of recommendation generation or escalation.
- [ ] First client onboarded with 12-month sales backfill and operational within 4 weeks.
