# Tasks: Automotive Stock Advisor

## Overview

**Total tasks**: 87 tasks across 20 work units  
**Phase 0 (spike)**: ✅ DONE — formula validation (51 tests passing)  
**Phase 1 (MVP)**: 10 weekly increments, builds Django app end-to-end  
**Phase 1.5 (v1 complete)**: full v1 scope with hardening  
**Phase 2+ (v2)**: automated obsoletion, seasonal adjustment, multi-tenant SaaS  

**Chained PR strategy**: 20 work units, each ≤400 lines, ordered by dependencies. Each WU is a reviewable, mergeable unit that produces working functionality.

**Spec coverage**: All 13 specs covered (catalog-ingestion, velocity-calculation, classification-engine, planning-calculation, recommendation-engine, approval-workflow, demand-override, notification-service, dashboard, onboarding, user-management, sector-configuration, operations).

**Business rules coverage**: All 14 business rules from proposal §7 are implementable via these tasks.

---

## Work Units (Chained PRs)

### WU-01: Django Foundation & Core Models
**Tasks**: T-001, T-002, T-003  
**Estimated lines**: ~350  
**Dependencies**: None (Phase 0 spike complete)  
**Acceptance criteria**: 
- Django project scaffolds successfully
- Tenant, User, Role, UserRole models exist with migrations
- Admin panel accessible, can create tenants and users
- Login/logout works via Django sessions

### WU-02: User Management & Invitation Flow
**Tasks**: T-004, T-005, T-006, T-007  
**Estimated lines**: ~380  
**Dependencies**: WU-01  
**Acceptance criteria**:
- Email-based invitation flow works (send invite → accept → activate)
- Four roles exist: administrator, gerente, warehouse_coordinator, warehouse_manager
- Multi-role assignment works (union of permissions)
- Conflict of interest warnings display for risky role combinations
- Audit log records role used for each action

### WU-03: Branch & Catalog Models
**Tasks**: T-008, T-009, T-010  
**Estimated lines**: ~350  
**Dependencies**: WU-01  
**Acceptance criteria**:
- Branch model supports branch_type (sucursal/centro_distribucion) and parent_branch_id
- Part model stores internal_sku_code, primary_mfr_code, alt_mfr_codes (JSONB)
- CrossReference model links related parts
- Admin can create branches and upload parts via CSV

### WU-04: DMS Adapter Interface & Mock Adapter
**Tasks**: T-011, T-012, T-013  
**Estimated lines**: ~300  
**Dependencies**: WU-03  
**Acceptance criteria**:
- BaseDMSAdapter abstract interface defined (read_parts, read_stock, read_sales, read_cross_references, read_branches)
- MockDMSAdapter returns fixture data for testing
- Retry mechanism (3 attempts, exponential backoff 1s/2s/4s, 30s timeout) implemented
- Adapter swap works without modifying core logic

### WU-05: Inventory Models & Data Ingestion
**Tasks**: T-014, T-015, T-016  
**Estimated lines**: ~350  
**Dependencies**: WU-03, WU-04  
**Acceptance criteria**:
- StockLevel model stores stock_disponible, stock_en_transito, last_synced_at per branch/part
- StockMovement model records sales/purchase/transfer movements with date
- Ingestion service reads from DMS adapter and persists to DB
- 12+ months of sales history can be imported
- Missing SKU in stock table treated as zero stock (cold-start flag)

### WU-06: Velocity Calculation Engine
**Tasks**: T-017, T-018, T-019  
**Estimated lines**: ~250  
**Dependencies**: WU-05  
**Acceptance criteria**:
- Weighted average velocity calculated (recent months weighted heavier)
- Coverage days = 365 / Stock Turn Ratio (avoids division by zero)
- Projected demand = velocity × (period_days / 30)
- DC velocity aggregation: own sales + sum of dependent branch velocities
- Empty history returns velocity = 0.0 without error

### WU-07: Classification Engine
**Tasks**: T-020, T-021, T-022, T-023  
**Estimated lines**: ~350  
**Dependencies**: WU-05, WU-06  
**Acceptance criteria**:
- Volume Class derived from annual sales (VC1 >250, VC2 121-250, ..., VC8 1-3)
- Lifecycle Stage codes assigned: N1/N2/N3 (New), OBS-S/OBS-N/OBS-P/OBS-R (Obsolete), Inactive, NS-C/NS-NS (Special)
- Classification pass runs monthly (separate from replenishment)
- Cross-reference groups use most conservative lifecycle stage
- OBS-R and NS-NS SKUs excluded from recommendations

### WU-08: Planning Calculation Engine
**Tasks**: T-024, T-025, T-026  
**Estimated lines**: ~250  
**Dependencies**: WU-06  
**Acceptance criteria**:
- Planning Target = (velocity / 30) × (Periodo de Stock + Stock de Seguridad + Tiempo de Pedido)
- Punto de Pedido = Planning Target + Tiempo de Pedido (raw numeric addition)
- Cantidad de Pedido = max(0, Planning Target − Stock Disponible − Stock en Tránsito)
- Per-branch and per-supplier lead time supported (most specific wins)
- DC Planning Target uses aggregated velocity

### WU-09: Recommendation Engine — Core Logic
**Tasks**: T-027, T-028, T-029  
**Estimated lines**: ~380  
**Dependencies**: WU-07, WU-08  
**Acceptance criteria**:
- Recommendation triggered when Stock Disponible + Stock en Tránsito ≤ Punto de Pedido
- Recommendation includes: SKU, classification code, quantity, source type, source branch, projected coverage
- Cold-start SKUs (zero sales history) flagged for manual override, not auto-recommended
- OBS-R and NS-NS SKUs excluded from automatic recommendations
- Idempotency: same (branch_id, part_id, run_date) does not create duplicate recommendations

### WU-10: Recommendation Engine — Source Resolution
**Tasks**: T-030, T-031, T-032, T-033  
**Estimated lines**: ~380  
**Dependencies**: WU-09  
**Acceptance criteria**:
- Inter-branch transfer checked before external supplier (excess stock = max(0, current_stock − Punto de Pedido))
- Source branch never falls below its own Punto de Pedido after transfer
- Multi-source split: recommendation split across multiple branches when needed
- Partial fulfillment alert sent to branch manager, coordinator(s), and gerente
- DC topology: parent DC checked first, then other branches if DC insufficient
- DC self-replenishment: projected stock after transfers evaluated, external supplier recommended if below Punto de Pedido

### WU-11: Approval Workflow — State Machine
**Tasks**: T-034, T-035, T-036  
**Estimated lines**: ~350  
**Dependencies**: WU-09  
**Acceptance criteria**:
- State machine: pending → approved | rejected | handled | ordered
- Branch manager is default approver for own branch
- Every state transition recorded in audit log (user_id, role_used_id, action, entity_type, entity_id, timestamp)
- Bulk actions (approve/reject/handle multiple) process only pending recommendations
- Rejected recommendations cannot be re-opened within same run

### WU-12: Approval Workflow — Escalation & Cross-Coordinator
**Tasks**: T-037, T-038, T-039  
**Estimated lines**: ~300  
**Dependencies**: WU-11  
**Acceptance criteria**:
- Threshold-based escalation: recommendations crossing value/volume/impact thresholds auto-escalate to coordinator
- Coordinator can escalate to gerente for cross-coordinator cases
- Cross-coordinator transfers require gerente approval (coordinators notified only)
- Single-coordinator transfers follow standard branch manager → coordinator flow
- Escalation logged with reason and from/to roles

### WU-13: Demand Override
**Tasks**: T-040, T-041, T-042  
**Estimated lines**: ~300  
**Dependencies**: WU-08, WU-11  
**Acceptance criteria**:
- Override type selection prompt mandatory (Persistent / Per-run / With expiry) with explanations
- Persistent override survives multiple runs until manually changed
- Per-run override discarded after current run completes
- Override with expiry automatically reverts after specified date
- Only branch manager can apply overrides for their branch
- Override log visible in dashboard with age warnings at 90 days
- Override affects Planning Target, Punto de Pedido, Cantidad de Pedido calculations

### WU-14: Notification Service
**Tasks**: T-043, T-044, T-045, T-046  
**Estimated lines**: ~350  
**Dependencies**: WU-10, WU-12, WU-13  
**Acceptance criteria**:
- Email digest sent per replenishment run (one email, not one per recommendation)
- In-app notifications appear within 5 minutes of recommendation generation
- Escalation notifications include reason and recommendation details
- Partial fulfillment alerts reach branch manager, coordinator(s), and gerente
- Cold-start flag notifications prompt branch manager to apply demand override
- Classification review notifications sent to gerente (or delegated coordinator)
- DC stock critical alerts sent to DC manager, dependent coordinators, and gerente
- Admin receives no direct notifications (views consolidated state in dashboard)
- Email delivery failures logged and retried

### WU-15: Dashboard — Branch Manager View
**Tasks**: T-047, T-048, T-049, T-050  
**Estimated lines**: ~380  
**Dependencies**: WU-11, WU-13, WU-14  
**Acceptance criteria**:
- Branch manager sees only own branch data
- KPI tiles display: Stock Total, Rotación, Cobertura (días), Stock Obsoleto, Stock Excesivo
- Pending recommendations count prominently displayed
- Approval history visible (approved/rejected/handled/ordered)
- Override log shows SKU, value, type, date, status, age warnings
- Classification results table filterable/sortable by Volume Class and Lifecycle Stage
- Special flags (NS-C) visually highlighted
- CSV export includes all visible columns
- KPI tiles auto-refresh every 60 seconds via HTMX

### WU-16: Dashboard — Coordinator, Gerente, Admin Views
**Tasks**: T-051, T-052, T-053, T-054  
**Estimated lines**: ~380  
**Dependencies**: WU-15  
**Acceptance criteria**:
- Coordinator sees aggregated data for branches in their scope (read-only)
- Coordinator can drill down into each branch individually
- Escalated items widget shows branch, SKU, quantity, escalation reason
- Inter-branch transfer status widget shows source/destination branches, SKU, quantity, state
- Gerente sees org-wide KPIs (all branches, all coordinators)
- Cross-coordinator transfer queue shows source/destination coordinators, branches, quantities
- Classification review queue shows SKU, proposed code, confirm/override actions
- Admin sees all branches plus user management and system configuration panels
- User with multiple roles sees union of all role-specific views

### WU-17: Sector Configuration
**Tasks**: T-055, T-056, T-057  
**Estimated lines**: ~250  
**Dependencies**: WU-07  
**Acceptance criteria**:
- SectorConfiguration model stores sector_key + config_json (terminology, classification thresholds, lifecycle rules)
- Default sector is "automotive_aftermarket" for new tenants
- Sector-specific terminology used in UI, notifications, exports
- Classification engine uses sector-specific thresholds (VC1 >250 for automotive, different for other sectors)
- Core formulas identical across all sectors (only labels/rules differ)
- Admin can create, view, modify sector configurations
- Custom lifecycle stages can be added with sector-specific behavioral rules

### WU-18: Onboarding Flow
**Tasks**: T-058, T-059, T-060, T-061  
**Estimated lines**: ~300  
**Dependencies**: WU-04, WU-05, WU-15  
**Acceptance criteria**:
- DMS connection setup validates connection and required tables/views
- Sales history backfill imports 12+ months (warns if insufficient, does not block)
- Branch manager assignment required before first replenishment run
- First test run validates end-to-end flow (catalog read → velocity → classification → Planning Target → recommendations)
- Onboarding checklist tracks progress (DMS connection → sales backfill → manager assignment → test run → go-live)
- User provisioning follows hierarchy (admin invites gerente → gerente invites coordinators → coordinator invites branch managers)
- Target onboarding time: ≤28 days from kickoff to first live run

### WU-19: Scheduling & Background Jobs
**Tasks**: T-062, T-063, T-064, T-065  
**Estimated lines**: ~300  
**Dependencies**: WU-10, WU-14  
**Acceptance criteria**:
- Django-Q2 scheduler configured (DB-backed for dev, Redis for prod)
- Replenishment run scheduled per branch (weekly by default, configurable)
- Classification pass scheduled monthly (separate from replenishment)
- Notification dispatch runs every 15 minutes (processes pending queue)
- Idempotency: replenishment_run dedupes by (branch_id, run_date), classification_pass by (tenant_id, month_key)
- Retry mechanism: 3 retries with 5min delay for failed jobs
- Dead tasks visible in Django-Q2 admin

### WU-20: Operations — Deployment, Logging, Health
**Tasks**: T-066, T-067, T-068, T-069, T-070  
**Estimated lines**: ~350  
**Dependencies**: All previous WUs  
**Acceptance criteria**:
- Dockerfile (multi-stage: python:slim, gunicorn + whitenoise) and docker-compose.yml (app + db + redis + worker) included
- Render deployment: auto-deploys on push to main, PostgreSQL managed database connected
- Structured JSON logs to stdout (timestamp, level, event, request_id, user_id, branch_id)
- Sentry integration active when SENTRY_DSN configured (optional)
- Health check endpoint returns status of web, db, queue components (HTTP 200/503)
- Database backup RPO ≤1 hour, RTO <4 hours (Render managed or pg_dump cron + S3)
- Alerts fire on 3 consecutive job failures, 500-rate spike, DB connection loss
- CI/CD pipeline: ruff lint → pytest → Docker build → push to registry → Render auto-deploy
- Local development: `docker-compose up` starts all services, `make reset-db` and `make seed` work

---

## Phase 1 MVP Roadmap (10 Weeks)

### Week 1: Foundation & Auth (WU-01, WU-02)
**Tasks**: T-001 through T-007  
**Deliverable**: Django scaffold, core models, user management, invitation flow, admin panel  
**Capabilities**: user-management (partial)  
**Demo**: Login/logout works, admin can invite users, roles assigned

### Week 2: Branches & Catalog (WU-03, WU-04)
**Tasks**: T-008 through T-013  
**Deliverable**: Branch model, Part model, DMS adapter interface, mock adapter  
**Capabilities**: catalog-ingestion (partial)  
**Demo**: Admin can create branches, upload parts CSV, mock adapter returns fixture data

### Week 3: Inventory & Velocity (WU-05, WU-06)
**Tasks**: T-014 through T-019  
**Deliverable**: StockLevel, StockMovement, velocity calculation, DC aggregation  
**Capabilities**: catalog-ingestion (complete), velocity-calculation (complete)  
**Demo**: 12 months of sales imported, velocity calculated per SKU, DC velocity aggregated

### Week 4: Classification (WU-07, WU-17)
**Tasks**: T-020 through T-023, T-055 through T-057  
**Deliverable**: Classification engine, sector configuration  
**Capabilities**: classification-engine (complete), sector-configuration (complete)  
**Demo**: Monthly classification pass runs, VC1-VC8 and Lifecycle Stage codes assigned, sector-specific thresholds work

### Week 5: Planning & Recommendations (WU-08, WU-09)
**Tasks**: T-024 through T-029  
**Deliverable**: Planning Target, Punto de Pedido, Cantidad de Pedido, recommendation generation  
**Capabilities**: planning-calculation (complete), recommendation-engine (partial)  
**Demo**: Manual trigger generates recommendations for SKUs below Punto de Pedido

### Week 6: Source Resolution (WU-10)
**Tasks**: T-030 through T-033  
**Deliverable**: Inter-branch transfer logic, excess stock calculation, multi-source split, DC topology  
**Capabilities**: recommendation-engine (complete)  
**Demo**: Recommendations resolved via inter-branch transfer first, external supplier fallback, partial fulfillment alerts

### Week 7: Approval Workflow (WU-11, WU-12)
**Tasks**: T-034 through T-039  
**Deliverable**: State machine, escalation, cross-coordinator transfers, audit logging  
**Capabilities**: approval-workflow (complete)  
**Demo**: Branch manager approves/rejects recommendations, threshold-based escalation works, cross-coordinator transfers require gerente approval

### Week 8: Demand Override & Notifications (WU-13, WU-14)
**Tasks**: T-040 through T-046  
**Deliverable**: Override UX with type selection, email + in-app notifications  
**Capabilities**: demand-override (complete), notification-service (complete)  
**Demo**: Branch manager applies override with type selection, digest email sent after run, in-app notifications appear

### Week 9: Dashboard (WU-15, WU-16)
**Tasks**: T-047 through T-054  
**Deliverable**: Role-based dashboard views, KPI tiles, CSV export, HTMX refresh  
**Capabilities**: dashboard (complete)  
**Demo**: Branch manager sees own branch KPIs, coordinator sees scoped branches, gerente sees org-wide KPIs, admin sees all

### Week 10: Onboarding, Scheduling, Operations (WU-18, WU-19, WU-20)
**Tasks**: T-058 through T-070  
**Deliverable**: Onboarding flow, scheduled jobs, deployment, logging, health checks, CI/CD  
**Capabilities**: onboarding (complete), operations (complete)  
**Demo**: First test run validates end-to-end flow, scheduled jobs run, Docker Compose starts all services, Render deployment works

---

## Detailed Tasks

### WU-01: Django Foundation & Core Models

**[x] T-001**: Django project scaffold  
**Capability**: operations  
**Work unit**: WU-01  
**Description**: Initialize Django 5.1+ project with `config/` (settings, urls, wsgi/asgi), `apps/` directory structure, and basic settings (DATABASE_URL, SECRET_KEY, DEBUG). Configure PostgreSQL 16+ connection. Add pytest, pytest-django, factory_boy to dev dependencies.  
**Files affected**: `manage.py`, `config/settings/`, `config/urls.py`, `config/wsgi.py`, `requirements.txt`, `pytest.ini`  
**Complexity**: S (0.5 day)  
**Depends on**: None  
**Acceptance criteria**: `python manage.py runserver` starts without errors, `pytest` runs

**[x] T-002**: Core models — Tenant, User, Role, UserRole  
**Capability**: user-management  
**Work unit**: WU-01  
**Description**: Create `apps/core/models.py` with Tenant (id, name, config_json), User (id, email, password_hash, is_active), Role (id, name), UserRole (id, user_id, role_id, branch_id, scope_json). Add migrations. Register in admin panel.  
**Files affected**: `apps/core/models.py`, `apps/core/migrations/`, `apps/core/admin.py`, `apps/accounts/models.py`, `apps/accounts/admin.py`  
**Complexity**: M (1 day)  
**Depends on**: T-001  
**Acceptance criteria**: Migrations apply successfully, admin panel shows Tenant/User/Role/UserRole, can create instances

**[x] T-003**: Authentication flow — login/logout  
**Capability**: user-management  
**Work unit**: WU-01  
**Description**: Configure Django sessions (2h idle, 24h absolute expiry). Add django-allauth for email verification and password reset. Create login/logout views and templates. Set SESSION_COOKIE_AGE and SESSION_EXPIRE_AT_BROWSER_CLOSE.  
**Files affected**: `config/settings/`, `apps/accounts/views.py`, `apps/accounts/urls.py`, `templates/accounts/login.html`, `templates/accounts/logout.html`  
**Complexity**: M (1 day)  
**Depends on**: T-002  
**Acceptance criteria**: User can login with email/password, session expires after 2h idle, logout clears session

### WU-02: User Management & Invitation Flow

**[x] T-004**: User invitation model and email template  
**Capability**: user-management  
**Work unit**: WU-02  
**Description**: Create Invitation model (id, email, role_id, branch_id, scope_json, token, expires_at, accepted_at). Create email template for invitation with activation link. Token expires after 7 days (configurable).  
**Files affected**: `apps/accounts/models.py`, `apps/accounts/migrations/`, `templates/emails/invitation.html`  
**Complexity**: S (0.5 day)  
**Depends on**: T-003  
**Acceptance criteria**: Invitation model exists, email template renders with activation link

**[x] T-005**: Invitation service — send and accept  
**Capability**: user-management  
**Work unit**: WU-02  
**Description**: Create InvitationService.send_invitation(email, role_id, branch_id, scope_json) that generates token, creates Invitation, sends email. Create InvitationService.accept_invitation(token, password) that validates token, creates User, marks Invitation as accepted.  
**Files affected**: `apps/accounts/services.py`, `apps/accounts/views.py`, `apps/accounts/urls.py`  
**Complexity**: M (1.5 days)  
**Depends on**: T-004  
**Acceptance criteria**: Admin can send invitation, recipient receives email, clicks link, creates password, account activated

**[x] T-006**: Multi-role assignment and permission union  
**Capability**: user-management  
**Work unit**: WU-02  
**Description**: Implement User.get_all_permissions() that unions all assigned roles' permissions. Add conflict of interest warnings in admin panel for risky combinations (admin + warehouse_manager). Audit log records role_used_id for each action.  
**Files affected**: `apps/accounts/models.py`, `apps/accounts/admin.py`, `apps/core/models.py` (AuditLog)  
**Complexity**: M (1.5 days)  
**Depends on**: T-005  
**Acceptance criteria**: User with multiple roles has union of permissions, admin panel warns about conflicts, audit log records role used

**[x] T-007**: Hierarchical access control  
**Capability**: user-management  
**Work unit**: WU-02  
**Description**: Implement permission checks: admin (all), gerente (org-wide), coordinator (scope only), branch manager (own branch only). Create decorators or mixins for view-level access control. Enforce user management hierarchy (admin manages all, gerente manages gerente and below, coordinator manages branch managers in scope).  
**Files affected**: `apps/accounts/permissions.py`, `apps/accounts/mixins.py`, `apps/accounts/views.py`  
**Complexity**: M (1 day)  
**Depends on**: T-006  
**Acceptance criteria**: Branch manager can access only own branch, coordinator can access only branches in scope, admin can access all

### WU-03: Branch & Catalog Models

**[x] T-008**: Branch model with DC topology  
**Capability**: catalog-ingestion  
**Work unit**: WU-03  
**Description**: Create Branch model (id, tenant_id, name, branch_type [sucursal/centro_distribucion], parent_branch_id, config_json). Add self-referential FK for DC topology. Register in admin.  
**Files affected**: `apps/branches/models.py`, `apps/branches/migrations/`, `apps/branches/admin.py`  
**Complexity**: S (0.5 day)  
**Depends on**: T-002  
**Acceptance criteria**: Branch model supports DC topology, admin can create branches with parent_branch_id

**[x] T-009**: Part and CrossReference models  
**Capability**: catalog-ingestion  
**Work unit**: WU-03  
**Description**: Create Part model (id, tenant_id, internal_sku_code, primary_mfr_code, alt_mfr_codes [JSONB], description, lead_time_days). Create CrossReference model (id, part_id, related_part_id, relation_type [substitute/alternative/successor], source_dms). Add unique constraint on (tenant_id, internal_sku_code).  
**Files affected**: `apps/catalog/models.py`, `apps/catalog/migrations/`, `apps/catalog/admin.py`  
**Complexity**: M (1 day)  
**Depends on**: T-008  
**Acceptance criteria**: Part model stores alt_mfr_codes as JSONB, CrossReference links related parts, admin can view/edit

**[x] T-010**: CSV upload for parts catalog  
**Capability**: catalog-ingestion  
**Work unit**: WU-03  
**Description**: Create admin action to upload parts catalog via CSV. Parse CSV, validate required fields (internal_sku_code, primary_mfr_code), create Part instances. Handle duplicates (update existing by internal_sku_code).  
**Files affected**: `apps/catalog/admin.py`, `apps/catalog/services.py`  
**Complexity**: M (1 day)  
**Depends on**: T-009  
**Acceptance criteria**: Admin can upload CSV, parts created/updated, duplicates handled

### WU-04: DMS Adapter Interface & Mock Adapter

**[x] T-011**: BaseDMSAdapter abstract interface  
**Capability**: catalog-ingestion  
**Work unit**: WU-04  
**Description**: Create `adapters/base.py` with BaseDMSAdapter ABC defining: read_parts(tenant_id), read_stock(branch_id), read_sales(branch_id, since_date), read_cross_references(tenant_id), read_branches(tenant_id). Each method returns Iterator of data classes (PartData, StockData, SalesData, CrossRefData, BranchData).  
**Files affected**: `adapters/base.py`, `adapters/data_classes.py`  
**Complexity**: S (0.5 day)  
**Depends on**: T-009  
**Acceptance criteria**: Abstract interface defined, concrete adapters must implement all methods

**[x] T-012**: MockDMSAdapter with fixture data  
**Capability**: catalog-ingestion  
**Work unit**: WU-04  
**Description**: Create MockDMSAdapter that returns hardcoded fixture data (50 SKUs, 4 branches, 12 months of sales). Use for testing and local development. Fixture data should produce realistic recommendations.  
**Files affected**: `adapters/mock.py`, `adapters/fixtures/sample_data.py`  
**Complexity**: M (1 day)  
**Depends on**: T-011  
**Acceptance criteria**: MockDMSAdapter returns fixture data, can be swapped in via settings

**[x] T-013**: Retry mechanism with exponential backoff  
**Capability**: catalog-ingestion  
**Work unit**: WU-04  
**Description**: Add retry decorator to BaseDMSAdapter methods: 3 attempts, exponential backoff (1s, 2s, 4s), 30s timeout per call. Use `tenacity` library. Log each retry attempt. Raise exception after all retries fail.  
**Files affected**: `adapters/base.py`, `requirements.txt`  
**Complexity**: S (0.5 day)  
**Depends on**: T-011  
**Acceptance criteria**: Failed DMS read retries 3 times with backoff, logs each attempt, raises after exhaustion

### WU-05: Inventory Models & Data Ingestion

**[x] T-014**: StockLevel and StockMovement models  
**Capability**: catalog-ingestion  
**Work unit**: WU-05  
**Description**: Create StockLevel model (id, branch_id, part_id, stock_disponible, stock_en_transito, last_synced_at). Create StockMovement model (id, branch_id, part_id, movement_type [sale/purchase/transfer], quantity, date). Add unique constraint on (branch_id, part_id) for StockLevel.  
**Files affected**: `apps/inventory/models.py`, `apps/inventory/migrations/`, `apps/inventory/admin.py`  
**Complexity**: S (0.5 day)  
**Depends on**: T-009  
**Acceptance criteria**: StockLevel stores stock_disponible and stock_en_transito separately, StockMovement records movement type and date

**[x] T-015**: Inventory ingestion service  
**Capability**: catalog-ingestion  
**Work unit**: WU-05  
**Description**: Create InventoryIngestionService that reads from DMS adapter and persists to DB. Methods: ingest_stock(branch_id), ingest_sales(branch_id, since_date), ingest_cross_references(tenant_id). Handle missing SKU in stock table (treat as zero stock, flag as cold-start).  
**Files affected**: `apps/inventory/services.py`  
**Complexity**: M (1.5 days)  
**Depends on**: T-014, T-012  
**Acceptance criteria**: Service reads from mock adapter, persists to DB, missing SKU treated as zero stock

**[x] T-016**: Sales history backfill (12+ months)  
**Capability**: catalog-ingestion  
**Work unit**: WU-05  
**Description**: Create method to import 12+ months of historical sales data from DMS. Validate data completeness (no gaps in monthly records). Warn if insufficient history (<12 months) but do not block. Flag all SKUs as cold-start if zero history.  
**Files affected**: `apps/inventory/services.py`  
**Complexity**: M (1 day)  
**Depends on**: T-015  
**Acceptance criteria**: 18 months of sales imported successfully, warning if <12 months, cold-start flag if zero

### WU-06: Velocity Calculation Engine

**[x] T-017**: Weighted average velocity calculation
**Capability**: velocity-calculation
**Work unit**: WU-06
**Description**: Create VelocityService.calculate_velocity(branch_id, part_id) that computes weighted average of monthly sales (recent months weighted heavier). Use linear ramp 0.5→1.5 (from spike). Handle empty history (return 0.0, flag as cold-start). Handle shorter history (<12 months).
**Files affected**: `apps/catalog/services.py`
**Complexity**: M (1 day)
**Depends on**: T-015
**Acceptance criteria**: Flat sales at X units/month returns X, rising trend produces weighted avg > simple mean, empty history returns 0.0

**[x] T-018**: Coverage days and projected demand
**Capability**: velocity-calculation
**Work unit**: WU-06
**Description**: Create VelocityService.calculate_coverage_days(branch_id, part_id) = 365 / Stock Turn Ratio (Ingresos Año-12 / Stock Promedio-12). Avoid division by zero (return 0.0). Create VelocityService.calculate_projected_demand(velocity, period_days) = velocity × (period_days / 30).
**Files affected**: `apps/catalog/services.py`
**Complexity**: S (0.5 day)
**Depends on**: T-017
**Acceptance criteria**: Coverage days avoids division by zero, projected demand matches formula

**[x] T-019**: DC velocity aggregation
**Capability**: velocity-calculation
**Work unit**: WU-06
**Description**: Create VelocityService.calculate_dc_velocity(dc_branch_id) = DC's own velocity + sum of dependent branch velocities. Query all branches with parent_branch_id = dc_branch_id. Handle DC with no dependents (return own velocity only).
**Files affected**: `apps/catalog/services.py`
**Complexity**: S (0.5 day)
**Depends on**: T-017, T-008
**Acceptance criteria**: DC velocity = own + sum of dependents, DC with no dependents returns own velocity

### WU-07: Classification Engine

**[x] T-020**: Volume Class derivation  
**Capability**: classification-engine  
**Work unit**: WU-07  
**Description**: Create ClassificationService.classify_volume_class(part_id, tenant_id) based on annual sales: VC1 >250, VC2 121-250, VC3 61-120, VC4 31-60, VC5 15-30, VC6 7-14, VC7 4-6, VC8 1-3. Zero sales returns no Volume Class (cold-start). Create ClassificationResult model (id, part_id, volume_class, lifecycle_stage, classified_at).  
**Files affected**: `apps/catalog/classification.py`, `apps/catalog/models.py`, `apps/catalog/migrations/`  
**Complexity**: M (1 day)  
**Depends on**: T-015  
**Acceptance criteria**: 300 annual sales → VC1, 121 → VC2, 0 → no VC, boundary values correct

**[x] T-021**: Lifecycle Stage — New and Obsolete  
**Capability**: classification-engine  
**Work unit**: WU-07  
**Description**: Create ClassificationService.classify_lifecycle_stage(part_id, tenant_id). New (0-6 months): N1 >15 sales in first 6 months, N2 4-15, N3 0-3. Obsolete: OBS-S (successor exists), OBS-N (>6 months in stock, never sold), OBS-P (>12 months no sales), OBS-R (>24 months no sales). Inactive: >12 months no sales AND no stock.  
**Files affected**: `apps/catalog/classification.py`  
**Complexity**: M (1.5 days)  
**Depends on**: T-020  
**Acceptance criteria**: New SKU with 18 sales in 6 months → N1, SKU with 14 months no sales → OBS-P, SKU with 26 months no sales → OBS-R

**[x] T-022**: Special lifecycle codes (NS-C, NS-NS)  
**Capability**: classification-engine  
**Work unit**: WU-07  
**Description**: Add support for NS-C (campaign/recall) and NS-NS (non-stock/individual order). These require gerente confirmation before taking effect. Add confirmation workflow (pending → confirmed). NS-NS SKUs excluded from automatic replenishment.  
**Files affected**: `apps/catalog/classification.py`, `apps/catalog/models.py`  
**Complexity**: S (0.5 day)  
**Depends on**: T-021  
**Acceptance criteria**: NS-C and NS-NS codes assigned, require gerente confirmation, NS-NS excluded from recommendations

**[x] T-023**: Cross-reference group classification  
**Capability**: classification-engine  
**Work unit**: WU-07  
**Description**: Create ClassificationService.classify_cross_reference_group(part_id) that applies the most conservative lifecycle stage across equivalent parts. Query all CrossReference records for the part, get lifecycle stages, pick most conservative (OBS-R > OBS-P > OBS-N > Active > New).  
**Files affected**: `apps/catalog/classification.py`  
**Complexity**: S (0.5 day)  
**Depends on**: T-021, T-009  
**Acceptance criteria**: Group with Active + OBS-P → OBS-P, most conservative wins

### WU-08: Planning Calculation Engine

**T-024**: Planning Target calculation  
**Capability**: planning-calculation  
**Work unit**: WU-08  
**Description**: Create PlanningService.calculate_planning_target(branch_id, part_id) = (velocity / 30) × (Periodo de Stock + Stock de Seguridad + Tiempo de Pedido). Clamp negative velocity to 0. Use branch-level defaults for Periodo de Stock, Stock de Seguridad, Tiempo de Pedido (configurable).  
**Files affected**: `apps/replenishment/services.py`  
**Complexity**: S (0.5 day)  
**Depends on**: T-017  
**Acceptance criteria**: velocity=20, period=30, security=15, lead=10 → PT=36.67, negative velocity clamped to 0

**T-025**: Punto de Pedido and Cantidad de Pedido  
**Capability**: planning-calculation  
**Work unit**: WU-08  
**Description**: Create PlanningService.calculate_punto_de_pedido(planning_target, lead_time_days) = planning_target + lead_time_days (raw numeric addition). Create PlanningService.calculate_cantidad_de_pedido(planning_target, stock_disponible, stock_en_transito) = max(0, planning_target - stock_disponible - stock_en_transito).  
**Files affected**: `apps/replenishment/services.py`  
**Complexity**: S (0.5 day)  
**Depends on**: T-024  
**Acceptance criteria**: PT=36.67, lead=10 → PP=46.67, PT=36.67, stock=15, transit=10 → CP=11.67, never negative

**T-026**: Per-branch and per-supplier lead time  
**Capability**: planning-calculation  
**Work unit**: WU-08  
**Description**: Add lead_time_days field to Part model (per-supplier) and Branch model (per-branch default). Create PlanningService.get_lead_time(branch_id, part_id) that returns per-supplier if available, else per-branch default. Log warning if using default.  
**Files affected**: `apps/catalog/models.py`, `apps/branches/models.py`, `apps/replenishment/services.py`  
**Complexity**: S (0.5 day)  
**Depends on**: T-024  
**Acceptance criteria**: Per-supplier lead time used if available, else per-branch default, warning logged

### WU-09: Recommendation Engine — Core Logic

**[x] T-027**: Recommendation model and trigger logic  
**Capability**: recommendation-engine  
**Work unit**: WU-09  
**Description**: Create Recommendation model (id, branch_id, part_id, quantity, source_type [transfer/supplier], source_branch_id, state [pending/approved/rejected/handled/ordered], classification_code, created_at, run_date). Create RecommendationService.generate_recommendations(branch_id, run_date) that triggers when Stock Disponible + Stock en Tránsito ≤ Punto de Pedido.  
**Files affected**: `apps/recommendations/models.py`, `apps/recommendations/migrations/`, `apps/recommendations/services.py`  
**Complexity**: M (1 day)  
**Depends on**: T-025, T-020  
**Acceptance criteria**: Recommendation created when stock ≤ PP, includes SKU, classification, quantity, source type

**[x] T-028**: Cold-start and lifecycle exclusion  
**Capability**: recommendation-engine  
**Work unit**: WU-09  
**Description**: Add logic to skip SKUs with zero sales history (cold-start) — flag as "requires manual override" instead of generating recommendation. Exclude SKUs classified as OBS-R or NS-NS from automatic recommendations. Log skipped SKUs.  
**Files affected**: `apps/recommendations/services.py`  
**Complexity**: S (0.5 day)  
**Depends on**: T-027, T-021  
**Acceptance criteria**: Cold-start SKU flagged, OBS-R and NS-NS excluded, logged

**T-029**: Idempotency for recommendation generation  
**Capability**: recommendation-engine  
**Work unit**: WU-09  
**Description**: Add idempotency check: before creating Recommendation, check if one exists with same (branch_id, part_id, run_date). If exists, skip. This prevents duplicate recommendations on retry.  
**Files affected**: `apps/recommendations/services.py`  
**Complexity**: S (0.5 day)  
**Depends on**: T-027  
**Acceptance criteria**: Same (branch_id, part_id, run_date) does not create duplicate

### WU-10: Recommendation Engine — Source Resolution

**T-030**: Excess stock calculation  
**Capability**: recommendation-engine  
**Work unit**: WU-10  
**Description**: Create RecommendationService.calculate_excess_stock(branch_id, part_id) = max(0, current_stock - Punto de Pedido). This is the amount a branch can transfer without falling below its own PP. Query StockLevel for current_stock.  
**Files affected**: `apps/replenishment/services.py`  
**Complexity**: S (0.5 day)  
**Depends on**: T-025  
**Acceptance criteria**: Excess stock = max(0, stock - PP), never negative

**T-031**: Inter-branch transfer source resolution  
**Capability**: recommendation-engine  
**Work unit**: WU-10  
**Description**: Create RecommendationService.resolve_source(branch_id, part_id, quantity_needed) that checks other branches for excess stock. Prioritize parent DC first (if branch has parent_branch_id). If DC has sufficient excess, recommend transfer from DC. Else, search other branches. Return list of (source_branch_id, quantity) tuples.  
**Files affected**: `apps/replenishment/services.py`  
**Complexity**: M (1.5 days)  
**Depends on**: T-030  
**Acceptance criteria**: DC checked first, other branches searched if DC insufficient, returns source list

**T-032**: Multi-source split logic  
**Capability**: recommendation-engine  
**Work unit**: WU-10  
**Description**: Extend resolve_source to split recommendation across multiple source branches when no single branch has sufficient excess. Allocate from each source up to their excess stock. Track remaining quantity needed. Return partial fulfillment if total excess < quantity_needed.  
**Files affected**: `apps/replenishment/services.py`  
**Complexity**: M (1 day)  
**Depends on**: T-031  
**Acceptance criteria**: Recommendation split across Branch B (8 units) and Branch C (12 units) when needed 20

**T-033**: Partial fulfillment alert and DC self-replenishment  
**Capability**: recommendation-engine  
**Work unit**: WU-10  
**Description**: If total excess stock < quantity_needed, create partial fulfillment recommendation (transfer what's available, external supplier for remainder). Trigger alert to branch manager, coordinator(s), and gerente. For DC self-replenishment: calculate projected stock after transfers to dependents, if ≤ PP, recommend external supplier for DC.  
**Files affected**: `apps/replenishment/services.py`, `apps/notifications/services.py`  
**Complexity**: M (1.5 days)  
**Depends on**: T-032  
**Acceptance criteria**: Partial fulfillment alert sent, DC self-replenishment triggered when projected stock ≤ PP

### WU-11: Approval Workflow — State Machine

**[x] T-034**: Recommendation state transitions  
**Capability**: approval-workflow  
**Work unit**: WU-11  
**Description**: Create RecommendationService.transition_state(recommendation_id, new_state, user_id, role_id) that validates state transitions (pending → approved/rejected/handled, approved → ordered). Record each transition in AuditLog (user_id, role_used_id, action, entity_type, entity_id, timestamp, metadata_json).  
**Files affected**: `apps/replenishment/services.py`, `apps/core/models.py` (AuditLog)  
**Complexity**: M (1 day)  
**Depends on**: T-027  
**Acceptance criteria**: State transitions valid, audit log records each transition with role used

**[x] T-035**: Branch manager as default approver  
**Capability**: approval-workflow  
**Work unit**: WU-11  
**Description**: Set default approver for pending recommendations to branch manager of target branch. Add assigned_approver_id field to Recommendation model. Query UserRole to find branch manager for the branch.  
**Files affected**: `apps/replenishment/models.py`, `apps/replenishment/services.py`  
**Complexity**: S (0.5 day)  
**Depends on**: T-034  
**Acceptance criteria**: New recommendation assigned to branch manager of target branch

**[x] T-036**: Bulk actions (approve/reject/handle multiple)  
**Capability**: approval-workflow  
**Work unit**: WU-11  
**Description**: Create RecommendationService.bulk_transition(recommendation_ids, new_state, user_id, role_id) that processes multiple recommendations in one action. Filter to only pending recommendations. Log each transition individually in audit log. Return count of processed recommendations.  
**Files affected**: `apps/replenishment/services.py`  
**Complexity**: S (0.5 day)  
**Depends on**: T-034  
**Acceptance criteria**: Bulk action processes only pending, logs each individually, returns count

### WU-12: Approval Workflow — Escalation & Cross-Coordinator

**[x] T-037**: Threshold-based escalation  
**Capability**: approval-workflow  
**Work unit**: WU-12  
**Description**: Add escalation_threshold_value, escalation_threshold_volume, escalation_threshold_impact fields to Tenant.config_json. Create RecommendationService.check_escalation(recommendation_id) that compares recommendation value/volume/impact against thresholds. If crossed, auto-escalate to coordinator (change assigned_approver_id to coordinator). Log escalation with reason.  
**Files affected**: `apps/core/models.py`, `apps/replenishment/services.py`  
**Complexity**: M (1 day)  
**Depends on**: T-035  
**Acceptance criteria**: Recommendation crossing threshold auto-escalates to coordinator, logged with reason  

**[x] T-038**: Cross-coordinator transfer approval  
**Capability**: approval-workflow  
**Work unit**: WU-12  
**Description**: Detect cross-coordinator transfers (source and destination branches in different coordinator scopes). Route to gerente for approval. Notify both coordinators (but they do not approve). Add is_cross_coordinator flag to Recommendation model.  
**Files affected**: `apps/replenishment/models.py`, `apps/replenishment/services.py`, `apps/notifications/services.py`  
**Complexity**: M (1.5 days)  
**Depends on**: T-037  
**Acceptance criteria**: Cross-coordinator transfer routed to gerente, coordinators notified, gerente approval required  

**[x] T-039**: Coordinator escalation to gerente  
**Capability**: approval-workflow  
**Work unit**: WU-12  
**Description**: Allow coordinator to escalate recommendation to gerente (manual escalation). Change assigned_approver_id to gerente. Log escalation with from_role=coordinator, to_role=gerente.  
**Files affected**: `apps/replenishment/services.py`  
**Complexity**: S (0.5 day)  
**Depends on**: T-037  
**Acceptance criteria**: Coordinator can escalate to gerente, logged  


### WU-13: Demand Override

**T-040**: DemandOverride model  
**Capability**: demand-override  
**Work unit**: WU-13  
**Description**: Create DemandOverride model (id, part_id, branch_id, override_type [persistent/per_run/with_expiry], quantity, expires_at, created_by, created_at, status [active/expired]). Add unique constraint on (part_id, branch_id, status=active) — only one active override per SKU per branch.  
**Files affected**: `apps/replenishment/models.py`, `apps/replenishment/migrations/`  
**Complexity**: S (0.5 day)  
**Depends on**: T-024  
**Acceptance criteria**: DemandOverride model exists, only one active override per SKU per branch

**T-041**: Override service with type selection  
**Capability**: demand-override  
**Work unit**: WU-13  
**Description**: Create DemandOverrideService.apply_override(part_id, branch_id, override_type, quantity, expires_at, user_id) that validates override_type, creates DemandOverride, logs in audit log. For with_expiry, validate expires_at is in the future. Reject negative quantity.  
**Files affected**: `apps/replenishment/services.py`  
**Complexity**: M (1 day)  
**Depends on**: T-040  
**Acceptance criteria**: Override applied with type selection, expires_at validated, negative quantity rejected

**T-042**: Override expiration and calculation integration  
**Capability**: demand-override  
**Work unit**: WU-13  
**Description**: Create DemandOverrideService.expire_overrides() that marks overrides with expires_at < now as expired. Modify PlanningService.calculate_planning_target to check for active override and use overridden velocity instead of calculated velocity. Per-run overrides discarded after run completes.  
**Files affected**: `apps/replenishment/services.py`  
**Complexity**: M (1 day)  
**Depends on**: T-041, T-024  
**Acceptance criteria**: Expired overrides marked, planning target uses overridden velocity, per-run overrides discarded

### WU-14: Notification Service

**T-043**: Notification model and email templates  
**Capability**: notification-service  
**Work unit**: WU-14  
**Description**: Create Notification model (id, user_id, notification_type, entity_type, entity_id, message, read_at, created_at). Create email templates: recommendation_pending, recommendation_escalated, partial_fulfillment, cold_start_flag, classification_review, dc_stock_critical. Use Django's email system + Anymail.  
**Files affected**: `apps/notifications/models.py`, `apps/notifications/migrations/`, `templates/emails/*.html`  
**Complexity**: M (1 day)  
**Depends on**: T-027  
**Acceptance criteria**: Notification model exists, email templates render correctly

**T-044**: Notification dispatch service  
**Capability**: notification-service  
**Work unit**: WU-14  
**Description**: Create NotificationService.send_notification(user_id, notification_type, entity_type, entity_id, message) that creates Notification and sends email. Create NotificationService.send_digest(branch_id, run_date) that batches all notifications for a run into one email. Retry failed emails (3 attempts).  
**Files affected**: `apps/notifications/services.py`  
**Complexity**: M (1.5 days)  
**Depends on**: T-043  
**Acceptance criteria**: Notification created and email sent, digest batches notifications, failed emails retried

**T-045**: In-app notification creation  
**Capability**: notification-service  
**Work unit**: WU-14  
**Description**: Create NotificationService.create_in_app_notification(user_id, notification_type, entity_type, entity_id, message) that creates Notification without sending email. Call this for real-time in-app notifications (within 5 minutes of event).  
**Files affected**: `apps/notifications/services.py`  
**Complexity**: S (0.5 day)  
**Depends on**: T-043  
**Acceptance criteria**: In-app notification created, appears in dashboard within 5 minutes

**T-046**: Notification triggers for all events  
**Capability**: notification-service  
**Work unit**: WU-14  
**Description**: Wire up notification triggers: recommendation_pending (branch manager), recommendation_escalated (coordinator/gerente), partial_fulfillment (branch manager + coordinators + gerente), cold_start_flag (branch manager), classification_review (gerente/delegated coordinator), dc_stock_critical (DC manager + coordinators + gerente). Admin receives no notifications.  
**Files affected**: `apps/replenishment/services.py`, `apps/classification/services.py`, `apps/notifications/services.py`  
**Complexity**: M (1 day)  
**Depends on**: T-044, T-045  
**Acceptance criteria**: All notification types triggered correctly, admin receives no notifications

### WU-15: Dashboard — Branch Manager View

**T-047**: Dashboard base template and KPI tile component  
**Capability**: dashboard  
**Work unit**: WU-15  
**Description**: Create `templates/dashboard/base.html` with Pico.css styling. Create KPI tile component (Stock Total, Rotación, Cobertura, Stock Obsoleto, Stock Excesivo). Add HTMX for auto-refresh every 60 seconds.  
**Files affected**: `templates/dashboard/base.html`, `templates/dashboard/components/kpi_tile.html`, `static/css/style.css`  
**Complexity**: M (1 day)  
**Depends on**: T-003  
**Acceptance criteria**: Base template renders, KPI tiles display, HTMX refresh works

**T-048**: Branch manager dashboard view  
**Capability**: dashboard  
**Work unit**: WU-15  
**Description**: Create BranchManagerDashboardView that shows: pending recommendations count, KPI tiles (scoped to own branch), approval history, override log, classification results table. Filter by branch_id = user's assigned branch.  
**Files affected**: `apps/dashboard/views.py`, `apps/dashboard/urls.py`, `templates/dashboard/branch_manager.html`  
**Complexity**: M (1.5 days)  
**Depends on**: T-047, T-027, T-042  
**Acceptance criteria**: Branch manager sees own branch data, pending count displayed, KPI tiles scoped to branch

**T-049**: Classification results table with filtering  
**Capability**: dashboard  
**Work unit**: WU-15  
**Description**: Add classification results table to branch manager dashboard. Show SKU, Volume Class, Lifecycle Stage. Add filters for Volume Class and Lifecycle Stage. Add sorting by either column. Highlight special flags (NS-C) visually.  
**Files affected**: `templates/dashboard/branch_manager.html`, `apps/dashboard/views.py`  
**Complexity**: M (1 day)  
**Depends on**: T-048, T-020  
**Acceptance criteria**: Table shows classification results, filters and sorting work, NS-C highlighted

**T-050**: CSV export for recommendations and KPIs  
**Capability**: dashboard  
**Work unit**: WU-15  
**Description**: Add CSV export button to recommendation table and KPI tiles. Use Django's csv.writer to generate CSV with all visible columns. Handle special characters in SKU descriptions (proper escaping).  
**Files affected**: `apps/dashboard/views.py`, `templates/dashboard/branch_manager.html`  
**Complexity**: S (0.5 day)  
**Depends on**: T-048  
**Acceptance criteria**: CSV download includes all columns, special characters escaped

### WU-16: Dashboard — Coordinator, Gerente, Admin Views

**T-051**: Coordinator dashboard view  
**Capability**: dashboard  
**Work unit**: WU-16  
**Description**: Create CoordinatorDashboardView that shows: aggregated KPIs for branches in scope, escalated items widget, inter-branch transfer status widget. Allow drill-down into each branch. Filter by coordinator's scope (UserRole.scope_json).  
**Files affected**: `apps/dashboard/views.py`, `apps/dashboard/urls.py`, `templates/dashboard/coordinator.html`  
**Complexity**: M (1.5 days)  
**Depends on**: T-047, T-037  
**Acceptance criteria**: Coordinator sees aggregated data for scope, drill-down works, escalated items displayed

**T-052**: Gerente dashboard view  
**Capability**: dashboard  
**Work unit**: WU-16  
**Description**: Create GerenteDashboardView that shows: org-wide KPIs, cross-coordinator transfer queue, classification review queue. Filter by tenant_id. Show all branches, all coordinators.  
**Files affected**: `apps/dashboard/views.py`, `apps/dashboard/urls.py`, `templates/dashboard/gerente.html`  
**Complexity**: M (1.5 days)  
**Depends on**: T-047, T-038, T-022  
**Acceptance criteria**: Gerente sees org-wide KPIs, cross-coordinator queue, classification review queue

**T-053**: Admin dashboard view  
**Capability**: dashboard  
**Work unit**: WU-16  
**Description**: Create AdminDashboardView that shows: all branches, user management panel, system configuration panel, global KPIs. Link to Django admin for detailed management.  
**Files affected**: `apps/dashboard/views.py`, `apps/dashboard/urls.py`, `templates/dashboard/admin.html`  
**Complexity**: M (1 day)  
**Depends on**: T-047  
**Acceptance criteria**: Admin sees all branches, user management, system config, global KPIs

**T-054**: Multi-role dashboard union  
**Capability**: dashboard  
**Work unit**: WU-16  
**Description**: Modify dashboard routing to show union of all role-specific views for users with multiple roles. If user is both branch_manager and coordinator, show both views. Use template conditionals to render role-specific widgets.  
**Files affected**: `apps/dashboard/views.py`, `templates/dashboard/base.html`  
**Complexity**: S (0.5 day)  
**Depends on**: T-048, T-051, T-052, T-053  
**Acceptance criteria**: User with multiple roles sees union of views

### WU-17: Sector Configuration

**T-055**: SectorConfiguration model  
**Capability**: sector-configuration  
**Work unit**: WU-17  
**Description**: Create SectorConfiguration model (id, tenant_id, sector_key, config_json). config_json contains: terminology labels, classification thresholds, lifecycle rules, special categories. Add unique constraint on (tenant_id, sector_key).  
**Files affected**: `apps/core/models.py`, `apps/core/migrations/`, `apps/core/admin.py`  
**Complexity**: S (0.5 day)  
**Depends on**: T-002  
**Acceptance criteria**: SectorConfiguration model exists, admin can create/view/modify

**T-056**: Default automotive sector configuration  
**Capability**: sector-configuration  
**Work unit**: WU-17  
**Description**: Create data migration to insert default "automotive_aftermarket" sector configuration with: terminology (Part, Branch, Warehouse Manager), classification thresholds (VC1 >250, etc.), lifecycle stages (N1/N2/N3, OBS-S/OBS-N/OBS-P/OBS-R, Inactive, NS-C/NS-NS).  
**Files affected**: `apps/core/migrations/`  
**Complexity**: S (0.5 day)  
**Depends on**: T-055  
**Acceptance criteria**: Default automotive config inserted, new tenants assigned to it

**T-057**: Sector-specific terminology and thresholds in engine  
**Capability**: sector-configuration  
**Work unit**: WU-17  
**Description**: Modify ClassificationService to read thresholds from SectorConfiguration.config_json instead of hardcoded values. Modify UI templates to use terminology from config_json. Ensure core formulas (Planning Target, Punto de Pedido, Cantidad de Pedido) remain unchanged.  
**Files affected**: `apps/classification/services.py`, `templates/**/*.html`  
**Complexity**: M (1 day)  
**Depends on**: T-056, T-020  
**Acceptance criteria**: Classification uses sector-specific thresholds, UI uses sector terminology, formulas unchanged

### WU-18: Onboarding Flow

**T-058**: Onboarding checklist model and view  
**Capability**: onboarding  
**Work unit**: WU-18  
**Description**: Create OnboardingChecklist model (id, branch_id, dms_connected, sales_backfilled, manager_assigned, test_run_completed, go_live_at). Create OnboardingView that displays checklist with progress (checkmarks for completed steps, highlight current step).  
**Files affected**: `apps/onboarding/models.py`, `apps/onboarding/migrations/`, `apps/onboarding/views.py`, `templates/onboarding/checklist.html`  
**Complexity**: M (1 day)  
**Depends on**: T-008  
**Acceptance criteria**: Checklist displays progress, steps marked complete, current step highlighted

**T-059**: DMS connection validation  
**Capability**: onboarding  
**Work unit**: WU-18  
**Description**: Create OnboardingService.validate_dms_connection(branch_id, adapter_config) that tests connection, validates required tables/views accessible, reports missing data sources. Mark dms_connected = True if successful. Block next step if validation fails.  
**Files affected**: `apps/onboarding/services.py`  
**Complexity**: M (1 day)  
**Depends on**: T-058, T-011  
**Acceptance criteria**: DMS connection validated, missing tables reported, next step blocked if fails

**T-060**: Sales backfill and manager assignment  
**Capability**: onboarding  
**Work unit**: WU-18  
**Description**: Create OnboardingService.backfill_sales(branch_id) that imports 12+ months of sales history. Warn if <12 months but do not block. Create OnboardingService.assign_branch_manager(branch_id, user_id) that links manager to branch. Mark sales_backfilled and manager_assigned = True.  
**Files affected**: `apps/onboarding/services.py`  
**Complexity**: M (1 day)  
**Depends on**: T-059, T-016  
**Acceptance criteria**: Sales backfilled (12+ months), manager assigned, checklist updated

**T-061**: First test run and go-live  
**Capability**: onboarding  
**Work unit**: WU-18  
**Description**: Create OnboardingService.run_first_test(branch_id) that validates end-to-end flow: catalog read → velocity → classification → Planning Target → recommendations. Display results in dashboard. Block if manager not assigned. Mark test_run_completed = True. Add "Go Live" button that sets go_live_at and enables scheduled runs.  
**Files affected**: `apps/onboarding/services.py`, `templates/onboarding/checklist.html`  
**Complexity**: M (1.5 days)  
**Depends on**: T-060, T-027  
**Acceptance criteria**: First test run validates flow, results displayed, go-live enables scheduling

### WU-19: Scheduling & Background Jobs

**T-062**: Django-Q2 configuration  
**Capability**: operations  
**Work unit**: WU-19  
**Description**: Add django-q2 to requirements. Configure in settings.py: Q_CLUSTER with ORM broker for dev, Redis for prod. Set workers, timeout, retry. Create `python manage.py qcluster` command for worker process.  
**Files affected**: `config/settings.py`, `requirements.txt`  
**Complexity**: S (0.5 day)  
**Depends on**: T-001  
**Acceptance criteria**: Django-Q2 configured, worker process starts

**T-063**: Replenishment run scheduled job  
**Capability**: operations  
**Work unit**: WU-19  
**Description**: Create replenishment_run job that calls RecommendationService.generate_recommendations(branch_id, run_date). Schedule per branch via Django-Q2 Schedule model (weekly by default, configurable cron). Add idempotency key (branch_id, run_date).  
**Files affected**: `apps/replenishment/jobs.py`, `apps/replenishment/services.py`  
**Complexity**: M (1 day)  
**Depends on**: T-062, T-027  
**Acceptance criteria**: Replenishment run scheduled per branch, idempotent, runs weekly

**T-064**: Classification pass scheduled job  
**Capability**: operations  
**Work unit**: WU-19  
**Description**: Create classification_pass job that calls ClassificationService.classify_all(tenant_id). Schedule monthly via Django-Q2 (cron 0 3 1 * *). Add idempotency key (tenant_id, month_key).  
**Files affected**: `apps/classification/jobs.py`, `apps/classification/services.py`  
**Complexity**: S (0.5 day)  
**Depends on**: T-062, T-020  
**Acceptance criteria**: Classification pass scheduled monthly, idempotent

**T-065**: Notification dispatch and retry  
**Capability**: operations  
**Work unit**: WU-19  
**Description**: Create notification_dispatch job that runs every 15 minutes, processes pending Notification records, sends emails. Retry failed emails (3 attempts, 5min delay). Log dead tasks.  
**Files affected**: `apps/notifications/jobs.py`, `apps/notifications/services.py`  
**Complexity**: S (0.5 day)  
**Depends on**: T-062, T-044  
**Acceptance criteria**: Notification dispatch runs every 15 min, retries failed emails, logs dead tasks

### WU-20: Operations — Deployment, Logging, Health

**T-066**: Dockerfile and docker-compose.yml  
**Capability**: operations  
**Work unit**: WU-20  
**Description**: Create multi-stage Dockerfile (python:3.12-slim, gunicorn + whitenoise for static). Create docker-compose.yml with services: app (web), worker (qcluster), db (postgres:16), redis. Add .dockerignore.  
**Files affected**: `Dockerfile`, `docker-compose.yml`, `.dockerignore`  
**Complexity**: M (1 day)  
**Depends on**: T-001  
**Acceptance criteria**: `docker-compose up` starts all services, app accessible on localhost

**T-067**: Structured logging with structlog  
**Capability**: operations  
**Work unit**: WU-20  
**Description**: Add structlog to requirements. Configure in settings.py to output JSON to stdout. Add middleware to inject request_id, user_id, branch_id into log context. Log request_completed, unhandled_exception, job_started events.  
**Files affected**: `config/settings.py`, `config/middleware.py`, `requirements.txt`  
**Complexity**: M (1 day)  
**Depends on**: T-001  
**Acceptance criteria**: JSON logs to stdout with timestamp, level, event, request_id, user_id, branch_id

**T-068**: Health check endpoint  
**Capability**: operations  
**Work unit**: WU-20  
**Description**: Create /health/ endpoint that checks: web service (always OK), database connection (SELECT 1), task queue (ping Redis or DB). Return HTTP 200 with {"web": "ok", "db": "ok", "queue": "ok"} or HTTP 503 if any component fails.  
**Files affected**: `apps/core/views.py`, `apps/core/urls.py`  
**Complexity**: S (0.5 day)  
**Depends on**: T-001  
**Acceptance criteria**: Health check returns 200 when healthy, 503 when db or queue down

**T-069**: Sentry integration (optional)  
**Capability**: operations  
**Work unit**: WU-20  
**Description**: Add sentry-sdk to requirements. Configure in settings.py if SENTRY_DSN env var set. Capture unhandled exceptions with stack trace, user context, request data. If not set, log to stdout only.  
**Files affected**: `config/settings.py`, `requirements.txt`  
**Complexity**: S (0.5 day)  
**Depends on**: T-067  
**Acceptance criteria**: Sentry active when SENTRY_DSN set, errors reported with context

**T-070**: CI/CD pipeline (GitHub Actions)  
**Capability**: operations  
**Work unit**: WU-20  
**Description**: Create .github/workflows/ci.yml that runs on push to main: ruff lint, pytest, Docker build, push to registry. Render auto-deploys on push. Fail pipeline if lint or tests fail.  
**Files affected**: `.github/workflows/ci.yml`  
**Complexity**: M (1 day)  
**Depends on**: T-066  
**Acceptance criteria**: CI pipeline runs lint, test, build on every push, Render auto-deploys

---

## Phase Roadmap

### Phase 0 (Spike) — ✅ DONE
**Status**: Complete (51 tests passing)  
**Deliverable**: Formula validation, methodology proof  
**Files**: `spike/` directory  

### Phase 1 (MVP) — 10 Weeks
**Scope**: Full v1 functionality, simple tooling, basic UI  
**Weeks 1-10**: See detailed roadmap above  
**Deliverable**: Working Django app with all 13 capabilities  
**Exit criteria**: First test run validates end-to-end flow, scheduled jobs run, dashboard displays KPIs  

### Phase 1.5 (v1 Complete) — 4-6 Weeks (Deferred)
**Scope**: Hardening, advanced features, production readiness  
**Tasks**:
- E2E tests (Playwright)
- Advanced analytics dashboard (forecast accuracy, recommendation quality)
- Performance optimization (query optimization, caching)
- Security audit (penetration testing, OWASP compliance)
- Documentation (user manual, admin guide, API docs)
- Load testing (100+ branches, 10K+ SKUs)

### Phase 2+ (v2) — Deferred
**Scope**: Multi-tenant SaaS, advanced features  
**Features**:
- Multi-tenant SaaS activation (self-service onboarding)
- Automated seasonal adjustment (Ciclo Temporal / estacionalidad)
- Automated obsoletion detection (without gerente review)
- External supplier identification in recommendations
- Vehicle compatibility (model/year fitment lookup)
- Branch proximity metadata for transfer optimization
- Multi-level DC hierarchies (DC depending on another DC)
- Advanced analytics (forecast accuracy, recommendation quality scoring)
- Mobile app (native iOS/Android)

---

## Risks and Dependencies

### External Dependencies
- **Python 3.12+**: Required for Django 5.1+ and modern Python features
- **PostgreSQL 16+**: Required for JSONB, window functions, enums
- **Render account**: For PaaS deployment (free tier for development)
- **Docker**: For local development and VPS deployment
- **Email provider**: SendGrid/Postmark/SES/Mailgun (Anymail supports all)
- **Sentry account**: For error tracking (free tier sufficient for v1)

### Blockers
- **DMS schema unknown**: First DMS adapter cannot be built until we know which DMS the first tenant uses. MockDMSAdapter unblocks development.
- **No pilot client**: Development continues without confirmed first tenant. Mock data and developer as first user unblocks validation.

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Django admin insufficient for complex workflows | Medium | Medium | Build custom CRUD views for approval workflow, classification review |
| HTMX lacks interactivity for rich UX | Low | Low | Add Alpine.js for complex interactions (override type selection, bulk actions) |
| Migration from spike formulas to Django ORM introduces bugs | Medium | High | Port all 51 spike tests to pytest-django, validate formulas against spike output |
| DMS adapter interface too rigid for real DMS | Medium | Medium | Keep interface generic, allow adapter to return raw data and normalize internally |
| Escalation thresholds set too low → coordinator overload | Medium | Medium | Default thresholds based on industry averages, configurable per tenant, monitor escalation rate |
| Override drift (persistent overrides unchanged after 90 days) | Medium | Medium | Dashboard shows override age, admin can audit and reset, target <10% drift |
| Notification fatigue (too many emails) | Medium | Low | Digest email per run (not per recommendation), daily summary, in-app for real-time |
| Performance degradation with 10K+ SKUs | Low | High | Optimize queries (use select_related, prefetch_related), add database indexes, cache KPIs |
| Data quality issues from DMS (missing sales, incorrect stock) | High | High | Validation at ingestion, flag anomalies in dashboard, tenant data audit before go-live |

### Mitigation Strategies
- **MockDMSAdapter**: Unblocks development until real DMS schema known
- **Spike tests**: All 51 tests ported to pytest-django to validate formula migration
- **Incremental delivery**: Each WU produces working functionality, can demo at any point
- **Chained PRs**: 400-line review budget per PR keeps reviews focused and fast
- **Developer as first user**: Validate UX and workflow before first tenant

---

## Open Questions (Deferred)

| ID | Question | Resolution |
|----|----------|------------|
| Q-001 | Exact weighted velocity weights (spike uses linear 0.5→1.5) | Defer to production tuning. Linear ramp is good starting point. Monitor forecast accuracy. |
| Q-002 | Default Periodo de Stock, Stock de Seguridad, Tiempo de Pedido values | Set initial values during first tenant onboarding based on their historical data. Configurable per branch. |
| Q-003 | First DMS target | Deferred until first tenant signs. BaseDMSAdapter interface is generic. First implementation validates it. |
| Q-004 | Email provider (SendGrid, SES, Postmark) | Pick cheapest with adequate deliverability in tenant's region. SendGrid free tier enough for v1. |
| Q-005 | Notification throttling strategy | Start with one digest per run + daily 8AM summary. Tune based on user feedback. |
| Q-006 | CSS framework (Pico.css vs Tailwind vs Bootstrap) | Pico.css for v1 (minimal, no build step). Evaluate Tailwind if custom designs needed for client demos. |
| Q-007 | Log aggregation tool | stdout for v1 development. Add Papertrail/Logtail/Loki when first tenant goes live. |
| Q-008 | Classification pass frequency | Monthly (separate from replenishment). Replenishment runs weekly; reclassifying on every run is wasteful. |

---

## Success Criteria

### Phase 1 MVP Exit Criteria
- [ ] All 13 capabilities implemented and tested
- [ ] All 14 business rules from proposal §7 implementable
- [ ] First test run validates end-to-end flow (catalog → velocity → classification → Planning Target → recommendations)
- [ ] Scheduled jobs run (replenishment weekly, classification monthly)
- [ ] Dashboard displays KPIs (Stock Total, Rotación, Cobertura, Stock Obsoleto, Stock Excesivo)
- [ ] Branch manager can approve/reject recommendations
- [ ] Escalation workflow routes high-impact recommendations to coordinator
- [ ] Demand override UX prompts for type selection
- [ ] Email + in-app notifications delivered
- [ ] Docker Compose starts all services
- [ ] CI/CD pipeline runs on every push
- [ ] Target onboarding time: ≤28 days from kickoff to first live run

### Phase 1.5 Exit Criteria (Deferred)
- [ ] E2E tests cover critical flows
- [ ] Performance validated with 10K+ SKUs
- [ ] Security audit passed
- [ ] User manual and admin guide complete

### Phase 2+ Exit Criteria (Deferred)
- [ ] Multi-tenant SaaS activation works
- [ ] Automated seasonal adjustment implemented
- [ ] External supplier identification in recommendations
- [ ] Vehicle compatibility (automotive) implemented

---

## Traceability

### Spec Coverage
- ✅ catalog-ingestion: T-008 through T-016
- ✅ velocity-calculation: T-017 through T-019
- ✅ classification-engine: T-020 through T-023
- ✅ planning-calculation: T-024 through T-026
- ✅ recommendation-engine: T-027 through T-033
- ✅ approval-workflow: T-034 through T-039
- ✅ demand-override: T-040 through T-042
- ✅ notification-service: T-043 through T-046
- ✅ dashboard: T-047 through T-054
- ✅ onboarding: T-058 through T-061
- ✅ user-management: T-001 through T-007
- ✅ sector-configuration: T-055 through T-057
- ✅ operations: T-062 through T-070

### Business Rules Coverage
1. ✅ Replenishment hierarchy (transfer first → supplier fallback): T-031, T-032
2. ✅ Punto de Pedido trigger: T-027
3. ✅ Stock en Tránsito treated separately: T-014, T-025
4. ✅ Classification is calculated, not manual: T-020, T-021, T-022
5. ✅ Lifecycle stages drive behavior: T-021, T-022, T-028
6. ✅ Override UX with mandatory type selection: T-041
7. ✅ Cold-start mandatory override: T-028, T-045
8. ✅ Advisory-only (never modifies DMS stock): All recommendation tasks
9. ✅ Single tenant, multi-branch, tenant_id present: T-002, T-008
10. ✅ Part identity (internal SKU code primary key): T-009
11. ✅ Escalation by threshold: T-037
12. ✅ External replenishment off-system: T-033 (alert only, no supplier named)
13. ✅ Cross-coordinator transfer: T-038
14. ✅ Excess stock for inter-branch transfer: T-030, T-031, T-032

---

## Next Steps

1. **Start WU-01**: Django scaffold + core models + auth (Week 1)
2. **Demo after each WU**: Validate working functionality before moving to next WU
3. **Port spike tests**: Migrate all 51 spike tests to pytest-django during WU-06 (velocity calculation)
4. **MockDMSAdapter**: Use throughout development until real DMS schema known
5. **Developer as first user**: Validate UX and workflow before first tenant onboarding

**Recommended next action**: Begin T-001 (Django project scaffold).
